"""Testes de PATCH /api/tickets/{id} — integração real contra o Postgres do
docker-compose.yml (Postgres + schema v5). Sem mock de banco."""

from fastapi.testclient import TestClient

from app.domain.db import SessionLocal
from app.main import app
from app.tickets.persistence import persist_generated_tickets
from tests.auth_helpers import AUTH_HEADERS

client = TestClient(app, headers=AUTH_HEADERS)


def _row(linha_origem=1):
    return {
        "linha_origem": linha_origem,
        "descricao_original": "VPN do escritorio caiu",
        "descricao_limpa": "vpn escritorio caiu",
        "data": None,
        "responsavel": None,
        "classification": {
            "nivel1": "Incidente",
            "nivel2": "Rede",
            "confianca_n1": 0.94,
            "confianca_n2": 0.88,
            "modelo_n1": "bert",
            "modelo_n2": "bert",
        },
        "prioridade_codigo": "P1",
        "titulo_sugerido": "VPN do escritorio caiu — Incidente",
    }


def _seed_ticket(hash_suffix):
    hash_ = hash_suffix * 64
    with SessionLocal() as session:
        created = persist_generated_tickets(
            session,
            file_key=f"uploads/{hash_}/teste.csv",
            bucket="autoitil-uploads",
            tamanho_bytes=10,
            rows=[_row()],
        )
        session.commit()
        return created[0]


def test_moves_ticket_to_new_status():
    ticket = _seed_ticket("4")

    response = client.patch(
        f"/api/tickets/{ticket['id']}", json={"status": "em_progresso"}
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["id"] == ticket["id"]
    assert payload["data"]["codigo"] == ticket["codigo"]
    assert payload["data"]["status"] == "em_progresso"


def test_allows_free_transition_between_any_columns():
    ticket = _seed_ticket("5")

    # triagem -> concluido (pula etapas) -> a_fazer (volta) — deve ser permitido
    r1 = client.patch(f"/api/tickets/{ticket['id']}", json={"status": "concluido"})
    assert r1.status_code == 200
    r2 = client.patch(f"/api/tickets/{ticket['id']}", json={"status": "a_fazer"})
    assert r2.status_code == 200
    assert r2.json()["data"]["status"] == "a_fazer"


def test_returns_404_for_nonexistent_ticket():
    response = client.patch("/api/tickets/999999999", json={"status": "triagem"})
    assert response.status_code == 404
    payload = response.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "TICKET_NOT_FOUND"


def test_returns_422_for_invalid_status():
    ticket = _seed_ticket("6")

    response = client.patch(f"/api/tickets/{ticket['id']}", json={"status": "foo"})
    assert response.status_code == 422
    payload = response.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "VALIDATION_ERROR"


def test_updates_atualizado_em_timestamp():
    ticket = _seed_ticket("7")

    response = client.patch(
        f"/api/tickets/{ticket['id']}", json={"status": "em_progresso"}
    )
    assert response.status_code == 200
    assert "atualizado_em" in response.json()["data"]
