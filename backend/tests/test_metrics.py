"""Tests for evaluate_model."""

import pytest

from app.evaluation.metrics import evaluate_model


class TestEvaluateModel:
    def test_returns_dict_with_macro_f1(self):
        y_true = ["Incidente", "Requisição", "Incidente", "Mudança"]
        y_pred = ["Incidente", "Requisição", "Incidente", "Mudança"]
        result = evaluate_model(y_true, y_pred, level="nivel1", model_name="bert")
        assert result["model_name"] == "bert"
        assert result["level"] == "nivel1"
        assert result["macro_f1"] == 1.0

    def test_returns_per_class_metrics(self):
        y_true = ["A", "A", "B", "B"]
        y_pred = ["A", "B", "B", "B"]
        result = evaluate_model(y_true, y_pred, level="nivel1", model_name="bert")
        assert "per_class" in result
        assert "A" in result["per_class"]
        assert "B" in result["per_class"]
        for cls in ("A", "B"):
            for k in ("precision", "recall", "f1-score", "support"):
                assert k in result["per_class"][cls]

    def test_returns_weighted_avg(self):
        y_true = ["A", "B", "A", "B"]
        y_pred = ["A", "B", "B", "B"]
        result = evaluate_model(y_true, y_pred, level="nivel1", model_name="bert")
        assert "weighted_avg" in result
        assert "f1-score" in result["weighted_avg"]

    def test_handles_zero_division(self):
        y_true = ["A", "A", "A"]
        y_pred = ["B", "B", "B"]  # class B never in y_true, A never predicted
        result = evaluate_model(y_true, y_pred, level="nivel1", model_name="bert")
        assert result["macro_f1"] == 0.0  # zero_division=0

    def test_rejects_invalid_level(self):
        with pytest.raises(ValueError, match="level"):
            evaluate_model(["A"], ["A"], level="nivel3", model_name="bert")  # type: ignore[arg-type]

    def test_mismatched_lengths_raises(self):
        with pytest.raises(ValueError):
            evaluate_model(["A", "B"], ["A"], level="nivel1", model_name="bert")
