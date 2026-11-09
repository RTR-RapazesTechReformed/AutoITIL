"""Testes de GET /api/models/performance/system-history — integração real contra o
Postgres do docker-compose.yml."""

from fastapi.testclient import TestClient

from app.domain.db import SessionLocal
from app.domain.system_metrics import record_system_metrics_sample
from app.main import app
from tests.auth_helpers import AUTH_HEADERS

client = TestClient(app, headers=AUTH_HEADERS)


def test_limit_is_clamped_to_at_least_one():
    # limit=0 é clampado pra 1 no handler — não assume o banco vazio (é o
    # Postgres real, persistente, compartilhado entre testes; outros
    # arquivos de teste já inserem linhas em metrica_sistema).
    response = client.get("/api/models/performance/system-history?limit=0")
    assert response.status_code == 200
    assert len(response.json()) <= 1


def test_returns_recorded_samples_in_ascending_order():
    with SessionLocal() as session:
        record_system_metrics_sample(session)
        record_system_metrics_sample(session)

    response = client.get("/api/models/performance/system-history?limit=2")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert body[0]["coletado_em"] <= body[1]["coletado_em"]
    for row in body:
        assert set(row.keys()) == {
            "cpu_percent",
            "memory_rss_mb",
            "memory_percent",
            "uptime_seconds",
            "coletado_em",
        }


def test_limit_is_clamped_to_1000():
    response = client.get("/api/models/performance/system-history?limit=999999")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
