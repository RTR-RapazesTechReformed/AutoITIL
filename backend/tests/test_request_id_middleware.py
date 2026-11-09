"""Testes de RequestIdMiddleware: header X-Request-ID na resposta,
correlação de logs pelo mesmo request_id, e cobertura mesmo em requisições
rejeitadas pelo JwtAuthMiddleware (ver ordem de registro em app.main)."""

import logging

from fastapi.testclient import TestClient

from app.main import app
from tests.auth_helpers import AUTH_HEADERS

client_with_key = TestClient(app, headers=AUTH_HEADERS)


def test_response_has_request_id_header():
    response = client_with_key.get("/api/models/quality")
    assert response.headers.get("X-Request-ID")


def test_different_requests_get_different_request_ids():
    id1 = client_with_key.get("/api/models/quality").headers["X-Request-ID"]
    id2 = client_with_key.get("/api/models/quality").headers["X-Request-ID"]
    assert id1 != id2


def test_request_id_present_even_when_auth_rejected():
    """RequestIdMiddleware precisa envolver o JwtAuthMiddleware — mesmo uma
    resposta 401 tem que sair com X-Request-ID e ter sido logada."""
    client_no_key = TestClient(app)
    response = client_no_key.get("/api/models/quality")
    assert response.status_code == 401
    assert response.headers.get("X-Request-ID")


def test_log_during_request_carries_same_request_id_as_header(caplog):
    with caplog.at_level(logging.INFO):
        response = client_with_key.get("/api/models/quality")

    request_id = response.headers["X-Request-ID"]
    finished = [r for r in caplog.records if r.getMessage() == "request_finished"]
    assert len(finished) == 1
    assert finished[0].request_id == request_id
    assert finished[0].status_code == 200
    assert finished[0].method == "GET"
    assert finished[0].path == "/api/models/quality"


def test_request_started_is_logged(caplog):
    with caplog.at_level(logging.INFO):
        client_with_key.get("/api/models/quality")

    started = [r for r in caplog.records if r.getMessage() == "request_started"]
    assert len(started) == 1
    assert started[0].method == "GET"
    assert started[0].path == "/api/models/quality"


def test_request_finished_is_logged_even_on_unhandled_exception(caplog):
    @app.get("/api/__test_only_boom_middleware__")
    async def _boom_mw():
        raise RuntimeError("erro proposital pra testar request_finished no path 500")

    client = TestClient(app, headers=AUTH_HEADERS, raise_server_exceptions=False)

    with caplog.at_level(logging.INFO):
        response = client.get("/api/__test_only_boom_middleware__")

    assert response.status_code == 500
    finished = [r for r in caplog.records if r.getMessage() == "request_finished"]
    assert len(finished) == 1
    assert finished[0].status_code == 500


def test_app_wires_request_id_middleware_with_a_metrics_sink():
    """Fecha o gap entre 'o middleware funciona isolado' (ver
    test_request_metrics_middleware.py) e 'a app de verdade está ligada a
    um sink' — inspeciona app.user_middleware, que expõe o kwarg
    metrics_sink passado em app.add_middleware(RequestIdMiddleware, ...)."""
    from app.api.request_logging import RequestIdMiddleware
    from app.observability.metrics import MetricsSink

    entry = next(
        m for m in app.user_middleware if m.cls is RequestIdMiddleware
    )
    sink = entry.kwargs.get("metrics_sink")
    assert isinstance(sink, MetricsSink)
