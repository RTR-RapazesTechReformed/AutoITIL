"""revisao.py — revisão humana da classificação (Tipo ITIL / Área) de um
ticket já processado. Cada revisão vira rótulo verdadeiro pra acurácia real
(ver backend/app/evaluation/real_accuracy.py) e também corrige o ticket de
verdade (classificacao.tipo_itil_id/.area_id são atualizados in-place).

"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.models import (
    AreaResponsavel,
    Classificacao,
    RevisaoClassificacao,
    Ticket,
    TipoItil,
)

NIVEIS_VALIDOS = ("tipo_itil", "area")


def _resolve_valor_id(session: Session, nivel: str, valor_nome: str) -> int | None:
    if nivel == "tipo_itil":
        return session.scalar(select(TipoItil.id).where(TipoItil.nome == valor_nome))
    return session.scalar(
        select(AreaResponsavel.id).where(AreaResponsavel.nome == valor_nome)
    )


def record_revisao(
    session: Session, ticket_id: int, nivel: str, valor_nome: str
) -> dict | None:
    """Registra uma revisão humana de `nivel` ("tipo_itil" ou "area") pro
    ticket `ticket_id`, com o valor `valor_nome` (nome, não id — mesma
    convenção de `update_ticket_status`).

    Retorna None se o ticket não existe (o chamador decide o 404).
    Levanta ValueError se `valor_nome` não existir na tabela correspondente
    (o chamador decide o 422) — `nivel` já deve ter sido validado como um
    dos NIVEIS_VALIDOS pelo chamador, esta função não revalida isso.

    Regra de negócio central: `*_original_id` só é gravado na PRIMEIRA
    revisão daquele nível (snapshot da predição do modelo no momento em que
    alguém revisa pela primeira vez) — nunca sobrescrito numa 2ª revisão.
    `*_revisado_id`/`*_revisado_em` são sempre atualizados, mesmo quando o
    valor escolhido repete o que já estava — é assim que uma confirmação
    também vira rótulo verdadeiro válido pra acurácia.

    `Classificacao` é 1:1 por ticket (nunca compartilhada entre tickets —
    ver persist_generated_tickets), então mutar in-place é seguro. Nunca
    toca `ticket.prioridade_id` — correção de prioridade está fora de
    escopo desta feature."""
    ticket = session.get(Ticket, ticket_id)
    if ticket is None:
        return None

    valor_id = _resolve_valor_id(session, nivel, valor_nome)
    if valor_id is None:
        raise ValueError(f"valor inválido para nivel {nivel!r}: {valor_nome!r}")

    classificacao = session.get(Classificacao, ticket.classificacao_id)

    revisao = session.scalar(
        select(RevisaoClassificacao).where(RevisaoClassificacao.ticket_id == ticket_id)
    )
    if revisao is None:
        revisao = RevisaoClassificacao(ticket_id=ticket_id)
        session.add(revisao)

    agora = datetime.now(UTC)
    if nivel == "tipo_itil":
        if revisao.tipo_itil_original_id is None:
            revisao.tipo_itil_original_id = classificacao.tipo_itil_id
        revisao.tipo_itil_revisado_id = valor_id
        revisao.tipo_itil_revisado_em = agora
        classificacao.tipo_itil_id = valor_id
    else:
        if revisao.area_original_id is None:
            revisao.area_original_id = classificacao.area_id
        revisao.area_revisado_id = valor_id
        revisao.area_revisado_em = agora
        classificacao.area_id = valor_id

    session.flush()
    return {"ticket_id": ticket_id, "nivel": nivel, "valor": valor_nome}
