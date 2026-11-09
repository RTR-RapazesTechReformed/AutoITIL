"""Métricas de aplicação (infra) desacopladas do destino: MetricsSink é um
Protocol que qualquer backend futuro pode implementar sem herdar nada.
CloudWatchEmfMetricsSink não faz nenhuma chamada de rede — emite uma linha
de log em formato EMF (Embedded Metric Format), que o CloudWatch converte
sozinho em métricas reais quando os logs do container chegam até ele."""

from __future__ import annotations

import logging
import time
from typing import Protocol, runtime_checkable

from app.config import settings

logger = logging.getLogger(__name__)


@runtime_checkable
class MetricsSink(Protocol):
    def record_request(
        self, *, method: str, route: str, status_code: int, duration_ms: float
    ) -> None: ...


class NoopMetricsSink:
    """Default local/testes — não produz nenhum efeito colateral."""

    def record_request(
        self, *, method: str, route: str, status_code: int, duration_ms: float
    ) -> None:
        pass


class CloudWatchEmfMetricsSink:
    """Loga uma linha JSON em formato EMF por requisição, via o pipeline de
    log já existente (JsonFormatter). Zero chamada AWS, zero SDK, zero
    credencial exigida pra rodar — o CloudWatch extrai as métricas sozinho
    a partir da chave "_aws" quando os logs do container chegam até ele."""

    def __init__(self, *, logger: logging.Logger | None = None) -> None:
        self._logger = logger if logger is not None else globals()["logger"]
        # Pina o nível do próprio logger em INFO, independente do que a
        # hierarquia de loggers (root, via configure_logging/LOG_LEVEL)
        # define — sem isso, um operador setando LOG_LEVEL=WARNING em
        # produção (redução de ruído comum) silenciosamente para de emitir
        # métrica nenhuma, sem erro visível.
        self._logger.setLevel(logging.INFO)

    def record_request(
        self, *, method: str, route: str, status_code: int, duration_ms: float
    ) -> None:
        self._logger.info(
            "request_metric",
            extra={
                "_aws": {
                    "Timestamp": int(time.time() * 1000),
                    "CloudWatchMetrics": [
                        {
                            "Namespace": settings.METRICS_NAMESPACE,
                            "Dimensions": [["method", "route"]],
                            "Metrics": [
                                {"Name": "RequestCount", "Unit": "Count"},
                                {"Name": "Duration", "Unit": "Milliseconds"},
                                {"Name": "ErrorCount", "Unit": "Count"},
                            ],
                        }
                    ],
                },
                "method": method,
                "route": route,
                "RequestCount": 1,
                "Duration": duration_ms,
                "ErrorCount": 1 if status_code >= 500 else 0,
            },
        )


def get_metrics_sink() -> MetricsSink:
    """Fábrica guiada por settings.METRICS_BACKEND. Um valor inválido cai
    em NoopMetricsSink com um warning — mesmo padrão de configure_logging()
    para LOG_LEVEL inválido."""
    backend = settings.METRICS_BACKEND
    if backend == "cloudwatch":
        return CloudWatchEmfMetricsSink()
    if backend != "noop":
        logger.warning("invalid_metrics_backend_falling_back_to_noop")
    return NoopMetricsSink()
