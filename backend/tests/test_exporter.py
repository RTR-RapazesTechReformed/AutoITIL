"""Tests for export_tickets."""

import csv
import io
import json

import pandas as pd
import pytest

from app.tickets.exporter import _flatten_for_tabular, export_tickets


def _ticket(idx=1):
    return {
        "id_ticket": f"TCK-{idx:04d}",
        "titulo_sugerido": "Falha VPN — Incidente",
        "tipo_itil": "Incidente",
        "area_responsavel": "Rede",
        "prioridade": "P1",
        "descricao_original": "VPN caiu",
        "data_geracao": "2026-06-10T12:34:56+00:00",
        "id_origem": f"T{idx:03d}",
        "confianca_n1": 0.92,
        "confianca_n2": 0.88,
    }


class TestExportJSON:
    def test_returns_bytes(self):
        out = export_tickets([_ticket()], format="json")
        assert isinstance(out, bytes)

    def test_roundtrip_preserves_data(self):
        tickets = [_ticket(1), _ticket(2)]
        out = export_tickets(tickets, format="json")
        parsed = json.loads(out)
        assert parsed == tickets

    def test_preserves_accents(self):
        ticket = _ticket()
        ticket["tipo_itil"] = "Requisição"
        out = export_tickets([ticket], format="json")
        text = out.decode("utf-8")
        assert "Requisição" in text  # no \\u00e7\\u00e3 escaping


class TestExportCSV:
    def test_returns_bytes(self):
        out = export_tickets([_ticket()], format="csv")
        assert isinstance(out, bytes)

    def test_has_header_and_one_row(self):
        out = export_tickets([_ticket()], format="csv").decode("utf-8")
        reader = csv.reader(io.StringIO(out))
        rows = list(reader)
        assert len(rows) == 2  # header + 1
        assert "id_ticket" in rows[0]
        assert "TCK-0001" in rows[1]

    def test_columns_match_ticket_dict_order(self):
        t = _ticket()
        out = export_tickets([t], format="csv").decode("utf-8")
        header = next(csv.reader(io.StringIO(out)))
        assert header == list(t.keys())


class TestExportInvalidFormat:
    def test_raises_value_error(self):
        with pytest.raises(ValueError, match="format"):
            export_tickets([_ticket()], format="xml")  # type: ignore[arg-type]


class TestFlattenForTabular:
    def test_flattens_dict_field_to_json_string(self):
        ticket = _ticket()
        ticket["descricao_enriquecida"] = {
            "objetivo": "resolver a falha",
            "requisicoes": None,
        }
        flat = _flatten_for_tabular([ticket])
        assert isinstance(flat[0]["descricao_enriquecida"], str)
        assert (
            json.loads(flat[0]["descricao_enriquecida"])
            == ticket["descricao_enriquecida"]
        )

    def test_leaves_scalar_fields_untouched(self):
        ticket = _ticket()
        flat = _flatten_for_tabular([ticket])
        assert flat[0]["id_ticket"] == ticket["id_ticket"]
        assert flat[0]["confianca_n1"] == ticket["confianca_n1"]

    def test_none_field_stays_none(self):
        ticket = _ticket()
        ticket["descricao_enriquecida"] = None
        flat = _flatten_for_tabular([ticket])
        assert flat[0]["descricao_enriquecida"] is None


class TestCsvInjectionMitigation:
    @pytest.mark.parametrize("prefix", ["=", "+", "-", "@"])
    def test_prefixes_formula_like_string_with_single_quote(self, prefix):
        ticket = _ticket()
        ticket["titulo_sugerido"] = f"{prefix}cmd|' /C calc'!A0"
        flat = _flatten_for_tabular([ticket])
        assert flat[0]["titulo_sugerido"] == f"'{prefix}cmd|' /C calc'!A0"

    def test_leaves_normal_string_untouched(self):
        ticket = _ticket()
        flat = _flatten_for_tabular([ticket])
        assert flat[0]["titulo_sugerido"] == ticket["titulo_sugerido"]

    def test_sanitizes_json_string_from_flattened_dict(self):
        ticket = _ticket()
        # dict cuja serialização JSON começa com '{' normalmente — mas se o
        # dict virar uma string que começa com um dos prefixos perigosos
        # (caso extremo, ex. chave única cujo dump comece assim), a
        # sanitização também precisa cobrir esse caminho.
        ticket["descricao_enriquecida"] = "=cmd|' /C calc'!A0"
        flat = _flatten_for_tabular([ticket])
        assert flat[0]["descricao_enriquecida"] == "'=cmd|' /C calc'!A0"


class TestExportXLSX:
    def test_returns_bytes(self):
        out = export_tickets([_ticket()], format="xlsx")
        assert isinstance(out, bytes)

    def test_roundtrip_preserves_data(self):
        ticket = _ticket()
        out = export_tickets([ticket], format="xlsx")
        df = pd.read_excel(io.BytesIO(out))
        assert df.iloc[0]["id_ticket"] == ticket["id_ticket"]
        assert df.iloc[0]["titulo_sugerido"] == ticket["titulo_sugerido"]

    def test_preserves_accents(self):
        ticket = _ticket()
        ticket["tipo_itil"] = "Requisição"
        out = export_tickets([ticket], format="xlsx")
        df = pd.read_excel(io.BytesIO(out))
        assert df.iloc[0]["tipo_itil"] == "Requisição"

    def test_flattens_nested_dict_field(self):
        ticket = _ticket()
        ticket["descricao_enriquecida"] = {
            "objetivo": "resolver a falha",
            "requisicoes": None,
        }
        out = export_tickets([ticket], format="xlsx")
        df = pd.read_excel(io.BytesIO(out))
        assert (
            json.loads(df.iloc[0]["descricao_enriquecida"])
            == ticket["descricao_enriquecida"]
        )

    def test_empty_list_returns_valid_empty_file(self):
        out = export_tickets([], format="xlsx")
        df = pd.read_excel(io.BytesIO(out))
        assert len(df) == 0
