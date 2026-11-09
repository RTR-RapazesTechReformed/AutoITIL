"""Testes de instrumentação de métricas em RequestIdMiddleware: usa uma app
FastAPI mínima (não app.main.app) com um MetricsSink fake, isolando o
middleware do resto da aplicação — mesmo espírito de isolamento de
backend/tests/test_request_id_middleware.py."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.request_logging import RequestIdMiddleware


class _FakeMetricsSink:
    def __init__(self):
        self.calls = []

    def record_request(self, *, method, route, status_code, duration_ms):
        self.calls.append(
            {
                "method": method,
                "route": route,
                "status_code": status_code,
                "duration_ms": duration_ms,
            }
        )


def _build_app(sink):
    app = FastAPI()
    app.add_middleware(RequestIdMiddleware, metrics_sink=sink)

    @app.get("/ping/{item_id}")
    async def ping(item_id: int):
        return {"item_id": item_id}

    @app.get("/boom")
    async def boom():
        raise RuntimeError("erro proposital pra testar metrics no path 500")

    return app


def test_matched_route_records_route_template_not_concrete_url():
    sink = _FakeMetricsSink()
    client = TestClient(_build_app(sink))

    response = client.get("/ping/42")

    assert response.status_code == 200
    assert len(sink.calls) == 1
    call = sink.calls[0]
    assert call["method"] == "GET"
    assert call["route"] == "/ping/{item_id}"
    assert call["status_code"] == 200
    assert isinstance(call["duration_ms"], float)


def test_unmatched_route_records_unmatched_label():
    sink = _FakeMetricsSink()
    client = TestClient(_build_app(sink))

    response = client.get("/nao-existe")

    assert response.status_code == 404
    assert len(sink.calls) == 1
    assert sink.calls[0]["route"] == "unmatched"
    assert sink.calls[0]["status_code"] == 404


def test_unhandled_exception_records_status_500():
    sink = _FakeMetricsSink()
    client = TestClient(_build_app(sink), raise_server_exceptions=False)

    response = client.get("/boom")

    assert response.status_code == 500
    assert len(sink.calls) == 1
    assert sink.calls[0]["route"] == "/boom"
    assert sink.calls[0]["status_code"] == 500


class _RaisingMetricsSink:
    """Simula um sink real de I/O que falha — usado pra confirmar que uma
    falha do sink nunca vaza pra fora do middleware (Finding 1)."""

    def record_request(self, *, method, route, status_code, duration_ms):
        raise RuntimeError("falha proposital do sink de métricas")


def test_sink_failure_does_not_break_a_healthy_response(caplog):
    sink = _RaisingMetricsSink()
    client = TestClient(_build_app(sink))

    with caplog.at_level("WARNING"):
        response = client.get("/ping/42")

    assert response.status_code == 200
    assert response.json() == {"item_id": 42}
    assert any(r.getMessage() == "metrics_sink_failed" for r in caplog.records)


def test_sink_failure_does_not_mask_the_original_unhandled_exception(caplog):
    sink = _RaisingMetricsSink()
    client = TestClient(_build_app(sink), raise_server_exceptions=True)

    with caplog.at_level("WARNING"):
        try:
            client.get("/boom")
        except RuntimeError as exc:
            assert "erro proposital pra testar metrics no path 500" in str(exc)
        else:
            raise AssertionError("esperava a exceção original da app, não a do sink")

    assert any(r.getMessage() == "metrics_sink_failed" for r in caplog.records)


def test_default_metrics_sink_is_used_when_none_provided():
    """Sem metrics_sink explícito, o middleware não deve quebrar — usa
    get_metrics_sink() (NoopMetricsSink em ambiente de teste, backend
    default)."""
    app = FastAPI()
    app.add_middleware(RequestIdMiddleware)

    @app.get("/ping")
    async def ping():
        return {"ok": True}

    client = TestClient(app)
    response = client.get("/ping")
    assert response.status_code == 200
