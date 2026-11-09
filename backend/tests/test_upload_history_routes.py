"""Testes de integração: /api/upload grava historico_upload em 'recebido'
e depois 'pre_visualizado' (ou 'falhou'), na mesma requisição. Requer
Postgres + MinIO do docker-compose.yml — sem mock de banco/storage."""

import uuid
from unittest.mock import patch

import pandas as pd
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.domain.db import SessionLocal
from app.domain.models import HistoricoUpload
from app.main import app
from tests.auth_helpers import AUTH_HEADERS

client = TestClient(app, headers=AUTH_HEADERS)


def _csv_bytes(rows):
    return pd.DataFrame(rows).to_csv(index=False).encode("utf-8")


def _entries_for(nome_original):
    with SessionLocal() as session:
        return session.scalars(
            select(HistoricoUpload)
            .where(HistoricoUpload.nome_original == nome_original)
            .order_by(HistoricoUpload.criado_em.asc())
        ).all()


def test_upload_creates_recebido_then_pre_visualizado():
    filename = f"historico_teste_1_{uuid.uuid4().hex}.csv"
    content = _csv_bytes({"descricao": ["VPN caiu"]})
    response = client.post(
        "/api/upload",
        files={"file": (filename, content, "text/csv")},
    )
    assert response.status_code == 200

    entries = _entries_for(filename)
    assert len(entries) == 1
    assert entries[0].status == "pre_visualizado"
    assert entries[0].total_linhas == 1


def test_second_upload_of_same_file_updates_most_recent_open_entry():
    filename = f"historico_teste_2_{uuid.uuid4().hex}.csv"
    content = _csv_bytes({"descricao": ["Impressora sem tinta"]})

    client.post(
        "/api/upload",
        files={"file": (filename, content, "text/csv")},
    )
    client.post(
        "/api/upload",
        files={"file": (filename, content, "text/csv")},
    )

    entries = _entries_for(filename)
    assert len(entries) == 2
    assert all(entry.status == "pre_visualizado" for entry in entries)


def test_upload_succeeds_even_if_history_write_fails():
    filename = f"historico_teste_3_{uuid.uuid4().hex}.csv"
    content = _csv_bytes({"descricao": ["Erro de historico nao deve travar upload"]})
    with patch(
        "app.api.routes.record_upload_received", side_effect=RuntimeError("boom")
    ):
        response = client.post(
            "/api/upload",
            files={"file": (filename, content, "text/csv")},
        )
    assert response.status_code == 200


def test_preview_failure_marks_falhou():
    filename = f"historico_teste_4_{uuid.uuid4().hex}.csv"
    # Bytes binários, não decodificáveis como CSV — IngestionPipeline().preview()
    # deve falhar o parse, caindo no except de _preview_upload.
    content = b"\xff\xfe\x00\x01invalid-binary-not-a-csv\x00\x02"

    response = client.post(
        "/api/upload",
        files={"file": (filename, content, "text/csv")},
    )
    assert response.status_code == 400

    entries = _entries_for(filename)
    assert len(entries) == 1
    assert entries[0].status == "falhou"
    assert entries[0].mensagem_erro
