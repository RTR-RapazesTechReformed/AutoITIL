"""persistence.py — grava a cadeia arquivo→registro→texto_processado→
classificacao→ticket no Postgres para tickets gerados a partir de upload.

Toda a gravação de um lote (um arquivo processado) acontece dentro da
sessão passada pelo chamador — quem decide commit/rollback é a rota que
chama esta função (backend/app/api/routes.py), não este módulo.

Fora de escopo (decisão de projeto): ticket.limiar_confianca_id
sempre fica NULL aqui — o roteamento condicional por limiar é F2-1.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from pathlib import Path

from dateutil.parser import parse as parse_date
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.domain.models import (
    AreaResponsavel,
    Arquivo,
    Classificacao,
    Modelo,
    Prioridade,
    Registro,
    StatusTicket,
    TextoProcessado,
    Ticket,
    TipoItil,
)

logger = logging.getLogger(__name__)

_STATUS_TRIAGEM = "triagem"


def _none_if_missing(value):
    """Uma célula vazia de `data`/`responsavel` numa planilha real vira
    NaN (float) depois que o pandas lê o CSV — não None. `valor or None`
    não pega esse caso porque NaN é truthy em Python (só 0, "", None e
    False são falsy), e um NaN cru quebra o INSERT numa coluna DATE com
    `cannot cast type double precision to date` (achado em produção,
    só acontecia em linhas específicas de um upload real, nunca nos
    datasets pequenos e sempre preenchidos dos testes)."""
    if isinstance(value, float) and value != value:  # NaN != NaN é sempre True
        return None
    return value or None


def _coerce_date(value):
    """Converte o valor da coluna `data` para um datetime.date antes do INSERT.

    Sem isso, uma string como "13/01/2026 08:20" (formato brasileiro, comum em
    export de ERP) ia crua para a coluna DATE e o Postgres a interpretava com
    o datestyle do servidor — MDY por padrão — lendo 13 como MÊS:

        DatetimeFieldOverflow: date/time field value out of range: "13/01/2026 08:20"

    Ou seja, o upload inteiro falhava em QUALQUER data com dia > 12, e passava
    despercebido em amostras com datas no começo do mês (achado ingerindo
    sample/P2_TOTVS_Protheus_OS.xlsx).

    dayfirst=True porque o domínio é brasileiro: "04/03/2026" é 4 de março,
    não 3 de abril. O dateutil ainda inverte sozinho quando a leitura
    dia-primeiro é impossível (em "04/20/2024" não existe mês 20), então
    planilhas em formato americano continuam funcionando.

    Data ilegível vira None em vez de derrubar o lote: registro.data_registro
    é nullable, e perder a data de uma linha é muito melhor que perder o
    upload inteiro por causa dela (ver sample/csv_15_data_invalida.csv).
    """
    value = _none_if_missing(value)
    if value is None:
        return None
    # datetime precisa vir antes de date: datetime é subclasse de date, e
    # pandas.Timestamp é subclasse de datetime.
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    texto = str(value).strip()
    if not texto:
        return None
    try:
        return parse_date(texto, dayfirst=True).date()
    except (ValueError, OverflowError, TypeError):
        logger.warning("data_ilegivel_ignorada", extra={"valor_data": texto[:60]})
        return None


def _lookup_id(session: Session, model, **filters) -> int:
    stmt = select(model.id)
    for field, value in filters.items():
        stmt = stmt.where(getattr(model, field) == value)
    result = session.scalars(stmt).first()
    if result is None:
        raise ValueError(f"{model.__tablename__}: nenhum registro com {filters}")
    return result


def _next_ticket_codigo(session: Session) -> str:
    numero = session.execute(
        text("SELECT nextval('autoitil.ticket_codigo_seq')")
    ).scalar_one()
    return f"TCK-{numero:04d}"


def persist_generated_tickets(
    session: Session,
    *,
    file_key: str,
    bucket: str,
    tamanho_bytes: int,
    rows: list[dict],
) -> list[dict]:
    """Retorna, para cada linha de `rows` (mesma ordem), um dict
    `{"id": <ticket.id>, "codigo": <ticket.codigo>}`. O `codigo` vem da
    sequence do banco — é o identificador de negócio real do ticket, e deve
    substituir qualquer `id_ticket` gerado localmente (ex.: por
    generate_ticket()) antes do arquivo de download ser exportado, para que
    o código no CSV/JSON baixado seja o mesmo que aparece no Kanban."""
    key_parts = file_key.split("/")
    # uploads/<hash>/<nome_original>
    content_hash = key_parts[1]
    nome_original = key_parts[2]
    extensao = Path(nome_original).suffix.lower()

    arquivo = Arquivo(
        nome_original=nome_original,
        extensao=extensao,
        hash_conteudo=content_hash,
        tamanho_bytes=tamanho_bytes,
        total_linhas=len(rows),
        storage_backend="s3",
        storage_uri=f"s3://{bucket}/{file_key}",
    )
    session.add(arquivo)
    session.flush()  # popula arquivo.id

    status_triagem_id = _lookup_id(session, StatusTicket, codigo=_STATUS_TRIAGEM)

    created = []

    for row in rows:
        registro = Registro(
            arquivo_id=arquivo.id,
            linha_origem=row["linha_origem"],
            descricao_original=row["descricao_original"],
            data_registro=_coerce_date(row.get("data")),
            responsavel=_none_if_missing(row.get("responsavel")),
        )
        session.add(registro)
        session.flush()

        texto_processado = TextoProcessado(
            registro_id=registro.id,
            descricao_limpa=row["descricao_limpa"],
        )
        session.add(texto_processado)
        session.flush()

        classification = row["classification"]

        tipo_itil_id = _lookup_id(session, TipoItil, nome=classification["nivel1"])
        modelo_n1_id = _lookup_id(
            session,
            Modelo,
            arquitetura=classification["modelo_n1"],
            nivel=1,
            ativo=True,
        )

        area_id = None
        modelo_n2_id = None
        confianca_n2 = classification.get("confianca_n2")
        if classification.get("nivel2") is not None:
            area_id = _lookup_id(
                session, AreaResponsavel, nome=classification["nivel2"]
            )
            modelo_n2_id = _lookup_id(
                session,
                Modelo,
                arquitetura=classification["modelo_n2"],
                nivel=2,
                ativo=True,
            )

        classificacao = Classificacao(
            texto_processado_id=texto_processado.id,
            tipo_itil_id=tipo_itil_id,
            area_id=area_id,
            modelo_n1_id=modelo_n1_id,
            modelo_n2_id=modelo_n2_id,
            confianca_n1=classification["confianca_n1"],
            confianca_n2=confianca_n2,
        )
        session.add(classificacao)
        session.flush()

        prioridade_id = _lookup_id(session, Prioridade, codigo=row["prioridade_codigo"])
        codigo = _next_ticket_codigo(session)

        ticket = Ticket(
            classificacao_id=classificacao.id,
            codigo=codigo,
            titulo_sugerido=row["titulo_sugerido"],
            prioridade_id=prioridade_id,
            status_id=status_triagem_id,
        )
        session.add(ticket)
        session.flush()

        created.append({"id": ticket.id, "codigo": codigo, "arquivo_id": arquivo.id})

    return created
