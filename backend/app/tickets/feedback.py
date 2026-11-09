"""feedback.py — feedback humano (👍/👎) sobre a descrição enriquecida
(Gemma 3) de um ticket. Um voto por ticket, sempre o mais recente — trocar
de 'up' pra 'down' (ou vice-versa) sobrescreve, sem histórico de votos
anteriores e sem opção de remover.

"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.models import FeedbackEnriquecimento, Ticket

VALORES_VALIDOS = ("up", "down")


def record_feedback(session: Session, ticket_id: int, valor: str) -> dict | None:
    """Registra (ou atualiza) o voto de feedback do ticket `ticket_id`.

    Retorna None se o ticket não existe (o chamador decide o 404).
    Levanta ValueError se `valor` não for um dos VALORES_VALIDOS (o
    chamador decide o 422).

    Diferente de record_revisao, não existe um "original" do modelo a
    preservar — feedback é só a opinião humana mais recente, sem y_pred
    associado."""
    if valor not in VALORES_VALIDOS:
        raise ValueError(
            f"valor inválido: {valor!r}. Use um dos: {', '.join(VALORES_VALIDOS)}."
        )

    ticket = session.get(Ticket, ticket_id)
    if ticket is None:
        return None

    feedback = session.scalar(
        select(FeedbackEnriquecimento).where(FeedbackEnriquecimento.ticket_id == ticket_id)
    )

    agora = datetime.now(UTC)
    if feedback is None:
        feedback = FeedbackEnriquecimento(
            ticket_id=ticket_id, valor=valor, criado_em=agora, atualizado_em=agora
        )
        session.add(feedback)
    else:
        feedback.valor = valor
        feedback.atualizado_em = agora

    session.flush()
    return {"ticket_id": ticket_id, "valor": valor}
