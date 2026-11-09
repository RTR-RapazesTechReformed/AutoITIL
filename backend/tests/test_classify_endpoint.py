"""Teste do endpoint POST /api/classify."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from tests.auth_helpers import AUTH_HEADERS

client = TestClient(app, headers=AUTH_HEADERS)


def test_classify_returns_cascade_result():
    fake_result = {
        "nivel1": "Incidente",
        "nivel2": "Rede",
        "confianca_n1": 0.92,
        "confianca_n2": 0.88,
    }
    with patch("app.api.routes._cascade") as mock_cascade:
        mock_cascade.is_available.return_value = True
        mock_cascade.classify.return_value = fake_result

        response = client.post("/api/classify", json={"texto": "vpn caiu"})

    assert response.status_code == 200
    assert response.json() == fake_result


def test_classify_returns_503_when_no_model_available():
    with patch("app.api.routes._cascade") as mock_cascade:
        mock_cascade.is_available.return_value = False

        response = client.post("/api/classify", json={"texto": "vpn caiu"})

    assert response.status_code == 503
    assert "indisponível" in response.json()["detail"].lower()


def test_classify_rejects_empty_text():
    response = client.post("/api/classify", json={"texto": ""})
    assert response.status_code == 422
