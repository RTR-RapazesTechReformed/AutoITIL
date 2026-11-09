"""eventos.py — ledger de eventos de custo (tabela evento_custo).

Paralelo às métricas de ops (app.domain.classification_metrics,
app.domain.enrichment_metrics), mas com propósito diferente: aqui é
custo de infraestrutura/LLM por organização, não telemetria de produto —
uma dashboard interna, não cobrança do cliente.
custo_unitario_centavos/custo_centavos são CONGELADOS no momento da
escrita (consulta custo_evento AGORA, grava o resultado já calculado) —
fechar um relatório de período nunca muda de valor se custo_evento for
reajustado depois. E, ao contrário das métricas de ops, uma falha aqui
NÃO deve ser engolida: perder um evento de custo é perder visibilidade
real de gasto, não é aceitável como "best effort".

"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.domain.models import CustoEvento, EventoCusto

TIPO_INGESTAO_LINHA = "ingestao_linha"
TIPO_CLASSIFICACAO_TICKET = "classificacao_ticket"
TIPO_ENRIQUECIMENTO_CHAMADA = "enriquecimento_chamada"


class CustoNaoConfiguradoError(RuntimeError):
    """`custo_evento` não tem linha para o tipo de evento — não tem como
    calcular o custo. Propositalmente não é engolido (ver docstring do
    módulo)."""


def _ceil_div(numerador: int, denominador: int) -> int:
    """Divisão inteira arredondada pra cima, sem passar por float (evita
    imprecisão de ponto flutuante em cálculo de custo)."""
    return -(-numerador // denominador)


def _custo(session: Session, tipo_evento: str) -> CustoEvento:
    custo = session.get(CustoEvento, tipo_evento)
    if custo is None:
        raise CustoNaoConfiguradoError(
            f"custo_evento não tem linha para '{tipo_evento}' — rode a "
            "migração 009 (ou configure o custo manualmente) antes de "
            "gerar eventos de custo desse tipo."
        )
    return custo


def registrar_ingestao_linha(
    session: Session, *, organizacao_id: int, quantidade: int, referencia_id: int, criado_em: datetime | None = None
) -> EventoCusto:
    custo = _custo(session, TIPO_INGESTAO_LINHA)
    evento = EventoCusto(
        organizacao_id=organizacao_id,
        tipo_evento=TIPO_INGESTAO_LINHA,
        quantidade=quantidade,
        referencia_id=referencia_id,
        custo_unitario_centavos=custo.custo_unidade_centavos,
        custo_centavos=custo.custo_unidade_centavos * quantidade,
    )
    if criado_em is not None:
        evento.criado_em = criado_em
    session.add(evento)
    session.flush()
    return evento


def registrar_classificacao_ticket(
    session: Session, *, organizacao_id: int, quantidade: int, referencia_id: int, criado_em: datetime | None = None
) -> EventoCusto:
    custo = _custo(session, TIPO_CLASSIFICACAO_TICKET)
    evento = EventoCusto(
        organizacao_id=organizacao_id,
        tipo_evento=TIPO_CLASSIFICACAO_TICKET,
        quantidade=quantidade,
        referencia_id=referencia_id,
        custo_unitario_centavos=custo.custo_unidade_centavos,
        custo_centavos=custo.custo_unidade_centavos * quantidade,
    )
    if criado_em is not None:
        evento.criado_em = criado_em
    session.add(evento)
    session.flush()
    return evento


def registrar_enriquecimento_chamada(
    session: Session,
    *,
    organizacao_id: int,
    tokens_entrada: int,
    tokens_saida: int,
    referencia_id: int,
    criado_em: datetime | None = None,
) -> EventoCusto:
    """quantidade é sempre 1 — uma chamada de enriquecimento é o evento
    inteiro, não há "lote". Por isso custo_unitario_centavos == custo_centavos
    aqui: com quantidade=1, o "custo por unidade" é o próprio custo total do
    evento (diferente de ingestao_linha/classificacao_ticket, onde
    custo_unitario é multiplicado por quantidade > 1 em geral)."""
    custo = _custo(session, TIPO_ENRIQUECIMENTO_CHAMADA)
    custo_centavos = _ceil_div(
        tokens_entrada * custo.custo_mil_tokens_entrada_centavos, 1000
    ) + _ceil_div(
        tokens_saida * custo.custo_mil_tokens_saida_centavos, 1000
    )
    evento = EventoCusto(
        organizacao_id=organizacao_id,
        tipo_evento=TIPO_ENRIQUECIMENTO_CHAMADA,
        quantidade=1,
        tokens_entrada=tokens_entrada,
        tokens_saida=tokens_saida,
        referencia_id=referencia_id,
        custo_unitario_centavos=custo_centavos,
        custo_centavos=custo_centavos,
    )
    if criado_em is not None:
        evento.criado_em = criado_em
    session.add(evento)
    session.flush()
    return evento
