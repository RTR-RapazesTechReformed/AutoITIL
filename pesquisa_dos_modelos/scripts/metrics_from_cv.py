"""
metrics_from_cv.py — monta metrics_report.json a partir dos resultados de
validação cruzada já calculados pelos notebooks de treino
(`pesquisa_dos_modelos/notebooks/*_cv_results.json`).

Não depende de código do backend (nenhum import de `app.*`) — só agrega
JSON já produzido pelos notebooks. Preferível a rodar inferência ao vivo:
não exige CSV de validação nem reexecuta os modelos, e usa predições
out-of-fold — mais honesto do que avaliar um modelo final (treinado em
100% dos dados) contra os próprios dados de treino.

Uso (a partir de pesquisa_dos_modelos/):
    python -m scripts.metrics_from_cv \
        --output ../backend/data/processed/metrics_report.json
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

DEFAULT_OUTPUT = Path("../backend/data/processed/metrics_report.json")

CV_RESULTS_FILES = {
    ("nivel1", "svm_baseline"): "notebooks/svm_nivel1_cv_results.json",
    ("nivel1", "bert"): "notebooks/bert_nivel1_cv_results.json",
    ("nivel2", "svm_baseline"): "notebooks/svm_nivel2_cv_results.json",
    ("nivel2", "bert"): "notebooks/bert_nivel2_cv_results.json",
}


def _report_from_cv_json(cv_data: dict, model_name: str, level: str) -> dict:
    """Converte um `*_cv_results.json` (OOF de validação cruzada) para o
    formato de relatório de métricas, sem re-rodar inferência nos modelos.
    """
    per_class = dict(cv_data["oof_classification_report"])
    macro_avg = per_class.pop("macro avg")
    weighted_avg = per_class.pop("weighted avg")
    per_class.pop("accuracy", None)

    return {
        "model_name": model_name,
        "level": level,
        "macro_f1": cv_data.get("f1_macro_mean", round(macro_avg["f1-score"], 4)),
        "macro_f1_std": cv_data.get("f1_macro_std"),
        "n_folds": cv_data.get("n_folds"),
        "macro_avg": macro_avg,
        "weighted_avg": weighted_avg,
        "per_class": per_class,
    }


def build_report_from_cv_results(
    base_dir: Path | None = None,
    output_path: Path | None = None,
) -> dict:
    base_dir = Path(base_dir) if base_dir is not None else Path(".")

    report: dict = {
        "generated_at": datetime.now(UTC).isoformat(),
        "source": "cv_results",
        "nivel1": {},
        "nivel2": {},
    }

    for (level, model_name), rel_path in CV_RESULTS_FILES.items():
        path = base_dir / rel_path
        if not path.exists():
            continue
        cv_data = json.loads(path.read_text(encoding="utf-8"))
        report[level][model_name] = _report_from_cv_json(cv_data, model_name, level)

    if output_path is not None and (report["nivel1"] or report["nivel2"]):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Monta metrics_report.json a partir dos *_cv_results.json."
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    report = build_report_from_cv_results(output_path=args.output)
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
