"""ingestion_funnel.py — funil do pipeline, do upload ao enriquecimento.

Responde "onde o volume some": quantos arquivos entraram, quantas linhas
foram lidas, quantos tickets nasceram, quantos passaram por revisão humana
e quantos foram enriquecidos.

Cada etapa é contada da sua PRÓPRIA tabela, não derivada da anterior — um
upload que falhou na geração de tickets some entre `arquivos` e `tickets`,
e é justamente essa diferença que o funil existe para mostrar.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.models import (
    Arquivo,
    HistoricoUpload,
    Registro,
    RevisaoClassificacao,
    Ticket,
)


def compute_ingestion_funnel(session: Session) -> dict:
    uploads = session.scalar(select(func.count(HistoricoUpload.id))) or 0
    uploads_falhos = (
        session.scalar(
            select(func.count(HistoricoUpload.id)).where(
                HistoricoUpload.status == "falhou"
            )
        )
        or 0
    )
    arquivos = session.scalar(select(func.count(Arquivo.id))) or 0
    linhas = session.scalar(select(func.count(Registro.id))) or 0
    tickets = session.scalar(select(func.count(Ticket.id))) or 0
    revisados = session.scalar(
        select(func.count(func.distinct(RevisaoClassificacao.ticket_id)))
    ) or 0
    enriquecidos = (
        session.scalar(
            select(func.count(Ticket.id)).where(
                Ticket.descricao_enriquecida.is_not(None)
            )
        )
        or 0
    )

    etapas = [
        {"etapa": "Uploads", "total": uploads},
        {"etapa": "Arquivos processados", "total": arquivos},
        {"etapa": "Linhas lidas", "total": linhas},
        {"etapa": "Tickets gerados", "total": tickets},
        {"etapa": "Revisados por humano", "total": revisados},
        {"etapa": "Enriquecidos", "total": enriquecidos},
    ]

    # Percentual relativo à PRIMEIRA etapa com volume, não ao topo fixo:
    # "linhas lidas" é ordens de grandeza maior que "uploads", e ancorar
    # tudo em uploads faria as barras finais sumirem visualmente.
    base = linhas or tickets or uploads or 0
    for e in etapas:
        e["percentual_da_base"] = round(e["total"] / base, 4) if base else None

    return {
        "etapas": etapas,
        "base": base,
        "uploads_falhos": uploads_falhos,
        "taxa_revisao": round(revisados / tickets, 4) if tickets else None,
        "taxa_enriquecimento": round(enriquecidos / tickets, 4) if tickets else None,
    }
