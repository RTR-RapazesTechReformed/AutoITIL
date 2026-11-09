"""Testes de POST /api/tickets/{id}/enrich (F2-4) — integração real contra
o Postgres do docker-compose.yml (ticket seedado de verdade). O LLM em si é
mockado via app.api.routes._enricher, no mesmo espírito de
test_cascade.py/test_bert_classifier.py: a inferência real já foi validada
manualmente, rodar o modelo de novo
a cada execução da suíte seria lento e não agrega cobertura nova aqui."""

import json
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.domain.db import SessionLocal
from app.domain.enrichment_metrics import list_enrichment_metrics_history
from app.domain.models import Ticket
from app.main import app
from app.tickets.persistence import persist_generated_tickets
from tests.auth_helpers import AUTH_HEADERS

client = TestClient(app, headers=AUTH_HEADERS)


def _row(linha_origem=1, descricao="vpn nao conecta desde ontem"):
    return {
        "linha_origem": linha_origem,
        "descricao_original": descricao,
        "descricao_limpa": descricao.lower(),
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
        "titulo_sugerido": "VPN não conecta — Incidente",
    }


def _seed_ticket(hash_suffix, **row_kwargs):
    hash_ = hash_suffix * 64
    with SessionLocal() as session:
        created = persist_generated_tickets(
            session,
            file_key=f"uploads/{hash_}/teste.csv",
            bucket="autoitil-uploads",
            tamanho_bytes=10,
            rows=[_row(**row_kwargs)],
        )
        session.commit()
        return created[0]


def test_returns_404_for_nonexistent_ticket():
    response = client.post("/api/tickets/999999999/enrich")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "TICKET_NOT_FOUND"


def test_enriches_and_persists_description():
    ticket = _seed_ticket("5", descricao="vpn nao conecta desde ontem")

    fields = {
        "objetivo": "Resolver a VPN que não está conectando.",
        "requisicoes": ["Verificar configuração de rede."],
        "cargo_recomendado": "Suporte de redes.",
    }

    with patch("app.api.routes._enricher") as mock_enricher:
        mock_enricher.is_available.return_value = True
        mock_enricher.enrich.return_value = fields
        mock_enricher.last_call_duration_ms = 1234.5
        mock_enricher.last_call_tokens_entrada = 42
        mock_enricher.last_call_tokens_saida = 18

        response = client.post(f"/api/tickets/{ticket['id']}/enrich")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["descricao_enriquecida"] == fields
    mock_enricher.enrich.assert_called_once_with("vpn nao conecta desde ontem")

    with SessionLocal() as session:
        persisted = session.get(Ticket, ticket["id"])
        assert json.loads(persisted.descricao_enriquecida) == fields

    with SessionLocal() as session:
        history = list_enrichment_metrics_history(session, limit=1)
    assert history[-1]["ticket_id"] == ticket["id"]
    assert history[-1]["duracao_ms"] == 1234.5
    assert history[-1]["tokens_entrada"] == 42
    assert history[-1]["tokens_saida"] == 18


def test_second_call_returns_cache_without_calling_model_again():
    ticket = _seed_ticket("6", descricao="impressora sem tinta")

    fields = {
        "objetivo": "Resolver a impressora sem tinta.",
        "requisicoes": ["Trocar o cartucho."],
        "cargo_recomendado": "Suporte de infraestrutura.",
    }

    with patch("app.api.routes._enricher") as mock_enricher:
        mock_enricher.is_available.return_value = True
        mock_enricher.enrich.return_value = fields
        mock_enricher.last_call_duration_ms = 500.0
        mock_enricher.last_call_tokens_entrada = 20
        mock_enricher.last_call_tokens_saida = 10

        first = client.post(f"/api/tickets/{ticket['id']}/enrich")
        second = client.post(f"/api/tickets/{ticket['id']}/enrich")

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["data"]["descricao_enriquecida"] == fields
    assert second.json()["message"].startswith("Descrição já enriquecida")
    mock_enricher.enrich.assert_called_once()


def test_returns_503_when_enricher_unavailable():
    ticket = _seed_ticket("7", descricao="sistema fora do ar")

    with patch("app.api.routes._enricher") as mock_enricher:
        mock_enricher.is_available.return_value = False

        response = client.post(f"/api/tickets/{ticket['id']}/enrich")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "ENRICHMENT_UNAVAILABLE"


def test_returns_503_when_enrich_call_fails():
    ticket = _seed_ticket("8", descricao="rede lenta")

    with patch("app.api.routes._enricher") as mock_enricher:
        mock_enricher.is_available.return_value = True
        mock_enricher.enrich.return_value = None

        response = client.post(f"/api/tickets/{ticket['id']}/enrich")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "ENRICHMENT_UNAVAILABLE"


def test_enrich_registra_evento_de_custo():
    from sqlalchemy import select

    from app.domain.models import EventoCusto

    ticket = _seed_ticket("7", descricao="disco cheio no servidor")
    fields = {"objetivo": "liberar espaço", "requisicoes": None, "cargo_recomendado": None}

    with patch("app.api.routes._enricher") as mock_enricher:
        mock_enricher.is_available.return_value = True
        mock_enricher.enrich.return_value = fields
        mock_enricher.last_call_duration_ms = 300.0
        mock_enricher.last_call_tokens_entrada = 50
        mock_enricher.last_call_tokens_saida = 25

        response = client.post(f"/api/tickets/{ticket['id']}/enrich")

    assert response.status_code == 200

    with SessionLocal() as session:
        evento = session.scalar(
            select(EventoCusto)
            .where(EventoCusto.tipo_evento == "enriquecimento_chamada")
            .order_by(EventoCusto.id.desc())
        )

    assert evento is not None
    assert evento.referencia_id == ticket["id"]
    assert evento.tokens_entrada == 50
    assert evento.tokens_saida == 25
