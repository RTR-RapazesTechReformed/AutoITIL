"""enrichment_feedback.py — agregado do feedback humano (👍/👎) sobre
descrições enriquecidas geradas pelo Gemma 3.

"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.models import FeedbackEnriquecimento, Ticket


def compute_feedback_summary(session: Session) -> dict:
    total_enriquecidos = (
        session.scalar(
            select(func.count(Ticket.id)).where(Ticket.descricao_enriquecida.is_not(None))
        )
        or 0
    )

    positivos = (
        session.scalar(
            select(func.count(FeedbackEnriquecimento.id)).where(
                FeedbackEnriquecimento.valor == "up"
            )
        )
        or 0
    )
    negativos = (
        session.scalar(
            select(func.count(FeedbackEnriquecimento.id)).where(
                FeedbackEnriquecimento.valor == "down"
            )
        )
        or 0
    )
    total_votados = positivos + negativos

    percentual_positivo = positivos / total_votados if total_votados > 0 else None

    return {
        "total_enriquecidos": total_enriquecidos,
        "total_votados": total_votados,
        "positivos": positivos,
        "negativos": negativos,
        "percentual_positivo": percentual_positivo,
    }
