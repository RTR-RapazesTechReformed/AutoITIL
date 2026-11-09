"""queries.py — leitura paginada/filtrada de tickets persistidos (F1-2).

Contrato de resposta documentado em docs/api-contract.md (GET /api/tickets).
"""

from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.models import (
    AreaResponsavel,
    Classificacao,
    FeedbackEnriquecimento,
    LimiarConfianca,
    Prioridade,
    Registro,
    StatusTicket,
    TextoProcessado,
    Ticket,
    TicketStatusHistorico,
    TipoItil,
)


def _parse_enriquecimento(raw: str | None) -> dict[str, str | list[str] | None] | None:
    """Converte o valor bruto de ticket.descricao_enriquecida (TEXT, guarda
    JSON serializado — ver save_enriched_description) pro formato
    estruturado esperado pela API (F2-4 redesign).

    Tolera dado legado: tickets enriquecidos antes desse redesign têm uma
    frase simples ali, não JSON — nesse caso, vira só o campo `objetivo`
    preenchido (mesmo texto de antes), sem perder o dado."""
    if raw is None:
        return None
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict) and "objetivo" in parsed:
            requisicoes = parsed.get("requisicoes")
            if isinstance(requisicoes, str):
                parsed["requisicoes"] = [requisicoes]
            return parsed
    except (json.JSONDecodeError, TypeError):
        pass
    return {"objetivo": raw, "requisicoes": None, "cargo_recomendado": None}


MAX_PAGE_SIZE = 100


def _base_query():
    return (
        select(
            Ticket.id,
            Ticket.codigo,
            Ticket.titulo_sugerido,
            Ticket.descricao_enriquecida,
            TipoItil.nome.label("tipo_itil"),
            AreaResponsavel.nome.label("area_responsavel"),
            Prioridade.codigo.label("prioridade"),
            StatusTicket.codigo.label("status"),
            Classificacao.confianca_n1,
            Classificacao.confianca_n2,
            Ticket.data_geracao,
            Ticket.atualizado_em,
            FeedbackEnriquecimento.valor.label("feedback_enriquecimento"),
        )
        .join(Classificacao, Classificacao.id == Ticket.classificacao_id)
        .join(TipoItil, TipoItil.id == Classificacao.tipo_itil_id)
        .outerjoin(AreaResponsavel, AreaResponsavel.id == Classificacao.area_id)
        .join(Prioridade, Prioridade.id == Ticket.prioridade_id)
        .join(StatusTicket, StatusTicket.id == Ticket.status_id)
        .outerjoin(FeedbackEnriquecimento, FeedbackEnriquecimento.ticket_id == Ticket.id)
    )


def valid_status_codes(session: Session) -> list[str]:
    return list(
        session.scalars(select(StatusTicket.codigo).order_by(StatusTicket.ordem))
    )


def update_ticket_status(session: Session, ticket_id: int, status: str) -> dict | None:
    """Move o ticket pra uma nova coluna do Kanban (transição livre entre
    quaisquer das 5 colunas — sem máquina de estados restrita). Retorna
    None se o ticket não existe; o chamador decide o 404.

    A validação de que `status` é um código válido é responsabilidade do
    chamador (ver valid_status_codes) — esta função assume que já foi
    validado."""
    ticket = session.get(Ticket, ticket_id)
    if ticket is None:
        return None

    status_id = session.scalar(
        select(StatusTicket.id).where(StatusTicket.codigo == status)
    )
    ticket.status_id = status_id
    session.flush()
    # atualizado_em é setado pelo trigger BEFORE UPDATE no Postgres (schema
    # v4+), não pelo ORM — precisa recarregar pra pegar o valor real.
    session.refresh(ticket)

    return {
        "id": ticket.id,
        "codigo": ticket.codigo,
        "status": status,
        "atualizado_em": ticket.atualizado_em.isoformat(),
    }


def _apply_filters(query, *, area, prioridade, status, busca):
    if area:
        query = query.where(AreaResponsavel.nome == area)
    if prioridade:
        query = query.where(Prioridade.codigo == prioridade)
    if status:
        query = query.where(StatusTicket.codigo == status)
    if busca:
        padrao = f"%{busca}%"
        query = query.where(
            Ticket.codigo.ilike(padrao) | Ticket.titulo_sugerido.ilike(padrao)
        )
    return query


