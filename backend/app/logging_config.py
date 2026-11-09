"""logging_config.py — logging estruturado em JSON pro backend inteiro.

Toda linha de log sai como um objeto JSON (timestamp, level, logger,
message, request_id, + campos extra). Formato único, sem alternância por
ambiente: o deploy real (AWS ECS + ALB, ver app.config.settings) manda
stdout de container pro CloudWatch, que indexa/filtra bem JSON.

request_id_ctx é a ContextVar que correlaciona todos os logs de uma mesma
requisição HTTP: RequestIdMiddleware (app.api.request_logging) seta o
valor no início de cada requisição e reseta no fim; RequestIdLogFilter
injeta esse valor em todo LogRecord emitido durante o processamento, sem
precisar passar request_id explicitamente em cada chamada de log.
"""

from __future__ import annotations

import contextvars
import json
import logging
from datetime import UTC, datetime

from app.config import settings

request_id_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id", default=None
)

# Atributos padrão de um LogRecord (ver documentação de logging.LogRecord) —
# usados pra distinguir "campos extra" (passados via extra={...}) do resto
# do record ao montar o JSON de saída.
_RESERVED_LOG_RECORD_ATTRS = {
    "name",
    "msg",
    "args",
    "levelname",
    "levelno",
    "pathname",
    "filename",
    "module",
    "exc_info",
    "exc_text",
    "stack_info",
    "lineno",
    "funcName",
    "created",
    "msecs",
    "relativeCreated",
    "thread",
    "threadName",
    "processName",
    "process",
    "message",
    "request_id",
    "taskName",
}


class RequestIdLogFilter(logging.Filter):
    """Injeta record.request_id a partir da ContextVar da requisição em
    andamento ("-" fora de uma requisição, ex.: logs de startup)."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get() or "-"
        return True


class JsonFormatter(logging.Formatter):
    """Serializa cada LogRecord como uma linha JSON: timestamp, level,
    logger, message, request_id, + qualquer campo extra passado via
    logger.info(msg, extra={...})."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }

        for key, value in record.__dict__.items():
            if key not in _RESERVED_LOG_RECORD_ATTRS and key not in payload:
                payload[key] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)


_configured_handler: logging.Handler | None = None


def configure_logging(level: str | None = None) -> None:
    """Configura o root logger com um StreamHandler (stdout) usando
    JsonFormatter + RequestIdLogFilter, no nível de `level` (ou
    settings.LOG_LEVEL se omitido). Chamada uma única vez, no import de
    app.main — segura de chamar mais de uma vez (não duplica handler,
    substitui o handler anterior instalado por ela mesma)."""
    global _configured_handler

    root_logger = logging.getLogger()
    if _configured_handler is not None:
        root_logger.removeHandler(_configured_handler)

    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RequestIdLogFilter())
    root_logger.addHandler(handler)
    _configured_handler = handler

    resolved_level = (level or settings.LOG_LEVEL).upper()
    numeric_level = getattr(logging, resolved_level, None)
    if not isinstance(numeric_level, int):
        logging.getLogger(__name__).warning(
            "invalid_log_level_falling_back_to_info",
            extra={"invalid_level": resolved_level},
        )
        numeric_level = logging.INFO
    root_logger.setLevel(numeric_level)
