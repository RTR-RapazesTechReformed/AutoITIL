"""
metrics.py — avaliação comparativa de classificadores ITIL.

Responsabilidade: calcular precision/recall/F1 por classe + macro/weighted
avg usando sklearn.classification_report, num formato JSON serializável.
Permite comparar BERT vs baseline SVM nos níveis 1 e 2.
"""

from __future__ import annotations

from typing import Literal

from sklearn.metrics import classification_report

Level = Literal["nivel1", "nivel2"]
VALID_LEVELS = ("nivel1", "nivel2")


def evaluate_model(
    y_true: list[str],
    y_pred: list[str],
    level: Level,
    model_name: str,
) -> dict:
    """
    Calcula métricas de classificação para um modelo num nível ITIL.

    Args:
        y_true: Labels verdadeiros.
        y_pred: Labels preditos pelo modelo.
        level: "nivel1" ou "nivel2".
        model_name: Identificador do modelo (ex: "bert", "svm_baseline").

    Returns:
        Dict com: model_name, level, macro_f1, per_class, macro_avg, weighted_avg.

    Raises:
        ValueError: se level inválido ou tamanhos diferentes.
    """
    if level not in VALID_LEVELS:
        raise ValueError(f"level inválido: {level!r}. Use {VALID_LEVELS}.")
    if len(y_true) != len(y_pred):
        raise ValueError(
            f"y_true e y_pred têm tamanhos diferentes: {len(y_true)} vs {len(y_pred)}"
        )

    report = classification_report(y_true, y_pred, output_dict=True, zero_division=0)

    macro_avg = report.pop("macro avg")
    weighted_avg = report.pop("weighted avg")
    report.pop("accuracy", None)

    return {
        "model_name": model_name,
        "level": level,
        "macro_f1": round(macro_avg["f1-score"], 4),
        "macro_avg": macro_avg,
        "weighted_avg": weighted_avg,
        "per_class": report,
    }
