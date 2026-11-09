"""Testes de app.custos.relatorios — integração real contra o Postgres."""

import uuid
from datetime import UTC, date, datetime

import pytest

from app.custos.eventos import registrar_classificacao_ticket, registrar_ingestao_linha
from app.custos.relatorios import (
    PeriodoJaFechadoError,
    detalhar_relatorio_custo,
    fechar_periodo,
    listar_relatorios_custo,
    preview_periodo_aberto,
)
from app.domain.db import SessionLocal
from app.domain.models import CustoEvento, Organizacao

_TIPOS_EVENTO_CUSTOS_TESTE = ("ingestao_linha", "classificacao_ticket")


@pytest.fixture(autouse=True)
def _preservar_custos_evento_globais():
    """`custo_evento` é uma tabela global (uma linha por tipo_evento, não por
    organização). Os testes deste arquivo sobrescrevem os custos de
    `ingestao_linha`/`classificacao_ticket` para poder montar relatórios
    previsíveis — sem isso, eles corromperiam permanentemente os custos reais
    (R$0,00) do Postgres de dev compartilhado, que nunca é resetado entre
    execuções de teste.
    """
    with SessionLocal() as session:
        originais = {
            tipo: session.get(CustoEvento, tipo) for tipo in _TIPOS_EVENTO_CUSTOS_TESTE
        }
        snapshot = {
            tipo: (
                None
                if custo is None
                else {
                    "custo_unidade_centavos": custo.custo_unidade_centavos,
                    "custo_mil_tokens_entrada_centavos": custo.custo_mil_tokens_entrada_centavos,
                    "custo_mil_tokens_saida_centavos": custo.custo_mil_tokens_saida_centavos,
                }
            )
            for tipo, custo in originais.items()
        }

    yield

    with SessionLocal() as session:
        for tipo, valores in snapshot.items():
            if valores is None:
                session.query(CustoEvento).filter_by(tipo_evento=tipo).delete()
            else:
                session.merge(CustoEvento(tipo_evento=tipo, **valores))
        session.commit()


def _organizacao_com_custos(session):
    # organizacao.nome é UNIQUE (migração 010) — sufixo único por chamada,
    # não só por execução da suíte, já que alguns testes chamam esta
    # função mais de uma vez (ver issue #26).
    org = Organizacao(nome=f"Relatorio Custo Test Org {uuid.uuid4().hex[:8]}")
    session.add(org)
    session.flush()
    session.merge(CustoEvento(tipo_evento="ingestao_linha", custo_unidade_centavos=10))
    session.merge(CustoEvento(tipo_evento="classificacao_ticket", custo_unidade_centavos=20))
    session.flush()
    return org.id


def test_fechar_periodo_agrega_por_tipo_evento():
    with SessionLocal() as session:
        org_id = _organizacao_com_custos(session)
        criado_em = datetime(2026, 1, 15, tzinfo=UTC)
        registrar_ingestao_linha(session, organizacao_id=org_id, quantidade=5, referencia_id=1, criado_em=criado_em)
        registrar_classificacao_ticket(session, organizacao_id=org_id, quantidade=5, referencia_id=1, criado_em=criado_em)
        session.commit()

        relatorio = fechar_periodo(
            session,
            organizacao_id=org_id,
            periodo_inicio=date(2026, 1, 1),
            periodo_fim=date(2026, 2, 1),
        )
        session.commit()

    assert relatorio["status"] == "fechada"
    assert relatorio["total_centavos"] == 5 * 10 + 5 * 20
    itens_por_tipo = {item["tipo_evento"]: item for item in relatorio["itens"]}
    assert itens_por_tipo["ingestao_linha"]["quantidade_total"] == 5
    assert itens_por_tipo["ingestao_linha"]["custo_total_centavos"] == 50
    assert itens_por_tipo["classificacao_ticket"]["custo_total_centavos"] == 100


def test_eventos_processados_nao_entram_em_relatorio_seguinte():
    with SessionLocal() as session:
        org_id = _organizacao_com_custos(session)
        criado_em = datetime(2026, 1, 15, tzinfo=UTC)
        registrar_ingestao_linha(session, organizacao_id=org_id, quantidade=1, referencia_id=1, criado_em=criado_em)
        session.commit()

        fechar_periodo(
            session, organizacao_id=org_id, periodo_inicio=date(2026, 1, 1), periodo_fim=date(2026, 2, 1)
        )
        session.commit()

        preview = preview_periodo_aberto(session, organizacao_id=org_id)

    assert preview["total_centavos"] == 0
    assert preview["itens"] == []


def test_fechar_o_mesmo_periodo_duas_vezes_levanta_erro():
    with SessionLocal() as session:
        org_id = _organizacao_com_custos(session)
        criado_em = datetime(2026, 3, 15, tzinfo=UTC)
        registrar_ingestao_linha(session, organizacao_id=org_id, quantidade=1, referencia_id=1, criado_em=criado_em)
        session.commit()

        fechar_periodo(
            session, organizacao_id=org_id, periodo_inicio=date(2026, 3, 1), periodo_fim=date(2026, 4, 1)
        )
        session.commit()

    with SessionLocal() as session:
        criado_em = datetime(2026, 3, 20, tzinfo=UTC)
        registrar_ingestao_linha(session, organizacao_id=org_id, quantidade=1, referencia_id=2, criado_em=criado_em)
        session.commit()

        with pytest.raises(PeriodoJaFechadoError):
            fechar_periodo(
                session, organizacao_id=org_id, periodo_inicio=date(2026, 3, 1), periodo_fim=date(2026, 4, 1)
            )


def test_listar_e_detalhar_relatorio_sao_escopados_por_organizacao():
    with SessionLocal() as session:
        org_a = _organizacao_com_custos(session)
        org_b = _organizacao_com_custos(session)
        criado_em = datetime(2026, 5, 15, tzinfo=UTC)
        registrar_ingestao_linha(session, organizacao_id=org_a, quantidade=1, referencia_id=1, criado_em=criado_em)
        session.commit()

        relatorio_a = fechar_periodo(
            session, organizacao_id=org_a, periodo_inicio=date(2026, 5, 1), periodo_fim=date(2026, 6, 1)
        )
        session.commit()

        relatorios_de_b = listar_relatorios_custo(session, organizacao_id=org_b)
        assert all(r["id"] != relatorio_a["id"] for r in relatorios_de_b)

        assert detalhar_relatorio_custo(session, organizacao_id=org_b, relatorio_custo_id=relatorio_a["id"]) is None
        assert detalhar_relatorio_custo(session, organizacao_id=org_a, relatorio_custo_id=relatorio_a["id"]) is not None
