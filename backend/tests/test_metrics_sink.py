"""Testes de app.observability.metrics: NoopMetricsSink (no-op),
CloudWatchEmfMetricsSink (emite uma linha em formato EMF por chamada, via
o pipeline de log já existente — ver JsonFormatter em app.logging_config)
e get_metrics_sink() (fábrica guiada por settings.METRICS_BACKEND)."""

import io
import json
import logging

from app.logging_config import JsonFormatter, RequestIdLogFilter
from app.observability.metrics import (
    CloudWatchEmfMetricsSink,
    NoopMetricsSink,
    get_metrics_sink,
)


def _make_capturing_logger(name: str):
    """Logger isolado (não propaga pro root) com um handler que escreve
    num StringIO, formatado com JsonFormatter + RequestIdLogFilter — mesmo
    padrão de backend/tests/test_logging_config.py, pra inspecionar a
    linha JSON emitida sem depender do estado do root logger."""
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RequestIdLogFilter())

    logger = logging.getLogger(name)
    logger.handlers = [handler]
    logger.propagate = False
    logger.setLevel(logging.DEBUG)
    return logger, stream


class TestNoopMetricsSink:
    def test_record_request_does_nothing(self):
        sink = NoopMetricsSink()
        # Não deve levantar nem produzir efeito colateral observável.
        sink.record_request(
            method="GET", route="/api/tickets", status_code=200, duration_ms=12.3
        )


class TestCloudWatchEmfMetricsSink:
    def _record_and_parse(self, **kwargs):
        logger, stream = _make_capturing_logger(
            "app.observability.metrics.test_instance"
        )
        sink = CloudWatchEmfMetricsSink(logger=logger)
        sink.record_request(**kwargs)
        return json.loads(stream.getvalue())

    def test_emits_one_json_line_with_emf_envelope(self):
        payload = self._record_and_parse(
            method="GET", route="/api/tickets", status_code=200, duration_ms=42.5
        )
        assert "_aws" in payload
        emf = payload["_aws"]
        assert "Timestamp" in emf
        assert isinstance(emf["Timestamp"], int)
        assert len(emf["CloudWatchMetrics"]) == 1
        block = emf["CloudWatchMetrics"][0]
        assert block["Dimensions"] == [["method", "route"]]
        metric_names = {m["Name"] for m in block["Metrics"]}
        assert metric_names == {"RequestCount", "Duration", "ErrorCount"}

    def test_uses_configured_namespace(self, monkeypatch):
        from app.config import settings

        monkeypatch.setattr(settings, "METRICS_NAMESPACE", "TesteNamespace")
        payload = self._record_and_parse(
            method="GET", route="/api/tickets", status_code=200, duration_ms=1.0
        )
        assert payload["_aws"]["CloudWatchMetrics"][0]["Namespace"] == "TesteNamespace"

    def test_dimension_values_and_metric_values_are_correct(self):
        payload = self._record_and_parse(
            method="POST",
            route="/api/tickets/{ticket_id}/enrich",
            status_code=200,
            duration_ms=99.9,
        )
        assert payload["method"] == "POST"
        assert payload["route"] == "/api/tickets/{ticket_id}/enrich"
        assert payload["RequestCount"] == 1
        assert payload["Duration"] == 99.9

    def test_error_count_is_zero_below_500(self):
        payload = self._record_and_parse(
            method="GET", route="/api/tickets", status_code=404, duration_ms=5.0
        )
        assert payload["ErrorCount"] == 0

    def test_error_count_is_one_at_or_above_500(self):
        payload = self._record_and_parse(
            method="GET", route="/api/tickets", status_code=500, duration_ms=5.0
        )
        assert payload["ErrorCount"] == 1

    def test_emits_metric_even_when_logger_level_is_higher_than_info(self):
        """Regressão pro acoplamento com LOG_LEVEL: o construtor deve pinar
        o nível do logger em INFO, independente do que o logger já tinha
        (ex.: herdado de configure_logging() com LOG_LEVEL=WARNING/CRITICAL
        em produção) — senão a métrica silenciosamente para de ser emitida."""
        logger, stream = _make_capturing_logger(
            "app.observability.metrics.test_instance_high_level"
        )
        logger.setLevel(logging.CRITICAL)

        sink = CloudWatchEmfMetricsSink(logger=logger)
        sink.record_request(
            method="GET", route="/api/tickets", status_code=200, duration_ms=1.0
        )

        payload = json.loads(stream.getvalue())
        assert "_aws" in payload


class TestGetMetricsSink:
    def test_noop_backend_returns_noop_sink(self, monkeypatch):
        from app.config import settings

        monkeypatch.setattr(settings, "METRICS_BACKEND", "noop")
        assert isinstance(get_metrics_sink(), NoopMetricsSink)

    def test_cloudwatch_backend_returns_cloudwatch_sink(self, monkeypatch):
        from app.config import settings

        monkeypatch.setattr(settings, "METRICS_BACKEND", "cloudwatch")
        assert isinstance(get_metrics_sink(), CloudWatchEmfMetricsSink)

    def test_invalid_backend_falls_back_to_noop_with_warning(self, monkeypatch, caplog):
        from app.config import settings

        monkeypatch.setattr(settings, "METRICS_BACKEND", "not_a_backend")
        with caplog.at_level(logging.WARNING):
            sink = get_metrics_sink()
        assert isinstance(sink, NoopMetricsSink)
        warnings = [
            r
            for r in caplog.records
            if r.getMessage() == "invalid_metrics_backend_falling_back_to_noop"
        ]
        assert len(warnings) == 1
