"""Tests for metrics_from_cv.build_report_from_cv_results."""

import json
from pathlib import Path

from scripts.metrics_from_cv import build_report_from_cv_results


def _make_cv_json(path: Path, f1_mean: float, f1_std: float, n_folds: int = 5) -> None:
    cv_data = {
        "n_folds": n_folds,
        "f1_macro_per_fold": [f1_mean] * n_folds,
        "f1_macro_mean": f1_mean,
        "f1_macro_std": f1_std,
        "oof_classification_report": {
            "Incidente": {
                "precision": 0.9,
                "recall": 0.9,
                "f1-score": 0.9,
                "support": 10.0,
            },
            "Requisição": {
                "precision": 0.8,
                "recall": 0.8,
                "f1-score": 0.8,
                "support": 10.0,
            },
            "accuracy": 0.85,
            "macro avg": {
                "precision": 0.85,
                "recall": 0.85,
                "f1-score": f1_mean,
                "support": 20.0,
            },
            "weighted avg": {
                "precision": 0.85,
                "recall": 0.85,
                "f1-score": 0.85,
                "support": 20.0,
            },
        },
    }
    path.write_text(json.dumps(cv_data, ensure_ascii=False), encoding="utf-8")


class TestBuildReportFromCvResults:
    def test_assembles_report_from_available_cv_files(self, tmp_path):
        notebooks_dir = tmp_path / "notebooks"
        notebooks_dir.mkdir()
        _make_cv_json(notebooks_dir / "svm_nivel1_cv_results.json", 0.91, 0.02)
        _make_cv_json(notebooks_dir / "bert_nivel1_cv_results.json", 0.96, 0.01)

        report = build_report_from_cv_results(base_dir=tmp_path)

        assert report["nivel1"]["svm_baseline"]["macro_f1"] == 0.91
        assert report["nivel1"]["bert"]["macro_f1"] == 0.96
        assert "macro avg" not in report["nivel1"]["bert"]["per_class"]
        assert "accuracy" not in report["nivel1"]["bert"]["per_class"]
        assert report["nivel1"]["bert"]["per_class"]["Incidente"]["f1-score"] == 0.9
        assert report["nivel2"] == {}

    def test_missing_files_are_skipped_not_errors(self, tmp_path):
        report = build_report_from_cv_results(base_dir=tmp_path)

        assert report["nivel1"] == {}
        assert report["nivel2"] == {}

    def test_writes_output_only_when_report_has_content(self, tmp_path):
        output = tmp_path / "metrics_report.json"

        build_report_from_cv_results(base_dir=tmp_path, output_path=output)
        assert not output.exists()

        notebooks_dir = tmp_path / "notebooks"
        notebooks_dir.mkdir()
        _make_cv_json(notebooks_dir / "bert_nivel2_cv_results.json", 0.80, 0.03)

        build_report_from_cv_results(base_dir=tmp_path, output_path=output)
        assert output.exists()
        data = json.loads(output.read_text(encoding="utf-8"))
        assert data["nivel2"]["bert"]["macro_f1"] == 0.80
        assert data["source"] == "cv_results"
