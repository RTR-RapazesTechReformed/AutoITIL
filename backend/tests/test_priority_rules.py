"""Tests for PriorityRules."""

import json
from pathlib import Path

import pytest

from app.tickets.priority_rules import PriorityRules


def _write_rules(tmp_path: Path, data: dict) -> Path:
    path = tmp_path / "priority_rules.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


class TestPriorityRules:
    def test_load_from_file(self, tmp_path):
        path = _write_rules(
            tmp_path,
            {
                "rules": {"Incidente": "P1", "Problema": "P2"},
                "fallback": "P3",
            },
        )
        rules = PriorityRules.from_json(path)
        assert rules.priority_for("Incidente") == "P1"
        assert rules.priority_for("Problema") == "P2"

    def test_returns_fallback_for_unknown_type(self, tmp_path):
        path = _write_rules(tmp_path, {"rules": {"Incidente": "P1"}, "fallback": "P3"})
        rules = PriorityRules.from_json(path)
        assert rules.priority_for("Inexistente") == "P3"

    def test_default_path_loads_repo_file(self):
        rules = PriorityRules.from_json()
        assert rules.priority_for("Incidente") == "P1"
        assert rules.priority_for("Mudança") == "P4"
        assert rules.priority_for("classe inexistente") == "P3"

    def test_missing_file_raises_helpful_error(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            PriorityRules.from_json(tmp_path / "naoexiste.json")
