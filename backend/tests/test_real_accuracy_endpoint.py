# backend/tests/test_real_accuracy_endpoint.py
"""Testes de GET /api/models/quality/reviews — integração real contra o
Postgres do docker-compose.yml. Sem mock de banco.

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


def test_shape_e_bounds_independente_de_quantas_revisoes_ja_existem():
    response = client.get("/api/models/quality/reviews")
    assert response.status_code == 200
    payload = response.json()

    for nivel in ("nivel1", "nivel2"):
        assert nivel in payload
        assert "macro_f1" in payload[nivel]
        assert "revisados" in payload[nivel]
        assert "total_tickets" in payload[nivel]
        assert payload[nivel]["revisados"] >= 0
        assert payload[nivel]["total_tickets"] >= 0
        if payload[nivel]["revisados"] == 0:
            assert payload[nivel]["macro_f1"] is None
        else:
            assert 0.0 <= payload[nivel]["macro_f1"] <= 1.0


def test_revisados_aumenta_apos_revisar_um_ticket():
    ticket = _seed_ticket("w")

    baseline = client.get("/api/models/quality/reviews").json()

    r = client.patch(
        f"/api/tickets/{ticket['id']}/revisao",
        json={"nivel": "tipo_itil", "valor": "Incidente"},
    )
    assert r.status_code == 200

    depois = client.get("/api/models/quality/reviews").json()
    assert depois["nivel1"]["revisados"] == baseline["nivel1"]["revisados"] + 1
    assert depois["nivel1"]["macro_f1"] is not None
    assert 0.0 <= depois["nivel1"]["macro_f1"] <= 1.0
    # nível 2 (área) não foi tocado por esta chamada
    assert depois["nivel2"]["revisados"] == baseline["nivel2"]["revisados"]
