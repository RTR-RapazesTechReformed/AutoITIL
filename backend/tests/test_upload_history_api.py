"""Testes de GET /api/uploads — lista os últimos uploads, mais recente
primeiro, exige token JWT. Integração real contra Postgres/MinIO."""

import pandas as pd
from fastapi.testclient import TestClient

from app.main import app
from tests.auth_helpers import AUTH_HEADERS

client_no_key = TestClient(app)
client_with_key = TestClient(app, headers=AUTH_HEADERS)


def test_requires_api_key():
    response = client_no_key.get("/api/uploads")
    assert response.status_code == 401


def test_lists_recent_uploads_most_recent_first():
    content = (
        pd.DataFrame({"descricao": ["Teste de listagem"]})
        .to_csv(index=False)
        .encode("utf-8")
    )

    client_with_key.post(
        "/api/upload",
        files={"file": ("historico_lista_1.csv", content, "text/csv")},
    )
    client_with_key.post(
        "/api/upload",
        files={"file": ("historico_lista_2.csv", content, "text/csv")},
    )

    response = client_with_key.get("/api/uploads")
    assert response.status_code == 200

    data = response.json()["data"]
    assert len(data) >= 2
    nomes = [item["nome_original"] for item in data]
    assert nomes.index("historico_lista_2.csv") < nomes.index("historico_lista_1.csv")
    assert "status" in data[0]
    assert "criado_em" in data[0]
