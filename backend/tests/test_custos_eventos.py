"""Testes de app.custos.eventos — integração real contra o Postgres (a
migração 009 já semeia custo_evento com placeholders em 0)."""

import uuid

import pytest

from app.custos.eventos import (
    CustoNaoConfiguradoError,
    registrar_classificacao_ticket,
    registrar_enriquecimento_chamada,
    registrar_ingestao_linha,
)
from app.domain.db import SessionLocal
from app.domain.models import CustoEvento, Organizacao


def _nova_organizacao(session):
    # organizacao.nome é UNIQUE (migração 010) — sufixo único por chamada,
    # já que esta função é chamada várias vezes na mesma execução (ver
    # issue #26).
    org = Organizacao(nome=f"Custos Test Org {uuid.uuid4().hex[:8]}")
    session.add(org)
    session.flush()
    return org.id


def test_registrar_ingestao_linha_usa_custo_configurado():
    with SessionLocal() as session:
        org_id = _nova_organizacao(session)
        session.merge(CustoEvento(tipo_evento="ingestao_linha", custo_unidade_centavos=5))
        session.flush()

        evento = registrar_ingestao_linha(
            session, organizacao_id=org_id, quantidade=10, referencia_id=999
        )

        assert evento.quantidade == 10
        assert evento.custo_unitario_centavos == 5
        assert evento.custo_centavos == 50
        assert evento.relatorio_custo_id is None


def test_registrar_classificacao_ticket_usa_custo_configurado():
    with SessionLocal() as session:
        org_id = _nova_organizacao(session)
        session.merge(
            CustoEvento(tipo_evento="classificacao_ticket", custo_unidade_centavos=3)
        )
        session.flush()

        evento = registrar_classificacao_ticket(
            session, organizacao_id=org_id, quantidade=7, referencia_id=1
        )

        assert evento.custo_centavos == 21


def test_registrar_enriquecimento_chamada_soma_por_token_arredondando_pra_cima():
    with SessionLocal() as session:
        org_id = _nova_organizacao(session)
        session.merge(
            CustoEvento(
                tipo_evento="enriquecimento_chamada",
                custo_mil_tokens_entrada_centavos=100,
                custo_mil_tokens_saida_centavos=200,
            )
        )
        session.flush()

        # 150 tokens de entrada -> 150/1000*100 = 15 centavos (exato)
        # 10 tokens de saida -> 10/1000*200 = 2 centavos (exato)
        evento = registrar_enriquecimento_chamada(
            session,
            organizacao_id=org_id,
            tokens_entrada=150,
            tokens_saida=10,
            referencia_id=42,
        )

        assert evento.quantidade == 1
        assert evento.custo_centavos == 17
        assert evento.custo_unitario_centavos == evento.custo_centavos


def test_registrar_enriquecimento_chamada_com_divisao_nao_exata():
    """Regressão: garantir que o cálculo usa arredondamento inteiro (sem float).

    70 tokens * 100 centavos/1000 tokens = 7.000 centavos (exatamente 7)
    140 tokens * 50 centavos/1000 tokens = 7.000 centavos (exatamente 7)

    Com float (70/1000*100), Python armazena 7.000000000000001, e math.ceil
    retorna 8 — um centavo a mais (bug de métrica financeira). Com inteiro
    (-(-70*100 // 1000)), obtemos 7 (correto)."""
    with SessionLocal() as session:
        org_id = _nova_organizacao(session)
        session.merge(
            CustoEvento(
                tipo_evento="enriquecimento_chamada",
                custo_mil_tokens_entrada_centavos=100,
                custo_mil_tokens_saida_centavos=50,
            )
        )
        session.flush()

        # 70 tokens de entrada → 70*100/1000 = 7 (não 8)
        # 140 tokens de saída → 140*50/1000 = 7 (não 8)
        evento = registrar_enriquecimento_chamada(
            session,
            organizacao_id=org_id,
            tokens_entrada=70,
            tokens_saida=140,
            referencia_id=99,
        )

        assert evento.custo_centavos == 14  # 7 + 7, não 8 + 8 = 16


def test_registrar_sem_custo_configurado_levanta_erro():
    with SessionLocal() as session:
        org_id = _nova_organizacao(session)
        session.query(CustoEvento).filter_by(tipo_evento="ingestao_linha").delete()
        session.flush()

        with pytest.raises(CustoNaoConfiguradoError):
            registrar_ingestao_linha(
                session, organizacao_id=org_id, quantidade=1, referencia_id=1
            )
