"""Testes de PATCH /api/tickets/{id}/revisao — integração real contra o
Postgres do docker-compose.yml. Sem mock de banco."""

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


def test_revisa_tipo_itil_e_retorna_ticket_atualizado():
    ticket = _seed_ticket("q")

    response = client.patch(
        f"/api/tickets/{ticket['id']}/revisao",
        json={"nivel": "tipo_itil", "valor": "Problema"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["id"] == ticket["id"]
    assert payload["data"]["tipo_itil"] == "Problema"


def test_revisa_area_e_retorna_ticket_atualizado():
    ticket = _seed_ticket("r")

    response = client.patch(
        f"/api/tickets/{ticket['id']}/revisao",
        json={"nivel": "area", "valor": "Servidor"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["area_responsavel"] == "Servidor"


def test_confirmar_o_mesmo_valor_tambem_e_aceito():
    ticket = _seed_ticket("s")

    # o ticket nasce com tipo_itil="Incidente" (seedado acima) — confirmar
    # esse mesmo valor precisa ser aceito, não só uma correção de verdade
    response = client.patch(
        f"/api/tickets/{ticket['id']}/revisao",
        json={"nivel": "tipo_itil", "valor": "Incidente"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["tipo_itil"] == "Incidente"


def test_nao_altera_prioridade():
    ticket = _seed_ticket("t")

    antes = client.get(f"/api/tickets?busca={ticket['codigo']}").json()["data"]["items"][0]
    prioridade_original = antes["prioridade"]

    client.patch(
        f"/api/tickets/{ticket['id']}/revisao",
        json={"nivel": "tipo_itil", "valor": "Mudança"},
    )

    depois = client.get(f"/api/tickets?busca={ticket['codigo']}").json()["data"]["items"][0]
    assert depois["prioridade"] == prioridade_original


def test_returns_404_for_nonexistent_ticket():
    response = client.patch(
        "/api/tickets/999999999/revisao",
        json={"nivel": "tipo_itil", "valor": "Incidente"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "TICKET_NOT_FOUND"


def test_returns_422_for_invalid_nivel():
    ticket = _seed_ticket("u")

    response = client.patch(
        f"/api/tickets/{ticket['id']}/revisao",
        json={"nivel": "prioridade", "valor": "P1"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_returns_422_for_invalid_valor():
    ticket = _seed_ticket("v")

    response = client.patch(
        f"/api/tickets/{ticket['id']}/revisao",
        json={"nivel": "tipo_itil", "valor": "Categoria Inexistente"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
