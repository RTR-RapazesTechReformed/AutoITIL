"""relatorios.py — fechamento e consulta de relatório de custo por
organização e período. Dashboard interna de gasto (tokens/eventos), não
cobrança de cliente.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.models import EventoCusto, RelatorioCusto, RelatorioCustoItem

# Fuso de negócio pra limites de período — sem isso, comparar DATE com
# evento_custo.criado_em (timestamptz) usa o fuso da SESSÃO do Postgres
# (UTC no Docker), e eventos entre 21h-24h BRT no último dia do mês caem no
# mês seguinte (ver issue #21).
_TZ_NEGOCIO = ZoneInfo("America/Sao_Paulo")


class PeriodoJaFechadoError(RuntimeError):
    """Já existe relatório de custo fechado pra essa organização+período —
    uq_relatorio_custo_periodo_org impede duplicar."""


def _inicio_do_dia(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, tzinfo=_TZ_NEGOCIO)


def _itens_de(session: Session, relatorio_custo_id: int) -> list[RelatorioCustoItem]:
    return list(
        session.scalars(
            select(RelatorioCustoItem).where(
                RelatorioCustoItem.relatorio_custo_id == relatorio_custo_id
            )
        )
    )


def _relatorio_para_dict(relatorio: RelatorioCusto, itens: list[RelatorioCustoItem]) -> dict:
    return {
        "id": relatorio.id,
        "organizacao_id": relatorio.organizacao_id,
        "periodo_inicio": relatorio.periodo_inicio.isoformat(),
        "periodo_fim": relatorio.periodo_fim.isoformat(),
        "status": relatorio.status,
        "total_centavos": relatorio.total_centavos,
        "criado_em": relatorio.criado_em.isoformat() if relatorio.criado_em else None,
        "fechado_em": relatorio.fechado_em.isoformat() if relatorio.fechado_em else None,
        "itens": [
            {
                "tipo_evento": item.tipo_evento,
                "quantidade_total": item.quantidade_total,
                "custo_total_centavos": item.custo_total_centavos,
            }
            for item in itens
        ],
    }


def _agregar_nao_processados(
    session: Session, *, organizacao_id: int, periodo_inicio: date | None, periodo_fim: date | None
):
    condicoes = [
        EventoCusto.organizacao_id == organizacao_id,
        EventoCusto.relatorio_custo_id.is_(None),
    ]
    if periodo_inicio is not None:
        condicoes.append(EventoCusto.criado_em >= _inicio_do_dia(periodo_inicio))
    if periodo_fim is not None:
        condicoes.append(EventoCusto.criado_em < _inicio_do_dia(periodo_fim))
    return session.execute(
        select(
            EventoCusto.tipo_evento,
            func.sum(EventoCusto.quantidade),
            func.sum(EventoCusto.custo_centavos),
        )
        .where(*condicoes)
        .group_by(EventoCusto.tipo_evento)
    ).all()


def _agregar_por_relatorio(session: Session, *, relatorio_custo_id: int):
    return session.execute(
        select(
            EventoCusto.tipo_evento,
            func.sum(EventoCusto.quantidade),
            func.sum(EventoCusto.custo_centavos),
        )
        .where(EventoCusto.relatorio_custo_id == relatorio_custo_id)
        .group_by(EventoCusto.tipo_evento)
    ).all()


def fechar_periodo(
    session: Session, *, organizacao_id: int, periodo_inicio: date, periodo_fim: date
) -> dict:
    relatorio = RelatorioCusto(
        organizacao_id=organizacao_id,
        periodo_inicio=periodo_inicio,
        periodo_fim=periodo_fim,
        status="fechada",
        total_centavos=0,
        fechado_em=datetime.now(UTC),
    )
    session.add(relatorio)
    try:
        session.flush()  # dispara uq_relatorio_custo_periodo_org se já existir
    except IntegrityError as exc:
        session.rollback()
        constraint = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
        if constraint != "uq_relatorio_custo_periodo_org":
            # Outra violação (ex.: ck_relatorio_custo_periodo, se um chamador
            # algum dia contornar a validação do Pydantic) não é "já existe
            # relatório" — não mascara o erro real atrás de um 409 enganoso.
            raise
        raise PeriodoJaFechadoError(
            f"Já existe relatório de custo para organização {organizacao_id} no "
            f"período {periodo_inicio}–{periodo_fim}."
        ) from exc

    # Primeiro reivindica (tag) exatamente os eventos que existem agora —
    # qualquer evento commitado concorrentemente depois deste UPDATE fica de
    # fora, e nunca é contado sem estar também taggeado (nem vice-versa).
    session.execute(
        update(EventoCusto)
        .where(
            EventoCusto.organizacao_id == organizacao_id,
            EventoCusto.relatorio_custo_id.is_(None),
            EventoCusto.criado_em >= _inicio_do_dia(periodo_inicio),
            EventoCusto.criado_em < _inicio_do_dia(periodo_fim),
        )
        .values(relatorio_custo_id=relatorio.id)
    )

    # Agora agrega exatamente o conjunto que o UPDATE acabou de taggear.
    agregados = _agregar_por_relatorio(session, relatorio_custo_id=relatorio.id)

    relatorio.total_centavos = sum(int(valor) for _, _, valor in agregados)

    for tipo_evento, quantidade, valor in agregados:
        session.add(
            RelatorioCustoItem(
                relatorio_custo_id=relatorio.id,
                tipo_evento=tipo_evento,
                quantidade_total=int(quantidade),
                custo_total_centavos=int(valor),
            )
        )

    session.flush()

    return _relatorio_para_dict(relatorio, _itens_de(session, relatorio.id))


def preview_periodo_aberto(session: Session, *, organizacao_id: int) -> dict:
    agregados = _agregar_nao_processados(
        session, organizacao_id=organizacao_id, periodo_inicio=None, periodo_fim=None
    )
    itens = [
        {"tipo_evento": tipo, "quantidade_total": int(qtd), "custo_total_centavos": int(valor)}
        for tipo, qtd, valor in agregados
    ]
    return {
        "itens": itens,
        "total_centavos": sum(item["custo_total_centavos"] for item in itens),
    }


def listar_relatorios_custo(session: Session, *, organizacao_id: int) -> list[dict]:
    relatorios = session.scalars(
        select(RelatorioCusto)
        .where(RelatorioCusto.organizacao_id == organizacao_id)
        .order_by(RelatorioCusto.periodo_inicio.desc())
    ).all()
    return [
        {
            "id": r.id,
            "periodo_inicio": r.periodo_inicio.isoformat(),
            "periodo_fim": r.periodo_fim.isoformat(),
            "status": r.status,
            "total_centavos": r.total_centavos,
        }
        for r in relatorios
    ]


def detalhar_relatorio_custo(
    session: Session, *, organizacao_id: int, relatorio_custo_id: int
) -> dict | None:
    relatorio = session.get(RelatorioCusto, relatorio_custo_id)
    if relatorio is None or relatorio.organizacao_id != organizacao_id:
        return None
    return _relatorio_para_dict(relatorio, _itens_de(session, relatorio_custo_id))
