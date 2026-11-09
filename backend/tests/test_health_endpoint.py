"""Teste do endpoint de health check, usado como smoke test do proxy frontend."""

from fastapi.testclient import TestClient

from app.main import app
from tests.auth_helpers import AUTH_HEADERS

client = TestClient(app, headers=AUTH_HEADERS)


def test_health_returns_ok():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
