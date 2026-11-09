"""Tests for the avaliar_modelos CLI script's core function."""

import json
from pathlib import Path

import pandas as pd

from scripts.avaliar_modelos import build_report


def _make_csv(tmp_path: Path, rows: list[dict]) -> Path:
    path = tmp_path / "valid.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def test_build_report_with_nivel1_only(tmp_path):
    csv_path = _make_csv(
        tmp_path,
        [
            {"descricao_limpa": "vpn caiu", "categoria": "Incidente"},
            {"descricao_limpa": "acesso erp", "categoria": "Requisição"},
        ],
    )

    def fake_predict_n1(texts):
        return ["Incidente", "Requisição"]

    def fake_predict_svm(texts):
        return ["Incidente", "Incidente"]

    report = build_report(
        csv_path,
        predict_bert_n1=fake_predict_n1,
        predict_bert_n2=None,
        predict_svm_n1=fake_predict_svm,
    )

    assert "nivel1" in report
    assert "bert" in report["nivel1"]
    assert "svm_baseline" in report["nivel1"]
    assert report["nivel1"]["bert"]["macro_f1"] == 1.0
    assert report["nivel1"]["svm_baseline"]["macro_f1"] < 1.0
    assert "nivel2" not in report or report["nivel2"] == {}


def test_build_report_with_both_levels(tmp_path):
    csv_path = _make_csv(
        tmp_path,
        [
            {"descricao_limpa": "vpn caiu", "categoria": "Incidente", "nivel2": "Rede"},
            {
                "descricao_limpa": "erp lento",
                "categoria": "Problema",
                "nivel2": "Aplicações",
            },
        ],
    )
    report = build_report(
        csv_path,
        predict_bert_n1=lambda texts: ["Incidente", "Problema"],
        predict_bert_n2=lambda texts: ["Rede", "Aplicações"],
        predict_svm_n1=lambda texts: ["Incidente", "Problema"],
    )

    assert "nivel2" in report
    assert "bert" in report["nivel2"]
    assert report["nivel2"]["bert"]["macro_f1"] == 1.0
    # SVM has no nivel2 — should not appear under nivel2
    assert "svm_baseline" not in report["nivel2"]


def test_build_report_writes_json(tmp_path):
    csv_path = _make_csv(
        tmp_path,
        [{"descricao_limpa": "x", "categoria": "Incidente"}],
    )
    output = tmp_path / "report.json"
    build_report(
        csv_path,
        predict_bert_n1=lambda texts: ["Incidente"],
        predict_bert_n2=None,
        predict_svm_n1=lambda texts: ["Incidente"],
        output_path=output,
    )
    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["nivel1"]["bert"]["macro_f1"] == 1.0
    assert "generated_at" in data
