"""Testes de POST /api/tickets/generate-from-file (upload+mapeamento → tickets).

Requer o container do MinIO do docker-compose.yml rodando (`docker compose up -d`) —
os testes fazem upload real via `app.domain.storage.upload_bytes`, sem mockar boto3.
"""

import json
from unittest.mock import patch

import pandas as pd
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.domain.db import SessionLocal
from app.domain.models import Ticket
from app.domain.storage import upload_bytes
from app.main import app
from tests.auth_helpers import AUTH_HEADERS

client = TestClient(app, headers=AUTH_HEADERS)


def _classification(nivel1="Incidente", nivel2="Rede", c1=0.92, c2=0.88):
    return {
        "nivel1": nivel1,
        "nivel2": nivel2,
        "confianca_n1": c1,
        "confianca_n2": c2,
        "modelo_n1": "bert",
        "modelo_n2": "bert" if nivel2 is not None else None,
    }


def _write_upload(name, rows):
    content = pd.DataFrame(rows).to_csv(index=False).encode("utf-8")
    return upload_bytes(content, name)


def test_generates_tickets_from_uploaded_file():
    file_key = _write_upload(
        "tickets_from_file.csv",
        {"problema": ["VPN do escritorio caiu"], "abertura": ["2026-05-14"]},
    )

    with patch("app.api.routes._cascade") as mock_cascade:
        mock_cascade.is_available.return_value = True
        mock_cascade.classify.return_value = _classification()

        response = client.post(
            "/api/tickets/generate-from-file",
            data={
                "file_path": file_key,
                "descricao": "problema",
                "data": "abertura",
                "responsavel": "",
                "format": "json",
            },
        )

    assert response.status_code == 200
    assert "attachment" in response.headers["content-disposition"]

    tickets = json.loads(response.content)
    assert len(tickets) == 1
    assert tickets[0]["descricao_original"] == "VPN do escritorio caiu"
    assert tickets[0]["tipo_itil"] == "Incidente"
    assert tickets[0]["area_responsavel"] == "Rede"

    # id_ticket no JSON baixado é substituído pelo codigo real da sequence
    # do banco (não mais o contador local por request) — devem ser o mesmo
    # identificador tanto no download quanto no Kanban.
    assert tickets[0]["id_ticket"].startswith("TCK-")

    with SessionLocal() as session:
        # Filtra por codigo (globalmente único via sequence), não por
        # titulo_sugerido — outros testes (ex.: test_persistence.py) usam
        # a mesma string de título em seus fixtures, então buscar por
        # título contaria tickets de outros testes também.
        persisted = session.scalars(
            select(Ticket).where(Ticket.codigo == tickets[0]["id_ticket"])
        ).all()
        assert len(persisted) == 1
        assert persisted[0].titulo_sugerido == tickets[0]["titulo_sugerido"]


def test_generates_tickets_when_some_rows_have_empty_date():
    """Bug real de producao: uma celula de data vazia numa planilha real
    virava NaN (float) apos o pandas ler o CSV. `row.get("data") or None`
    em persistence.py nao pegava esse caso -- NaN e truthy em Python --
    entao o NaN ia parar direto no INSERT como valor de uma coluna DATE,
    e o Postgres rejeitava com 'cannot cast type double precision to
    date'. O erro acontecia so quando ALGUMA linha tinha data vazia,
    nao em todo upload -- por isso passou despercebido em testes com
    datasets pequenos e sempre preenchidos."""
    file_key = _write_upload(
        "tickets_empty_date.csv",
        {
            "problema": ["VPN do escritorio caiu", "Impressora sem tinta"],
            "abertura": ["2026-05-14", None],
        },
    )

    with patch("app.api.routes._cascade") as mock_cascade:
        mock_cascade.is_available.return_value = True
        mock_cascade.classify.return_value = _classification()

        response = client.post(
            "/api/tickets/generate-from-file",
            data={
                "file_path": file_key,
                "descricao": "problema",
                "data": "abertura",
                "responsavel": "",
                "format": "json",
            },
        )

    assert response.status_code == 200
    tickets = json.loads(response.content)
    assert len(tickets) == 2


def test_returns_503_when_classifier_unavailable(tmp_path):
    file_key = _write_upload(
        "tickets_no_model.csv", {"descricao": ["VPN do escritorio caiu"]}
    )

    with patch("app.api.routes._cascade") as mock_cascade:
        mock_cascade.is_available.return_value = False

        response = client.post(
            "/api/tickets/generate-from-file",
            data={
                "file_path": file_key,
                "descricao": "descricao",
                "data": "",
                "responsavel": "",
                "format": "json",
            },
        )

    assert response.status_code == 503
    # Bug real de producao: com format=json, essa rota sempre devolvia HTML
    # (_render_index) em qualquer erro -- response.json() explodia com
    # SyntaxError no frontend, escondendo a mensagem real do backend atras
    # de um fallback generico ("Falha ao gerar os tickets."). Ver
    # _generate_from_file_error em app/api/routes.py.
    assert response.headers["content-type"].startswith("application/json")
    payload = response.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "CLASSIFIER_UNAVAILABLE"


def test_returns_error_for_missing_descricao_mapping():
    file_key = _write_upload(
        "tickets_bad_mapping.csv", {"descricao": ["VPN do escritorio caiu"]}
    )

    response = client.post(
        "/api/tickets/generate-from-file",
        data={
            "file_path": file_key,
            "descricao": "coluna_inexistente",
            "data": "",
            "responsavel": "",
            "format": "json",
        },
    )

    assert response.status_code == 400
    assert response.headers["content-type"].startswith("application/json")
    payload = response.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "COLUMN_NOT_FOUND"


def test_returns_error_for_nonexistent_file():
    response = client.post(
        "/api/tickets/generate-from-file",
        data={
            "file_path": "uploads/nao-existe/arquivo.csv",
            "descricao": "descricao",
            "data": "",
            "responsavel": "",
            "format": "json",
        },
    )

    assert response.status_code == 400
    assert response.headers["content-type"].startswith("application/json")
    payload = response.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "FILE_NOT_FOUND"


def test_error_response_is_always_json_even_when_format_is_not_json():
    """A rota é consumida exclusivamente pelo frontend React — o fluxo
    legado em Jinja2 que também batia aqui esperando HTML foi removido
    junto com a autenticação JWT. Erro é sempre JSON agora, mesmo com
    format=csv (só a resposta de *sucesso* varia por `format`)."""
    file_key = _write_upload(
        "tickets_bad_mapping_csv.csv", {"descricao": ["VPN do escritorio caiu"]}
    )

    response = client.post(
        "/api/tickets/generate-from-file",
        data={
            "file_path": file_key,
            "descricao": "coluna_inexistente",
            "data": "",
            "responsavel": "",
            "format": "csv",
        },
    )

    assert response.status_code == 400
    assert response.headers["content-type"].startswith("application/json")
    payload = response.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "COLUMN_NOT_FOUND"
