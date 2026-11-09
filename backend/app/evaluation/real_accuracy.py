"""real_accuracy.py — acurácia real do classificador, calculada sobre
revisões humanas de tickets já processados em produção (diferente do
holdout de treino, que é o que backend/app/evaluation/metrics.py::
evaluate_model já calculava antes desta feature — aqui só reaproveitamos
a mesma função de cálculo, com y_true/y_pred vindos de
`revisao_classificacao` em vez de um dataset de teste separado).

"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.models import AreaResponsavel, RevisaoClassificacao, Ticket, TipoItil
from app.evaluation.metrics import evaluate_model


def _nivel_tipo_itil(session: Session, total_tickets: int) -> dict:
    rows = session.execute(
        select(
            RevisaoClassificacao.tipo_itil_original_id,
            RevisaoClassificacao.tipo_itil_revisado_id,
        ).where(
            RevisaoClassificacao.tipo_itil_original_id.is_not(None),
            RevisaoClassificacao.tipo_itil_revisado_id.is_not(None),
        )
    ).all()

    if not rows:
        return {"macro_f1": None, "revisados": 0, "total_tickets": total_tickets}

    nomes = dict(session.execute(select(TipoItil.id, TipoItil.nome)).all())
    y_pred = [nomes[original_id] for original_id, _ in rows]
    y_true = [nomes[revisado_id] for _, revisado_id in rows]

    resultado = evaluate_model(y_true, y_pred, level="nivel1", model_name="producao_real")
    return {
        "macro_f1": resultado["macro_f1"],
        "revisados": len(rows),
        "total_tickets": total_tickets,
    }


def _nivel_area(session: Session, total_tickets: int) -> dict:
    rows = session.execute(
        select(
            RevisaoClassificacao.area_original_id,
            RevisaoClassificacao.area_revisado_id,
        ).where(
            RevisaoClassificacao.area_original_id.is_not(None),
            RevisaoClassificacao.area_revisado_id.is_not(None),
        )
    ).all()

    if not rows:
        return {"macro_f1": None, "revisados": 0, "total_tickets": total_tickets}

    nomes = dict(session.execute(select(AreaResponsavel.id, AreaResponsavel.nome)).all())
    y_pred = [nomes[original_id] for original_id, _ in rows]
    y_true = [nomes[revisado_id] for _, revisado_id in rows]

    resultado = evaluate_model(y_true, y_pred, level="nivel2", model_name="producao_real")
    return {
        "macro_f1": resultado["macro_f1"],
        "revisados": len(rows),
        "total_tickets": total_tickets,
    }


def compute_real_accuracy(session: Session) -> dict:
    """Acurácia real por nível, calculada sobre `revisao_classificacao`.
    Ignora linhas onde aquele nível específico ainda não foi revisado
    (original ou revisado NULL) — nem toda linha cobre os dois níveis."""
    total_tickets = session.scalar(select(func.count(Ticket.id))) or 0

    return {
        "nivel1": _nivel_tipo_itil(session, total_tickets),
        "nivel2": _nivel_area(session, total_tickets),
    }
