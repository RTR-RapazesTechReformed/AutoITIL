"""Testes de GET /api/models/quality/enrichment-feedback — integração real contra
o Postgres do docker-compose.yml. Sem mock de banco.

Banco real e persistente, sem reset entre testes — nunca assume contagem
absoluta; sempre compara antes/depois de uma ação que este teste controla."""

from fastapi.testclient import TestClient

from app.domain.db import SessionLocal
from app.main import app
from app.tickets.persistence import persist_generated_tickets
from tests.auth_helpers import AUTH_HEADERS

client = TestClient(app, headers=AUTH_HEADERS)


def _row(linha_origem=1):
    return {
        "linha_origem": linha_origem,
        "descricao_original": "Erro ao acessar o servidor de arquivos",
        "descricao_limpa": "erro acessar servidor arquivos",
        "data": None,
        "responsavel": None,
        "classification": {
            "nivel1": "Incidente",
            "nivel2": "Servidor",
            "confianca_n1": 0.9,
            "confianca_n2": 0.85,
            "modelo_n1": "bert",
            "modelo_n2": "bert",
        },
        "prioridade_codigo": "P2",
        "titulo_sugerido": "Erro ao acessar o servidor de arquivos — Incidente",
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


def test_shape_e_bounds_independente_de_quantos_votos_ja_existem():
    response = client.get("/api/models/quality/enrichment-feedback")
    assert response.status_code == 200
    payload = response.json()

    for campo in ("total_enriquecidos", "total_votados", "positivos", "negativos"):
        assert campo in payload
        assert payload[campo] >= 0
    assert "percentual_positivo" in payload
    if payload["total_votados"] == 0:
        assert payload["percentual_positivo"] is None
    else:
        assert 0.0 <= payload["percentual_positivo"] <= 1.0
    assert payload["positivos"] + payload["negativos"] == payload["total_votados"]


def test_positivos_aumenta_apos_votar_up():
    ticket = _seed_ticket("y")

    baseline = client.get("/api/models/quality/enrichment-feedback").json()

    r = client.patch(
        f"/api/tickets/{ticket['id']}/feedback-enriquecimento",
        json={"valor": "up"},
    )
    assert r.status_code == 200

    depois = client.get("/api/models/quality/enrichment-feedback").json()
    assert depois["positivos"] == baseline["positivos"] + 1
    assert depois["total_votados"] == baseline["total_votados"] + 1
    assert depois["negativos"] == baseline["negativos"]


def test_trocar_o_voto_move_de_positivo_pra_negativo_sem_mudar_total():
    ticket = _seed_ticket("z")

    client.patch(f"/api/tickets/{ticket['id']}/feedback-enriquecimento", json={"valor": "up"})
    baseline = client.get("/api/models/quality/enrichment-feedback").json()

    client.patch(f"/api/tickets/{ticket['id']}/feedback-enriquecimento", json={"valor": "down"})
    depois = client.get("/api/models/quality/enrichment-feedback").json()

    assert depois["positivos"] == baseline["positivos"] - 1
    assert depois["negativos"] == baseline["negativos"] + 1
    assert depois["total_votados"] == baseline["total_votados"]
