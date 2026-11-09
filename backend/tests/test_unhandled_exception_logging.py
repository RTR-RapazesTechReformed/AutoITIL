"""Testa que uma exceção não tratada em qualquer rota é logada (ERROR, com
traceback) antes do FastAPI devolver 500 — hoje isso não deixa nenhum
rastro no log."""

import logging

from fastapi.testclient import TestClient

from app.main import app
from tests.auth_helpers import AUTH_HEADERS


def test_unhandled_exception_is_logged_and_returns_500(caplog):
    @app.get("/api/__test_only_boom__")
    async def _boom():
        raise RuntimeError("erro proposital de teste")

    client = TestClient(
        app, headers=AUTH_HEADERS, raise_server_exceptions=False
    )

    with caplog.at_level(logging.ERROR):
        response = client.get("/api/__test_only_boom__")

    assert response.status_code == 500
    error_records = [r for r in caplog.records if r.levelname == "ERROR"]
    assert len(error_records) == 1
    assert error_records[0].getMessage() == "unhandled_exception"
    assert error_records[0].exc_info is not None


def test_unhandled_exception_response_and_log_carry_request_id(caplog):
    @app.get("/api/__test_only_boom_2__")
    async def _boom2():
        raise RuntimeError("erro proposital de teste 2")

    client = TestClient(
        app, headers=AUTH_HEADERS, raise_server_exceptions=False
    )

    with caplog.at_level(logging.ERROR):
        response = client.get("/api/__test_only_boom_2__")

    request_id = response.headers.get("X-Request-ID")
    assert request_id
    assert request_id != "-"

    error_records = [
        r
        for r in caplog.records
        if r.levelname == "ERROR" and r.getMessage() == "unhandled_exception"
    ]
    assert len(error_records) == 1
    assert error_records[0].request_id == request_id
