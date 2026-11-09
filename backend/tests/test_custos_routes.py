"""Testes de /api/admin/custos/fechar, /api/custos, /api/custos/preview
e /api/custos/{id} — integração real contra o Postgres."""

import uuid
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.auth.security import create_access_token
from app.auth.service import create_user
from app.custos.eventos import registrar_ingestao_linha
from app.domain.db import SessionLocal
from app.domain.models import CustoEvento, Organizacao
from app.main import app
from tests.auth_helpers import AUTH_HEADERS

# Per-run unique suffix to avoid persistent-DB collisions (nunca-resetado project DB).
# Follows project convention from tests/auth_helpers.py.
_RUN = uuid.uuid4().hex[:8]

regular_client = TestClient(app, headers=AUTH_HEADERS)


@pytest.fixture(autouse=True)
def _preservar_custo_ingestao_linha():
    """`custo_evento` é global (uma linha por tipo_evento, não por
    organização) — sobrescrever o custo de `ingestao_linha` para montar
    relatórios de teste previsíveis corromperia o Postgres de dev
    compartilhado (nunca resetado entre execuções) se não for restaurado
    depois."""
    with SessionLocal() as session:
        original = session.get(CustoEvento, "ingestao_linha")
        snapshot = (
            None
            if original is None
            else {
                "custo_unidade_centavos": original.custo_unidade_centavos,
                "custo_mil_tokens_entrada_centavos": original.custo_mil_tokens_entrada_centavos,
                "custo_mil_tokens_saida_centavos": original.custo_mil_tokens_saida_centavos,
            }
        )

    yield

    with SessionLocal() as session:
        if snapshot is None:
            session.query(CustoEvento).filter_by(tipo_evento="ingestao_linha").delete()
        else:
            session.merge(CustoEvento(tipo_evento="ingestao_linha", **snapshot))
        session.commit()


def _garantir_custo_ingestao_linha():
    with SessionLocal() as session:
        session.merge(CustoEvento(tipo_evento="ingestao_linha", custo_unidade_centavos=1))
        session.commit()


def _admin_em_organizacao_propria():
    # Organização e admin dedicados por chamada (não só por run): o Postgres
    # de dev usado nos testes nunca é resetado entre execuções, e fechar um
    # período grande contra a organização compartilhada "Organização Padrão"
    # varreria eventos reais/de outros testes para dentro de um relatório de
    # teste. Cada teste que fecha período ganha sua própria organização,
    # nunca tocada por mais ninguém. Segue o padrão de
    # tests/test_admin_usuarios_organizacao.py::_admin_de_outra_organizacao.
    sufixo = f"{_RUN}-{uuid.uuid4().hex[:8]}"
    with SessionLocal() as session:
        org = Organizacao(nome=f"Custos Routes Test Org {sufixo}")
        session.add(org)
        session.flush()
        usuario = create_user(
            session,
            f"admin-custos-{sufixo}@autoitil.test",
            "senha-correta",
            is_admin=True,
            organizacao_id=org.id,
        )
        org_id = org.id
        session.commit()
        token = create_access_token(usuario)
    client = TestClient(app, headers={"Authorization": f"Bearer {token}"})
    return client, org_id


def test_non_admin_cannot_fechar_periodo():
    response = regular_client.post(
        "/api/admin/custos/fechar",
        json={"periodo_inicio": "2026-01-01", "periodo_fim": "2026-02-01"},
    )
    assert response.status_code == 403


def test_fechar_listar_e_detalhar_relatorio_fluxo_completo():
    _garantir_custo_ingestao_linha()
    admin_client, org_id = _admin_em_organizacao_propria()

    with SessionLocal() as session:
        registrar_ingestao_linha(session, organizacao_id=org_id, quantidade=3, referencia_id=1)
        session.commit()

    # Generate unique period per run to avoid persistent-DB collisions.
    # Use full _RUN (32-bit hex) to derive day-level offset over large range (0-9999 days).
    # This provides ~10k distinct periods; collision probability << birthday-bound flakiness.
    # Ensure period contains today (when registrar_ingestao_linha writes events).
    today = date.today()
    run_offset_days = int(_RUN, 16) % 10000  # 0-9999: full-width entropy from _RUN
    periodo_inicio = (today - timedelta(days=5000 + run_offset_days)).isoformat()
    periodo_fim = (today + timedelta(days=5000)).isoformat()

    fechar_response = admin_client.post(
        "/api/admin/custos/fechar",
        json={"periodo_inicio": periodo_inicio, "periodo_fim": periodo_fim},
    )
    assert fechar_response.status_code == 201
    relatorio_id = fechar_response.json()["data"]["id"]

    listar_response = admin_client.get("/api/custos")
    assert listar_response.status_code == 200
    assert any(r["id"] == relatorio_id for r in listar_response.json()["data"])

    detalhe_response = admin_client.get(f"/api/custos/{relatorio_id}")
    assert detalhe_response.status_code == 200
    assert detalhe_response.json()["data"]["id"] == relatorio_id

    fechar_de_novo = admin_client.post(
        "/api/admin/custos/fechar",
        json={"periodo_inicio": periodo_inicio, "periodo_fim": periodo_fim},
    )
    assert fechar_de_novo.status_code == 409


def test_preview_periodo_aberto():
    _garantir_custo_ingestao_linha()
    admin_client, org_id = _admin_em_organizacao_propria()

    with SessionLocal() as session:
        registrar_ingestao_linha(session, organizacao_id=org_id, quantidade=1, referencia_id=1)
        session.commit()

    response = admin_client.get("/api/custos/preview")
    assert response.status_code == 200
    assert response.json()["data"]["total_centavos"] >= 1


def test_detalhar_relatorio_de_outra_organizacao_retorna_404():
    admin_client, _ = _admin_em_organizacao_propria()
    assert admin_client.get("/api/custos/999999999").status_code == 404

    # Isolamento de verdade: um relatório que EXISTE, mas pertence a outra
    # organização, também não pode ser visto — o id existir não basta
    # (ver issue #27; a versão anterior deste teste só cobria id inexistente).
    _garantir_custo_ingestao_linha()
    admin_a, _ = _admin_em_organizacao_propria()
    admin_b, org_b_id = _admin_em_organizacao_propria()

    with SessionLocal() as session:
        registrar_ingestao_linha(session, organizacao_id=org_b_id, quantidade=1, referencia_id=1)
        session.commit()

    today = date.today()
    run_offset_days = int(_RUN, 16) % 10000
    periodo_inicio = (today - timedelta(days=5000 + run_offset_days)).isoformat()
    periodo_fim = (today + timedelta(days=5000)).isoformat()

    fechar_response = admin_b.post(
        "/api/admin/custos/fechar",
        json={"periodo_inicio": periodo_inicio, "periodo_fim": periodo_fim},
    )
    assert fechar_response.status_code == 201
    relatorio_de_outra_org = fechar_response.json()["data"]["id"]

    assert admin_a.get(f"/api/custos/{relatorio_de_outra_org}").status_code == 404
