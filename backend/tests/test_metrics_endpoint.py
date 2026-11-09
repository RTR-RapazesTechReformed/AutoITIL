"""Testes de GET /api/models/quality — expõe metrics_report.json como JSON puro."""

import json

from fastapi.testclient import TestClient

from app.main import app
from tests.auth_helpers import AUTH_HEADERS

client = TestClient(app, headers=AUTH_HEADERS)


def test_returns_metrics_report_content(monkeypatch, tmp_path):
    fake_path = tmp_path / "metrics_report.json"
    report = {
        "generated_at": "2026-08-21T00:00:00+00:00",
        "nivel1": {"bert": {"macro_f1": 0.95}},
        "nivel2": {},
    }
    fake_path.write_text(json.dumps(report), encoding="utf-8")
    monkeypatch.setattr("app.api.routes.METRICS_PATH", fake_path)

    response = client.get("/api/models/quality")
    assert response.status_code == 200
    assert response.json() == report


def test_returns_empty_shape_when_report_missing(monkeypatch, tmp_path):
    fake_path = tmp_path / "metrics_report.json"
    monkeypatch.setattr("app.api.routes.METRICS_PATH", fake_path)

    response = client.get("/api/models/quality")
    assert response.status_code == 200
    assert response.json() == {"nivel1": {}, "nivel2": {}}
