"""Tests for generate_ticket."""

from datetime import datetime

from app.tickets.generator import generate_ticket
from app.tickets.priority_rules import PriorityRules


def _rules():
    return PriorityRules(rules={"Incidente": "P1", "Requisição": "P3"}, fallback="P3")


def _row(descricao="VPN do escritório caiu para todos os usuários remotos"):
    return {"id": "T001", "descricao": descricao}


def _classification(nivel1="Incidente", nivel2="Rede", c1=0.92, c2=0.88):
    return {
        "nivel1": nivel1,
        "nivel2": nivel2,
        "confianca_n1": c1,
        "confianca_n2": c2,
    }


class TestGenerateTicket:
    def test_full_ticket_structure(self):
        ticket = generate_ticket(
            row=_row(),
            classification=_classification(),
            rules=_rules(),
            ticket_counter=1,
        )

        assert ticket["id_ticket"] == "TCK-0001"
        assert ticket["tipo_itil"] == "Incidente"
        assert ticket["area_responsavel"] == "Rede"
        assert ticket["prioridade"] == "P1"
        assert ticket["descricao_original"] == _row()["descricao"]
        assert ticket["id_origem"] == "T001"
        assert ticket["confianca_n1"] == 0.92
        assert ticket["confianca_n2"] == 0.88

    def test_title_uses_first_80_chars_plus_type(self):
        long_desc = "x" * 200
        ticket = generate_ticket(
            row={"id": "T001", "descricao": long_desc},
            classification=_classification(nivel1="Incidente"),
            rules=_rules(),
            ticket_counter=1,
        )
        assert ticket["titulo_sugerido"] == "x" * 80 + " — Incidente"

    def test_short_description_kept_as_is_in_title(self):
        short = "VPN caiu"
        ticket = generate_ticket(
            row={"id": "T001", "descricao": short},
            classification=_classification(),
            rules=_rules(),
            ticket_counter=1,
        )
        assert ticket["titulo_sugerido"] == "VPN caiu — Incidente"

    def test_ticket_counter_zero_padded_4_digits(self):
        ticket = generate_ticket(
            row=_row(),
            classification=_classification(),
            rules=_rules(),
            ticket_counter=42,
        )
        assert ticket["id_ticket"] == "TCK-0042"

    def test_data_geracao_is_iso_utc(self):
        ticket = generate_ticket(
            row=_row(),
            classification=_classification(),
            rules=_rules(),
            ticket_counter=1,
        )
        parsed = datetime.fromisoformat(ticket["data_geracao"])
        assert parsed.tzinfo is not None  # has timezone info

    def test_unknown_itil_type_uses_fallback_priority(self):
        ticket = generate_ticket(
            row=_row(),
            classification=_classification(nivel1="Desconhecido"),
            rules=_rules(),
            ticket_counter=1,
        )
        assert ticket["prioridade"] == "P3"  # fallback
