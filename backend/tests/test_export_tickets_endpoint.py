"""Testes de GET /api/tickets/export — integração real contra o Postgres do
docker-compose.yml (Postgres + schema v5). Sem mock de banco."""

import io

import pandas as pd
from fastapi.testclient import TestClient

from app.domain.db import SessionLocal
from app.main import app
from app.tickets.persistence import persist_generated_tickets
from tests.auth_helpers import AUTH_HEADERS

client = TestClient(app, headers=AUTH_HEADERS)


def _row(linha_origem, descricao, nivel1="Incidente", nivel2="Rede", prioridade="P1"):
    return {
        "linha_origem": linha_origem,
        "descricao_original": descricao,
        "descricao_limpa": descricao.lower(),
        "data": None,
        "responsavel": None,
        "classification": {
            "nivel1": nivel1,
            "nivel2": nivel2,
            "confianca_n1": 0.90,
            "confianca_n2": 0.80 if nivel2 is not None else None,
            "modelo_n1": "bert",
            "modelo_n2": "bert" if nivel2 is not None else None,
        },
        "prioridade_codigo": prioridade,
        "titulo_sugerido": f"{descricao} — {nivel1}",
    }


def _seed(file_key, rows):
    with SessionLocal() as session:
        created = persist_generated_tickets(
            session,
            file_key=file_key,
            bucket="autoitil-uploads",
            tamanho_bytes=10,
            rows=rows,
        )
        session.commit()
        return created


def test_export_csv_returns_200_with_correct_headers():
    hash_ = "5" * 64
    _seed(
        f"uploads/{hash_}/lote-export-csv.csv",
        [_row(1, "falha exclusiva pro export csv")],
    )

    response = client.get(
        "/api/tickets/export?format=csv&busca=falha exclusiva pro export csv"
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert (
        'attachment; filename="tickets-classificados.csv"'
        in response.headers["content-disposition"]
    )
    assert "falha exclusiva pro export csv" in response.text


def test_export_xlsx_returns_200_with_correct_headers():
    hash_ = "6" * 64
    _seed(
        f"uploads/{hash_}/lote-export-xlsx.csv",
        [_row(1, "falha exclusiva pro export xlsx")],
    )

    response = client.get(
        "/api/tickets/export?format=xlsx&busca=falha exclusiva pro export xlsx"
    )

    assert response.status_code == 200
    assert (
        response.headers["content-type"]
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert (
        'attachment; filename="tickets-classificados.xlsx"'
        in response.headers["content-disposition"]
    )
    df = pd.read_excel(io.BytesIO(response.content))
    assert (df["titulo_sugerido"].str.contains("falha exclusiva pro export xlsx")).any()


def test_export_invalid_format_returns_422():
    response = client.get("/api/tickets/export?format=xml")
    assert response.status_code == 422


def test_export_without_api_key_returns_401():
    anon_client = TestClient(app)
    response = anon_client.get("/api/tickets/export?format=csv")
    assert response.status_code == 401
