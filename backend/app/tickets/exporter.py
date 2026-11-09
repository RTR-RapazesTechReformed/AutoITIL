"""
exporter.py — serializa lista de tickets em JSON, CSV ou XLSX.

Responsabilidade: converter a lista de tickets (gerada por generate_ticket()
OU lida do banco via export_tickets_rows()) em bytes prontos para download
(HTTP response ou st.download_button do Streamlit). Sem escrita em disco.
"""

from __future__ import annotations

import csv
import io
import json
from typing import Literal

import pandas as pd

ExportFormat = Literal["json", "csv", "xlsx"]


_FORMULA_PREFIXES = ("=", "+", "-", "@")


def _sanitize_csv_value(value):
    """Mitiga CSV/formula injection: se o valor for string e começar com um
    dos caracteres que Excel/LibreOffice interpretam como início de fórmula
    (=, +, -, @), prefixa com aspa simples pra forçar interpretação como
    texto puro. Aspas em CSV não protegem contra isso — a mitigação precisa
    ser no conteúdo. Valores não-string (int, float, None, bool) não mudam."""
    if isinstance(value, str) and value.startswith(_FORMULA_PREFIXES):
        return "'" + value
    return value


def _flatten_for_tabular(tickets: list[dict]) -> list[dict]:
    """CSV/XLSX não representam valor aninhado numa célula — achata qualquer
    campo dict (ex.: descricao_enriquecida, vindo de export_tickets_rows) pra
    uma string JSON. Campos escalares (str/int/float/None) passam direto.
    Strings (incluindo as vindas do achatamento de dict) que comecem com
    =, +, - ou @ são sanitizadas contra CSV injection (ver
    _sanitize_csv_value). Não muda os dicts originais (lista nova)."""
    return [
        {
            k: _sanitize_csv_value(
                json.dumps(v, ensure_ascii=False) if isinstance(v, dict) else v
            )
            for k, v in t.items()
        }
        for t in tickets
    ]


def export_tickets(tickets: list[dict], format: ExportFormat) -> bytes:
    """
    Serializa a lista de tickets para JSON, CSV ou XLSX.

    Args:
        tickets: Lista de dicts (de generate_ticket() ou export_tickets_rows()).
        format: "json", "csv" ou "xlsx".

    Returns:
        Conteúdo serializado em bytes.

    Raises:
        ValueError: se format não for "json", "csv" nem "xlsx".
    """
    if format == "json":
        return json.dumps(tickets, indent=2, ensure_ascii=False).encode("utf-8")
    if format == "csv":
        if not tickets:
            return b""
        flat = _flatten_for_tabular(tickets)
        buffer = io.StringIO()
        fieldnames = list(flat[0].keys())
        writer = csv.DictWriter(buffer, fieldnames=fieldnames)
        writer.writeheader()
        for t in flat:
            writer.writerow(t)
        return buffer.getvalue().encode("utf-8")
    if format == "xlsx":
        flat = _flatten_for_tabular(tickets)
        buffer = io.BytesIO()
        pd.DataFrame(flat).to_excel(buffer, index=False, engine="openpyxl")
        return buffer.getvalue()
    raise ValueError(f"format inválido: {format!r}. Use 'json', 'csv' ou 'xlsx'.")
