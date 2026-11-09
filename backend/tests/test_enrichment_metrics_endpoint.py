"""Testes de GET /api/models/performance/enrichment-history — integração real contra o
Postgres do docker-compose.yml."""

from fastapi.testclient import TestClient

from app.domain.db import SessionLocal
from app.domain.enrichment_metrics import record_enrichment_metric
from app.main import app
from tests.auth_helpers import AUTH_HEADERS

client = TestClient(app, headers=AUTH_HEADERS)


def test_limit_is_clamped_to_at_least_one():
    # limit=0 é clampado pra 1 no handler — não assume o banco vazio (é o
    # Postgres real, persistente, compartilhado entre testes; outros
    # arquivos de teste já inserem linhas em metrica_enriquecimento).
    response = client.get("/api/models/performance/enrichment-history?limit=0")
    assert response.status_code == 200
    assert len(response.json()) <= 1


def test_returns_recorded_metrics_in_ascending_order():
    with SessionLocal() as session:
        record_enrichment_metric(
            session, ticket_id=1, duracao_ms=100.0, tokens_entrada=10, tokens_saida=5
        )
        record_enrichment_metric(
            session, ticket_id=2, duracao_ms=200.0, tokens_entrada=20, tokens_saida=8
        )
        session.commit()

    response = client.get("/api/models/performance/enrichment-history?limit=2")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert body[0]["criado_em"] <= body[1]["criado_em"]
    for row in body:
        assert set(row.keys()) == {
            "ticket_id",
            "duracao_ms",
            "tokens_entrada",
            "tokens_saida",
            "criado_em",
        }
