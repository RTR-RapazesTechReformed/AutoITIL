"""Tests for POST /api/tickets/generate."""

import csv
import io
import json
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from tests.auth_helpers import AUTH_HEADERS

client = TestClient(app, headers=AUTH_HEADERS)


def _classification(nivel1="Incidente", nivel2="Rede", c1=0.92, c2=0.88):
    return {
        "nivel1": nivel1,
        "nivel2": nivel2,
        "confianca_n1": c1,
        "confianca_n2": c2,
    }


def _payload(rows=None, format="json"):
    return {
        "rows": rows
        or [
            {"id": "T001", "descricao": "VPN do escritorio caiu"},
            {"id": "T002", "descricao": "Solicito acesso ao ERP"},
        ],
        "format": format,
    }


def test_generate_tickets_json_returns_file():
    with patch("app.api.routes._cascade") as mock_cascade:
        mock_cascade.is_available.return_value = True
        mock_cascade.classify.side_effect = [
            _classification("Incidente", "Rede", 0.92, 0.88),
            _classification("Requisição", "Aplicações", 0.81, 0.77),
        ]

        response = client.post("/api/tickets/generate", json=_payload(format="json"))

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert "attachment" in response.headers["content-disposition"]
    assert response.headers["content-disposition"].endswith('.json"')

    tickets = json.loads(response.content)
    assert len(tickets) == 2
    assert tickets[0]["id_ticket"] == "TCK-0001"
    assert tickets[0]["tipo_itil"] == "Incidente"
    assert tickets[0]["area_responsavel"] == "Rede"
    assert tickets[0]["prioridade"] == "P1"
    assert tickets[1]["id_ticket"] == "TCK-0002"
    assert tickets[1]["tipo_itil"] == "Requisição"


def test_generate_tickets_csv_returns_file():
    with patch("app.api.routes._cascade") as mock_cascade:
        mock_cascade.is_available.return_value = True
        mock_cascade.classify.return_value = _classification()

        response = client.post(
            "/api/tickets/generate",
            json=_payload(rows=[{"id": "T001", "descricao": "VPN caiu"}], format="csv"),
        )

    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    assert response.headers["content-disposition"].endswith('.csv"')

    rows = list(csv.reader(io.StringIO(response.content.decode("utf-8"))))
    assert len(rows) == 2  # header + 1
    assert "id_ticket" in rows[0]


def test_returns_503_when_classifier_unavailable():
    with patch("app.api.routes._cascade") as mock_cascade:
        mock_cascade.is_available.return_value = False

        response = client.post("/api/tickets/generate", json=_payload())

    assert response.status_code == 503


def test_rejects_invalid_format():
    response = client.post("/api/tickets/generate", json={"rows": [], "format": "xml"})
    assert response.status_code == 422


def test_rejects_empty_rows():
    response = client.post("/api/tickets/generate", json={"rows": [], "format": "json"})
    assert response.status_code == 422


def test_rejects_row_missing_descricao():
    response = client.post(
        "/api/tickets/generate",
        json={"rows": [{"id": "T001"}], "format": "json"},
    )
    assert response.status_code == 422
