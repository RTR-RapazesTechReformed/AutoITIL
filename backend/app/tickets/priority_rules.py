"""
priority_rules.py — carrega e consulta a tabela de prioridades ITIL.

Responsabilidade: ler `data/config/priority_rules.json` e responder a
consultas de prioridade por tipo ITIL, com fallback para casos não mapeados.

Formato do arquivo:
    {
        "rules": {"Incidente": "P1", "Problema": "P2", ...},
        "fallback": "P3"
    }
"""

from __future__ import annotations

import json
from pathlib import Path

DEFAULT_PATH = Path("data/config/priority_rules.json")


class PriorityRules:
    """Mapeia tipo ITIL → prioridade, com fallback para tipos desconhecidos."""

    def __init__(self, rules: dict[str, str], fallback: str) -> None:
        self._rules = rules
        self._fallback = fallback

    @classmethod
    def from_json(cls, path: Path | None = None) -> PriorityRules:
        """Carrega a tabela a partir de um arquivo JSON."""
        path = Path(path) if path is not None else DEFAULT_PATH
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
        return cls(rules=data["rules"], fallback=data["fallback"])

    def priority_for(self, tipo_itil: str) -> str:
        """Retorna a prioridade do tipo, ou o fallback se não mapeado."""
        return self._rules.get(tipo_itil, self._fallback)
