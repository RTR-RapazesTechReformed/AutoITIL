"""Testes de app.logging_config: formatter JSON, propagação de request_id
via ContextVar, e configuração do root logger."""

import io
import json
import logging

from app.logging_config import (
    JsonFormatter,
    RequestIdLogFilter,
    configure_logging,
    request_id_ctx,
)


def _make_logger():
    """Logger isolado (não propaga pro root) com um handler que escreve
    num StringIO, formatado com JsonFormatter + RequestIdLogFilter — pra
    testar a saída do formatter sem depender do estado do root logger."""
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RequestIdLogFilter())

    logger = logging.getLogger("test.json_formatter")
    logger.handlers = [handler]
    logger.propagate = False
    logger.setLevel(logging.DEBUG)
    return logger, stream


class TestJsonFormatter:
    def test_output_is_valid_json_with_core_fields(self):
        logger, stream = _make_logger()
        logger.info("mensagem de teste")

        payload = json.loads(stream.getvalue())
        assert payload["level"] == "INFO"
        assert payload["logger"] == "test.json_formatter"
        assert payload["message"] == "mensagem de teste"
        assert "timestamp" in payload

    def test_request_id_defaults_to_dash_outside_request(self):
        logger, stream = _make_logger()
        logger.info("sem request em andamento")

        payload = json.loads(stream.getvalue())
        assert payload["request_id"] == "-"

    def test_request_id_comes_from_context_var(self):
        logger, stream = _make_logger()
        token = request_id_ctx.set("abc-123")
        try:
            logger.info("dentro de uma requisicao")
        finally:
            request_id_ctx.reset(token)

        payload = json.loads(stream.getvalue())
        assert payload["request_id"] == "abc-123"

    def test_extra_fields_are_included(self):
        # "uploaded_filename", não "filename" — "filename" já é um atributo
        # reservado de LogRecord (nome do arquivo-fonte da chamada de log);
        # passar extra={"filename": ...} faz o logging levantar KeyError.
        logger, stream = _make_logger()
        logger.info(
            "upload_saved",
            extra={"uploaded_filename": "chamados.csv", "size_bytes": 1024},
        )

        payload = json.loads(stream.getvalue())
        assert payload["uploaded_filename"] == "chamados.csv"
        assert payload["size_bytes"] == 1024

    def test_exception_info_is_included(self):
        logger, stream = _make_logger()
        try:
            raise RuntimeError("erro de teste")
        except RuntimeError:
            logger.exception("falhou")

        payload = json.loads(stream.getvalue())
        assert "RuntimeError" in payload["exception"]
        assert "erro de teste" in payload["exception"]


class TestConfigureLogging:
    def test_default_level_is_info(self):
        configure_logging()
        assert logging.getLogger().level == logging.INFO

    def test_respects_explicit_level(self):
        configure_logging(level="DEBUG")
        assert logging.getLogger().level == logging.DEBUG
        configure_logging(level="INFO")  # restaura o default pros próximos testes

    def test_root_handler_uses_json_formatter(self):
        configure_logging()
        json_handlers = [
            h
            for h in logging.getLogger().handlers
            if isinstance(h.formatter, JsonFormatter)
        ]
        assert len(json_handlers) == 1

    def test_calling_configure_logging_twice_does_not_duplicate_handlers(self):
        configure_logging()
        configure_logging()
        json_handlers = [
            h
            for h in logging.getLogger().handlers
            if isinstance(h.formatter, JsonFormatter)
        ]
        assert len(json_handlers) == 1

    def test_lowercase_level_is_accepted(self):
        configure_logging(level="debug")
        assert logging.getLogger().level == logging.DEBUG
        configure_logging(level="INFO")

    def test_invalid_level_falls_back_to_info_with_warning(self, caplog):
        with caplog.at_level(logging.WARNING):
            configure_logging(level="NOT_A_LEVEL")
        assert logging.getLogger().level == logging.INFO
        warnings = [
            r
            for r in caplog.records
            if r.getMessage() == "invalid_log_level_falling_back_to_info"
        ]
        assert len(warnings) == 1
        configure_logging(level="INFO")
