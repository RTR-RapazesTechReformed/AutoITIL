"""Testes de app.tickets.queries — parsing/persistência de
ticket.descricao_enriquecida (F2-4 redesign). Integração real contra o
Postgres do docker-compose.yml, mesmo padrão de test_persistence.py."""

import json

from app.domain.db import SessionLocal
from app.domain.models import Ticket
from app.tickets.persistence import persist_generated_tickets
from app.tickets.queries import (
    _parse_enriquecimento,
    get_ticket_for_enrichment,
    list_tickets,
    save_enriched_description,
)


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


class TestParseEnriquecimento:
    def test_none_stays_none(self):
        assert _parse_enriquecimento(None) is None

    def test_parses_valid_json(self):
        raw = json.dumps(
            {
                "objetivo": "Resolver X.",
                "requisicoes": ["Fazer Y."],
                "cargo_recomendado": "Suporte.",
            }
        )
        assert _parse_enriquecimento(raw) == {
            "objetivo": "Resolver X.",
            "requisicoes": ["Fazer Y."],
            "cargo_recomendado": "Suporte.",
        }

    def test_legacy_plain_string_becomes_objetivo_only(self):
        raw = "A VPN não está conectando desde ontem."
        assert _parse_enriquecimento(raw) == {
            "objetivo": "A VPN não está conectando desde ontem.",
            "requisicoes": None,
            "cargo_recomendado": None,
        }

    def test_legacy_requisicoes_string_is_coerced_to_list(self):
        raw = json.dumps(
            {
                "objetivo": "X.",
                "requisicoes": "Y.",
                "cargo_recomendado": "Z.",
            }
        )
        assert _parse_enriquecimento(raw) == {
            "objetivo": "X.",
            "requisicoes": ["Y."],
            "cargo_recomendado": "Z.",
        }

    def test_malformed_json_falls_back_to_legacy(self):
        raw = "{objetivo: sem aspas, json invalido}"
        result = _parse_enriquecimento(raw)
        assert result["objetivo"] == raw
        assert result["requisicoes"] is None


class TestSaveAndGetEnriquecimento:
    def test_round_trip_persists_and_reads_back_structured_dict(self):
        ticket = _seed_ticket("d")
        fields = {
            "objetivo": "Resolver a VPN.",
            "requisicoes": ["Verificar configuração.", "Testar conectividade."],
            "cargo_recomendado": "Suporte de redes.",
        }

        with SessionLocal() as session:
            result = save_enriched_description(session, ticket["id"], fields)
            session.commit()

        assert result["descricao_enriquecida"] == fields

        with SessionLocal() as session:
            found = get_ticket_for_enrichment(session, ticket["id"])

        assert found["descricao_enriquecida"] == fields

    def test_stored_value_is_valid_json_in_the_database(self):
        ticket = _seed_ticket("e")
        fields = {"objetivo": "X.", "requisicoes": ["Y."], "cargo_recomendado": "Z."}

        with SessionLocal() as session:
            save_enriched_description(session, ticket["id"], fields)
            session.commit()

        with SessionLocal() as session:
            persisted = session.get(Ticket, ticket["id"])
            assert json.loads(persisted.descricao_enriquecida) == fields

    def test_reads_back_legacy_plain_string_ticket(self):
        ticket = _seed_ticket("f")

        with SessionLocal() as session:
            t = session.get(Ticket, ticket["id"])
            t.descricao_enriquecida = "Texto legado sem JSON."
            session.commit()

        with SessionLocal() as session:
            found = get_ticket_for_enrichment(session, ticket["id"])

        assert found["descricao_enriquecida"] == {
            "objetivo": "Texto legado sem JSON.",
            "requisicoes": None,
            "cargo_recomendado": None,
        }


class TestListTicketsEnriquecimento:
    def test_list_tickets_returns_structured_and_legacy_shapes(self):
        estruturado = _seed_ticket("g")
        legado = _seed_ticket("h")

        fields = {
            "objetivo": "Resolver a VPN.",
            "requisicoes": ["Verificar configuração."],
            "cargo_recomendado": "Suporte de redes.",
        }
        with SessionLocal() as session:
            t = session.get(Ticket, estruturado["id"])
            t.descricao_enriquecida = json.dumps(fields, ensure_ascii=False)
            session.commit()

        with SessionLocal() as session:
            t = session.get(Ticket, legado["id"])
            t.descricao_enriquecida = "Texto legado sem JSON."
            session.commit()

        with SessionLocal() as session:
            result = list_tickets(session, page=1, page_size=100)

        by_id = {item["id"]: item for item in result["items"]}

        assert by_id[estruturado["id"]]["descricao_enriquecida"] == fields
        assert by_id[legado["id"]]["descricao_enriquecida"] == {
            "objetivo": "Texto legado sem JSON.",
            "requisicoes": None,
            "cargo_recomendado": None,
        }