def _row_to_dict(row) -> dict:
    return {
        "id": row.id,
        "codigo": row.codigo,
        "titulo_sugerido": row.titulo_sugerido,
        "descricao_enriquecida": _parse_enriquecimento(row.descricao_enriquecida),
        "tipo_itil": row.tipo_itil,
        "area_responsavel": row.area_responsavel,
        "prioridade": row.prioridade,
        "status": row.status,
        "confianca_n1": float(row.confianca_n1)
        if row.confianca_n1 is not None
        else None,
        "confianca_n2": float(row.confianca_n2)
        if row.confianca_n2 is not None
        else None,
        "data_geracao": row.data_geracao.isoformat() if row.data_geracao else None,
        "atualizado_em": row.atualizado_em.isoformat() if row.atualizado_em else None,
        "feedback_enriquecimento": row.feedback_enriquecimento,
    }


def list_tickets(
    session: Session,
    *,
    page: int,
    page_size: int,
    area: str | None = None,
    prioridade: str | None = None,
    status: str | None = None,
    busca: str | None = None,
) -> dict:
    query = _apply_filters(
        _base_query(), area=area, prioridade=prioridade, status=status, busca=busca
    )

    total = session.scalar(
        select(func.count()).select_from(query.order_by(None).subquery())
    )

    rows = session.execute(
        query.order_by(Ticket.data_geracao.desc(), Ticket.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    items = [_row_to_dict(row) for row in rows]

    total_pages = (total + page_size - 1) // page_size if total else 0

    return {
        "items": items,
        "meta": {
            "page": page,
            "page_size": page_size,
            "total": total or 0,
            "total_pages": total_pages,
        },
    }


def export_tickets_rows(
    session: Session,
    *,
    area: str | None = None,
    prioridade: str | None = None,
    status: str | None = None,
    busca: str | None = None,
) -> list[dict]:
    """Retorna TODOS os tickets que casam com os filtros, sem paginação —
    usado pela exportação (GET /api/tickets/export), que precisa da base
    inteira, não de uma página."""
    query = _apply_filters(
        _base_query(), area=area, prioridade=prioridade, status=status, busca=busca
    )
    rows = session.execute(
        query.order_by(Ticket.data_geracao.desc(), Ticket.id.desc())
    ).all()
    return [_row_to_dict(row) for row in rows]


def get_ticket_for_enrichment(session: Session, ticket_id: int) -> dict | None:
    """F2-4 — busca o necessário para enriquecer a descrição de um ticket:
    a descrição original (que só existe lá na cadeia
    ticket -> classificacao -> texto_processado -> registro, o ticket em si
    não guarda o texto bruto) e o cache já existente em
    ticket.descricao_enriquecida, se houver. Retorna None se o ticket não
    existe (o chamador decide o 404)."""
    row = session.execute(
        select(Registro.descricao_original, Ticket.descricao_enriquecida)
        .select_from(Ticket)
        .join(Classificacao, Classificacao.id == Ticket.classificacao_id)
        .join(TextoProcessado, TextoProcessado.id == Classificacao.texto_processado_id)
        .join(Registro, Registro.id == TextoProcessado.registro_id)
        .where(Ticket.id == ticket_id)
    ).first()

    if row is None:
        return None

    return {
        "descricao_original": row.descricao_original,
        "descricao_enriquecida": _parse_enriquecimento(row.descricao_enriquecida),
    }


def save_enriched_description(
    session: Session, ticket_id: int, descricao_enriquecida: dict[str, str | list[str]]
) -> dict:
    """F2-4 — grava o resultado estruturado do enriquecimento em cache (nunca
    recalculado automaticamente depois). Serializa como JSON na mesma
    coluna TEXT (sem migração de schema — ver _parse_enriquecimento pro lado
    da leitura). Assume que o ticket existe (chamador já validou via
    get_ticket_for_enrichment)."""
    ticket = session.get(Ticket, ticket_id)
    ticket.descricao_enriquecida = json.dumps(descricao_enriquecida, ensure_ascii=False)
    session.flush()

    return {
        "id": ticket.id,
        "codigo": ticket.codigo,
        "descricao_enriquecida": descricao_enriquecida,
    }


def _average_time_per_status(session: Session) -> list[dict]:
    """Tempo médio (em horas) que os tickets passam em cada coluna do
    Kanban, a partir de ticket_status_historico. Só conta transições
    COMPLETAS — um ticket que nunca saiu de uma coluna (é a linha mais
    recente daquele ticket) não contribui pra média daquela coluna; não há
    estimativa de tempo parcial."""
    rows = session.execute(
        select(
            TicketStatusHistorico.ticket_id,
            TicketStatusHistorico.status_id,
            TicketStatusHistorico.data_transicao,
        ).order_by(
            TicketStatusHistorico.ticket_id, TicketStatusHistorico.data_transicao
        )
    ).all()

    by_ticket: dict[int, list[tuple[int, datetime]]] = {}
    for ticket_id, status_id, data_transicao in rows:
        by_ticket.setdefault(ticket_id, []).append((status_id, data_transicao))

    durations_by_status: dict[int, list[float]] = {}
    for transitions in by_ticket.values():
        for (status_id, inicio), (_, fim) in zip(
            transitions, transitions[1:], strict=False
        ):
            horas = (fim - inicio).total_seconds() / 3600
            durations_by_status.setdefault(status_id, []).append(horas)

    if not durations_by_status:
        return []

    status_rows = session.execute(
        select(StatusTicket.id, StatusTicket.codigo, StatusTicket.descricao)
        .where(StatusTicket.id.in_(durations_by_status.keys()))
        .order_by(StatusTicket.ordem)
    ).all()

    return [
        {
            "status": codigo,
            "descricao": descricao,
            "media_horas": round(
                sum(durations_by_status[status_id])
                / len(durations_by_status[status_id]),
                2,
            ),
        }
        for status_id, codigo, descricao in status_rows
    ]


def _pivotar_por_dia(rows) -> list[dict]:
    """Converte linhas (dia, categoria, total) numa lista pivotada no
    formato largo: uma chave por categoria, uma linha por dia — formato
    que um gráfico de linha multi-série (frontend) espera diretamente."""
    por_dia: dict[str, dict[str, int]] = {}
    for dia, categoria, total in rows:
        chave_dia = dia.date().isoformat()
        por_dia.setdefault(chave_dia, {})[categoria] = total
    return [{"data": dia, **categorias} for dia, categorias in sorted(por_dia.items())]


def _volume_diario_por_area(session: Session) -> list[dict]:
    # Reutiliza o mesmo objeto de expressão nas 3 cláusulas — chamar
    # func.date_trunc(...) de novo em cada uma gera bind params distintos
    # e o Postgres rejeita o GROUP BY (GroupingError) mesmo com o SQL
    # textualmente idêntico.
    dia = func.date_trunc("day", Ticket.data_geracao)
    rows = session.execute(
        select(
            dia,
            AreaResponsavel.nome,
            func.count(Ticket.id),
        )
        .select_from(Ticket)
        .join(Classificacao, Classificacao.id == Ticket.classificacao_id)
        .join(AreaResponsavel, AreaResponsavel.id == Classificacao.area_id)
        .group_by(dia, AreaResponsavel.nome)
        .order_by(dia)
    ).all()
    return _pivotar_por_dia(rows)


def _volume_diario_por_prioridade(session: Session) -> list[dict]:
    dia = func.date_trunc("day", Ticket.data_geracao)
    rows = session.execute(
        select(
            dia,
            Prioridade.codigo,
            func.count(Ticket.id),
        )
        .select_from(Ticket)
        .join(Prioridade, Prioridade.id == Ticket.prioridade_id)
        .group_by(dia, Prioridade.codigo)
        .order_by(dia)
    ).all()
    return _pivotar_por_dia(rows)


def _taxa_enriquecimento(session: Session) -> dict:
    total = session.scalar(select(func.count(Ticket.id))) or 0
    enriquecidos = (
        session.scalar(
            select(func.count(Ticket.id)).where(
                Ticket.descricao_enriquecida.is_not(None)
            )
        )
        or 0
    )
    percentual = round((enriquecidos / total) * 100, 1) if total > 0 else 0
    return {"enriquecidos": enriquecidos, "total": total, "percentual": percentual}


def tipo_area_heatmap(session: Session) -> dict:
    """Grade tipo ITIL (Nível 1) x área responsável (Nível 2), com volume e
    confiança média do Nível 2 em cada célula.

    Os dois gráficos de barra do dashboard já mostram as marginais — quantos
    chamados por área, quantos por tipo —, mas separados eles escondem o
    cruzamento: 'Incidente em Rede' pode concentrar metade do volume sem que
    nenhuma das duas barras denuncie isso.

    A grade vem densa (todas as combinações do domínio, inclusive as
    zeradas), pelo mesmo motivo da matriz de confusão: uma grade que muda de
    tamanho conforme o dado é ilegível, e célula vazia é informação — se
    nunca apareceu um 'Problema em Aplicações', isso diz algo sobre a base.

    Chamados sem área (Nível 2 não classificado) ficam fora da grade e vão
    no campo `sem_area`, para o total bater com o do dashboard.
    """
    tipos = [
        nome for (nome,) in session.execute(select(TipoItil.nome).order_by(TipoItil.id))
    ]
    areas = [
        nome
        for (nome,) in session.execute(
            select(AreaResponsavel.nome).order_by(AreaResponsavel.id)
        )
    ]

    rows = session.execute(
        select(
            TipoItil.nome,
            AreaResponsavel.nome,
            func.count(Ticket.id),
            func.avg(Classificacao.confianca_n2),
        )
        .select_from(Ticket)
        .join(Classificacao, Classificacao.id == Ticket.classificacao_id)
        .join(TipoItil, TipoItil.id == Classificacao.tipo_itil_id)
        .join(AreaResponsavel, AreaResponsavel.id == Classificacao.area_id)
        .group_by(TipoItil.nome, AreaResponsavel.nome)
    ).all()

    medidos = {
        (tipo, area): (total, confianca) for tipo, area, total, confianca in rows
    }
    celulas = []
    for tipo in tipos:
        for area in areas:
            total, confianca = medidos.get((tipo, area), (0, None))
            celulas.append(
                {
                    "tipo": tipo,
                    "area": area,
                    "total": total,
                    "confianca_media": round(float(confianca), 4)
                    if confianca is not None
                    else None,
                }
            )

    sem_area = (
        session.scalar(
            select(func.count(Ticket.id))
            .select_from(Ticket)
            .join(Classificacao, Classificacao.id == Ticket.classificacao_id)
            .where(Classificacao.area_id.is_(None))
        )
        or 0
    )

    return {
        "tipos": tipos,
        "areas": areas,
        "celulas": celulas,
        "total": sum(c["total"] for c in celulas),
        "sem_area": sem_area,
    }


def get_ticket_by_id(session: Session, ticket_id: int) -> dict | None:
    """Busca um único ticket pelo id, mesmo formato de item de
    list_tickets/GET /api/tickets — usado por
    PATCH /api/tickets/{id}/revisao pra devolver o ticket atualizado sem
    reimplementar a serialização. Retorna None se o ticket não existe."""
    row = session.execute(_base_query().where(Ticket.id == ticket_id)).first()
    if row is None:
        return None
    return _row_to_dict(row)


def dashboard_summary(session: Session) -> dict:
    """Agregações operacionais (F1-5): contagem por área/prioridade,
    confiança média por nível, e contagem de tickets abaixo do limiar de
    confiança ativo (limiar_confianca.ativo)."""
    total_tickets = session.scalar(select(func.count(Ticket.id))) or 0

    por_area_rows = session.execute(
        select(AreaResponsavel.nome, func.count(Ticket.id))
        .join(Classificacao, Classificacao.area_id == AreaResponsavel.id)
        .join(Ticket, Ticket.classificacao_id == Classificacao.id)
        .group_by(AreaResponsavel.nome)
        .order_by(func.count(Ticket.id).desc())
    ).all()

    por_prioridade_rows = session.execute(
        select(Prioridade.codigo, func.count(Ticket.id))
        .join(Ticket, Ticket.prioridade_id == Prioridade.id)
        .group_by(Prioridade.codigo, Prioridade.ordem)
        .order_by(Prioridade.ordem)
    ).all()

    medias = session.execute(
        select(
            func.avg(Classificacao.confianca_n1), func.avg(Classificacao.confianca_n2)
        )
        .select_from(Ticket)
        .join(Classificacao, Classificacao.id == Ticket.classificacao_id)
    ).one()
    media_n1 = round(float(medias[0]), 4) if medias[0] is not None else None
    media_n2 = round(float(medias[1]), 4) if medias[1] is not None else None

    limiar = session.execute(
        select(LimiarConfianca.valor).where(LimiarConfianca.ativo)
    ).scalar_one_or_none()

    abaixo_do_limiar_total = 0
    if limiar is not None:
        abaixo_do_limiar_total = (
            session.scalar(
                select(func.count(Ticket.id))
                .select_from(Ticket)
                .join(Classificacao, Classificacao.id == Ticket.classificacao_id)
                .where(Classificacao.confianca_n1 < limiar)
            )
            or 0
        )

    return {
        "total_tickets": total_tickets,
        "por_area": [{"area": nome, "total": total} for nome, total in por_area_rows],
        "por_prioridade": [
            {"prioridade": codigo, "total": total}
            for codigo, total in por_prioridade_rows
        ],
        "confianca_media": {"nivel1": media_n1, "nivel2": media_n2},
        "abaixo_do_limiar": {
            "limiar_ativo": float(limiar) if limiar is not None else None,
            "total": abaixo_do_limiar_total,
        },
        "tempo_medio_por_coluna": _average_time_per_status(session),
        "volume_diario_por_area": _volume_diario_por_area(session),
        "volume_diario_por_prioridade": _volume_diario_por_prioridade(session),
        "taxa_enriquecimento": _taxa_enriquecimento(session),
    }
