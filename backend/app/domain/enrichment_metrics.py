"""enrichment_metrics.py — histórico de tempo/tokens de cada chamada
BEM-SUCEDIDA de DescriptionEnricher.enrich() (tabela `metrica_enriquecimento`).

Independente de ticket (sem FK) — ticket_id é só uma referência solta, pra
correlacionar visualmente se quiser, nunca validada contra a tabela ticket."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.models import MetricaEnriquecimento


def record_enrichment_metric(
    session: Session,
    *,
    ticket_id: int | None,
    duracao_ms: float,
    tokens_entrada: int,
    tokens_saida: int,
) -> None:
    session.add(
        MetricaEnriquecimento(
            ticket_id=ticket_id,
            duracao_ms=duracao_ms,
            tokens_entrada=tokens_entrada,
            tokens_saida=tokens_saida,
        )
    )
    session.flush()


def list_enrichment_metrics_history(session: Session, limit: int = 200) -> list[dict]:
    """Devolve as últimas `limit` chamadas, em ordem cronológica ASCENDENTE
    (mais antiga primeiro) — mesma técnica de app.domain.system_metrics
    (busca DESC, inverte em Python)."""
    rows = session.scalars(
        select(MetricaEnriquecimento)
        .order_by(
            MetricaEnriquecimento.criado_em.desc(), MetricaEnriquecimento.id.desc()
        )
        .limit(limit)
    ).all()
    rows = list(reversed(rows))
    return [
        {
            "ticket_id": row.ticket_id,
            "duracao_ms": float(row.duracao_ms),
            "tokens_entrada": row.tokens_entrada,
            "tokens_saida": row.tokens_saida,
            "criado_em": row.criado_em.isoformat(),
        }
        for row in rows
    ]
