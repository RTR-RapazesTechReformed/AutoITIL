"""Testes de integração: /api/tickets/generate-from-file atualiza
historico_upload pra 'tickets_gerados' ou 'falhou', conforme o resultado.
Requer Postgres + MinIO do docker-compose.yml — sem mock de banco/storage,
só o classificador (_cascade) é mockado."""

from unittest.mock import patch

import pandas as pd
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.domain.db import SessionLocal
from app.domain.models import HistoricoUpload
from app.main import app
from tests.auth_helpers import AUTH_HEADERS

client_with_key = TestClient(app, headers=AUTH_HEADERS)


def _upload_and_get_file_path(name, rows):
    content = pd.DataFrame(rows).to_csv(index=False).encode("utf-8")
    response = client_with_key.post(
        "/api/upload", files={"file": (name, content, "text/csv")}
    )
    assert response.status_code == 200
    return response.json()["data"]["file_id"]


def _classification():
    return {
        "nivel1": "Incidente",
        "nivel2": "Rede",
        "confianca_n1": 0.9,
        "confianca_n2": 0.85,
        "modelo_n1": "bert",
        "modelo_n2": "bert",
    }


def _latest_entry(nome_original):
    with SessionLocal() as session:
        return session.scalars(
            select(HistoricoUpload)
            .where(HistoricoUpload.nome_original == nome_original)
            .order_by(HistoricoUpload.criado_em.desc())
        ).first()


def test_successful_generation_marks_tickets_gerados():
    file_path = _upload_and_get_file_path(
        "historico_generation_ok.csv", {"descricao": ["VPN do escritorio caiu"]}
    )

    with patch("app.api.routes._cascade") as mock_cascade:
        mock_cascade.is_available.return_value = True
        mock_cascade.classify.return_value = _classification()

        response = client_with_key.post(
            "/api/tickets/generate-from-file",
            data={
                "file_path": file_path,
                "descricao": "descricao",
                "data": "",
                "responsavel": "",
                "format": "json",
            },
        )

    assert response.status_code == 200
    entry = _latest_entry("historico_generation_ok.csv")
    assert entry is not None
    assert entry.status == "tickets_gerados"


def test_classifier_unavailable_marks_falhou():
    file_path = _upload_and_get_file_path(
        "historico_generation_503.csv", {"descricao": ["Impressora sem tinta"]}
    )

    with patch("app.api.routes._cascade") as mock_cascade:
        mock_cascade.is_available.return_value = False

        response = client_with_key.post(
            "/api/tickets/generate-from-file",
            data={
                "file_path": file_path,
                "descricao": "descricao",
                "data": "",
                "responsavel": "",
                "format": "json",
            },
        )

    assert response.status_code == 503
    entry = _latest_entry("historico_generation_503.csv")
    assert entry is not None
    assert entry.status == "falhou"
    assert entry.mensagem_erro


def test_bad_mapping_marks_falhou():
    file_path = _upload_and_get_file_path(
        "historico_generation_400.csv", {"descricao": ["Erro de mapeamento"]}
    )

    response = client_with_key.post(
        "/api/tickets/generate-from-file",
        data={
            "file_path": file_path,
            "descricao": "coluna_inexistente",
            "data": "",
            "responsavel": "",
            "format": "json",
        },
    )

    assert response.status_code == 400
    entry = _latest_entry("historico_generation_400.csv")
    assert entry is not None
    assert entry.status == "falhou"
