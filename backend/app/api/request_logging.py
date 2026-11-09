"""request_logging.py — RequestIdMiddleware: gera um request_id por
requisição, propaga via app.logging_config.request_id_ctx (assim todo log
emitido durante o processamento carrega o mesmo id — ver
RequestIdLogFilter), devolve o id no header X-Request-ID, loga início e
fim de cada requisição com método/path/status/duração, e emite uma
métrica de aplicação por requisição via MetricsSink (ver
app.observability.metrics) — dimensionada pelo TEMPLATE da rota, não pela
URL concreta, pra não explodir cardinalidade no backend de métricas."""

from __future__ import annotations

import logging
import time
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.logging_config import request_id_ctx
from app.observability.metrics import MetricsSink, get_metrics_sink

logger = logging.getLogger(__name__)


def _route_label(request: Request) -> str:
    """Template da rota casada (ex.: "/api/tickets/{ticket_id}/enrich"), ou
    "unmatched" quando request.scope["route"] não foi populado. Isso cobre
    não só 404 genuíno, mas também requisições rejeitadas por
    ApiKeyMiddleware antes do roteamento (401) e rotas não-APIRoute como o
    mount /static — nenhum desses casos tem um Starlette Route casado no
    momento em que este middleware roda (RequestIdMiddleware é o middleware
    mais externo, então vê a requisição antes de ApiKeyMiddleware e antes do
    roteamento acontecer). Nunca a URL concreta, que teria cardinalidade
    ilimitada como dimensão de métrica."""
    route = request.scope.get("route")
    return route.path if route is not None else "unmatched"


class RequestIdMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, metrics_sink: MetricsSink | None = None) -> None:
        super().__init__(app)
        self._metrics_sink = metrics_sink if metrics_sink is not None else get_metrics_sink()

    def _finish(self, request: Request, status_code: int, start: float) -> float:
        """Computa a duração, loga "request_finished" e emite a métrica de
        requisição — parte compartilhada entre o caminho de sucesso e o
        caminho de exceção não tratada de dispatch(). Uma falha do sink de
        métricas é contida aqui (logada como warning) pra nunca virar um 500
        numa requisição saudável nem mascarar a exceção real da aplicação."""
        duration_ms = round((time.monotonic() - start) * 1000, 2)
        logger.info(
            "request_finished",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": status_code,
                "duration_ms": duration_ms,
            },
        )
        try:
            self._metrics_sink.record_request(
                method=request.method,
                route=_route_label(request),
                status_code=status_code,
                duration_ms=duration_ms,
            )
        except Exception:
            logger.warning("metrics_sink_failed", exc_info=True)
        return duration_ms

    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        token = request_id_ctx.set(request_id)
        start = time.monotonic()
        try:
            logger.info(
                "request_started",
                extra={"method": request.method, "path": request.url.path},
            )
            try:
                response = await call_next(request)
            except Exception:
                self._finish(request, 500, start)
                raise
            self._finish(request, response.status_code, start)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            request_id_ctx.reset(token)
