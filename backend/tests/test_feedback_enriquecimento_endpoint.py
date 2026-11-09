"""Testes de PATCH /api/tickets/{id}/feedback-enriquecimento — integração
real contra o Postgres do docker-compose.yml. Sem mock de banco."""

from fastapi.testclient import TestClient

from app.domain.db import SessionLocal
from app.main import app
from app.tickets.persistence import persist_generated_tickets
from tests.auth_helpers import AUTH_HEADERS

client = TestClient(app, headers=AUTH_HEADERS)


def _row(linha_origem=1):
    return {
        "linha_origem": linha_origem,
        "descricao_original": "Impressora sem tinta",
        "descricao_limpa": "impressora sem tinta",
        "data": None,
        "responsavel": None,
        "classification": {
            "nivel1": "Incidente",
            "nivel2": "Aplicações",
            "confianca_n1": 0.9,
            "confianca_n2": 0.8,
            "modelo_n1": "bert",
            "modelo_n2": "bert",
        },
        "prioridade_codigo": "P3",
        "titulo_sugerido": "Impressora sem tinta — Incidente",
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


def test_registra_voto_e_retorna_ticket_atualizado():
    ticket = _seed_ticket("l")

    response = client.patch(
        f"/api/tickets/{ticket['id']}/feedback-enriquecimento",
        json={"valor": "up"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["id"] == ticket["id"]
    assert payload["data"]["feedback_enriquecimento"] == "up"


def test_trocar_o_voto_atualiza_o_valor():
    ticket = _seed_ticket("o")

    client.patch(f"/api/tickets/{ticket['id']}/feedback-enriquecimento", json={"valor": "up"})
    response = client.patch(
        f"/api/tickets/{ticket['id']}/feedback-enriquecimento",
        json={"valor": "down"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["feedback_enriquecimento"] == "down"


def test_voto_aparece_na_listagem_de_tickets():
    ticket = _seed_ticket("j")

    client.patch(
        f"/api/tickets/{ticket['id']}/feedback-enriquecimento",
        json={"valor": "up"},
    )

    response = client.get(f"/api/tickets?busca={ticket['codigo']}")
    assert response.status_code == 200
    assert response.json()["data"]["items"][0]["feedback_enriquecimento"] == "up"


def test_returns_404_for_nonexistent_ticket():
    response = client.patch(
        "/api/tickets/999999999/feedback-enriquecimento",
        json={"valor": "up"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "TICKET_NOT_FOUND"


def test_returns_422_for_invalid_valor():
    ticket = _seed_ticket("x")

    response = client.patch(
        f"/api/tickets/{ticket['id']}/feedback-enriquecimento",
        json={"valor": "sideways"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
