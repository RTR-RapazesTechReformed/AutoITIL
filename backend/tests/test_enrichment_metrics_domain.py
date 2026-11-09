"""Testes de app.domain.enrichment_metrics — integração real contra o
Postgres do docker-compose.yml (mesmo padrão de test_upload_history.py)."""

from app.domain.db import SessionLocal
from app.domain.enrichment_metrics import (
    list_enrichment_metrics_history,
    record_enrichment_metric,
)


def test_record_enrichment_metric_inserts_a_row_with_ticket_id():
    with SessionLocal() as session:
        record_enrichment_metric(
            session,
            ticket_id=123,
            duracao_ms=456.7,
            tokens_entrada=30,
            tokens_saida=45,
        )
        session.commit()

        history = list_enrichment_metrics_history(session, limit=1)
        assert history[-1]["ticket_id"] == 123
        assert history[-1]["duracao_ms"] == 456.7
        assert history[-1]["tokens_entrada"] == 30
        assert history[-1]["tokens_saida"] == 45


def test_record_enrichment_metric_accepts_null_ticket_id():
    with SessionLocal() as session:
        record_enrichment_metric(
            session,
            ticket_id=None,
            duracao_ms=100.0,
            tokens_entrada=10,
            tokens_saida=5,
        )
        session.commit()

        history = list_enrichment_metrics_history(session, limit=1)
        assert history[-1]["ticket_id"] is None


def test_list_enrichment_metrics_history_returns_ascending_order():
    with SessionLocal() as session:
        record_enrichment_metric(
            session, ticket_id=1, duracao_ms=100.0, tokens_entrada=10, tokens_saida=5
        )
        record_enrichment_metric(
            session, ticket_id=2, duracao_ms=200.0, tokens_entrada=20, tokens_saida=8
        )

        history = list_enrichment_metrics_history(session, limit=2)
        assert len(history) == 2
        assert history[0]["criado_em"] <= history[1]["criado_em"]
