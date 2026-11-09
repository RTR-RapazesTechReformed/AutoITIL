"""
generator.py — gera tickets estruturados a partir da classificação ITIL.

Responsabilidade: combinar a linha original do CSV com o resultado do
CascadeClassifier para produzir um ticket completo (id, título, tipo,
área, prioridade, datas).

Contrato do ticket:
{
    "id_ticket": "TCK-0001",
    "titulo_sugerido": "...",
    "tipo_itil": "Incidente",
    "area_responsavel": "Rede",
    "prioridade": "P1",
    "descricao_original": "...",
    "data_geracao": "2026-06-10T12:34:56+00:00",
    "id_origem": "T001",
    "confianca_n1": 0.92,
    "confianca_n2": 0.88,
}
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.tickets.priority_rules import PriorityRules

TITLE_MAX_CHARS = 80


def _build_title(descricao: str, nivel1: str) -> str:
    prefix = descricao[:TITLE_MAX_CHARS]
    return f"{prefix} — {nivel1}"


def generate_ticket(
    row: dict,
    classification: dict,
    rules: PriorityRules,
    ticket_counter: int,
) -> dict:
    """
    Gera um ticket estruturado a partir da classificação em cascata.

    Args:
        row: Linha original do CSV (precisa ter 'id' e 'descricao').
        classification: Saída do CascadeClassifier.classify().
        rules: Tabela de prioridades carregada.
        ticket_counter: Número sequencial do ticket (1-based).

    Returns:
        Dict com a estrutura completa do ticket.
    """
    nivel1 = classification["nivel1"]
    return {
        "id_ticket": f"TCK-{ticket_counter:04d}",
        "titulo_sugerido": _build_title(row["descricao"], nivel1),
        "tipo_itil": nivel1,
        "area_responsavel": classification["nivel2"],
        "prioridade": rules.priority_for(nivel1),
        "descricao_original": row["descricao"],
        "data_geracao": datetime.now(UTC).isoformat(),
        "id_origem": row["id"],
        "confianca_n1": classification["confianca_n1"],
        "confianca_n2": classification["confianca_n2"],
    }
