"""
avaliar_modelos.py — CLI para gerar relatório comparativo BERT vs SVM
rodando os classificadores de produção contra um CSV de validação rotulado.

Lê um CSV de validação rotulado, roda os classificadores disponíveis
contra a coluna texto_limpo, e produz metrics_report.json comparando
F1 macro por nível e por classe.

Uso (a partir de backend/):
    python -m scripts.avaliar_modelos \\
        --csv data/processed/validacao.csv \\
        --output data/processed/metrics_report.json

Para montar o relatório a partir dos resultados de validação cruzada dos
notebooks (sem rodar inferência ao vivo), ver
`pesquisa_dos_modelos/scripts/metrics_from_cv.py`.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from app.evaluation.metrics import evaluate_model

PredictFn = Callable[[list[str]], list[str]]

DEFAULT_OUTPUT = Path("data/processed/metrics_report.json")


def build_report(
    csv_path: Path,
    *,
    predict_bert_n1: PredictFn | None,
    predict_bert_n2: PredictFn | None,
    predict_svm_n1: PredictFn | None,
    output_path: Path | None = None,
) -> dict:
    df = pd.read_csv(csv_path)
    texts = df["descricao_limpa"].astype(str).tolist()

    report: dict = {
        "generated_at": datetime.now(UTC).isoformat(),
        "nivel1": {},
        "nivel2": {},
    }

    if "categoria" in df.columns:
        y_true_n1 = df["categoria"].astype(str).tolist()
        if predict_bert_n1 is not None:
            report["nivel1"]["bert"] = evaluate_model(
                y_true_n1, predict_bert_n1(texts), level="nivel1", model_name="bert"
            )
        if predict_svm_n1 is not None:
            report["nivel1"]["svm_baseline"] = evaluate_model(
                y_true_n1,
                predict_svm_n1(texts),
                level="nivel1",
                model_name="svm_baseline",
            )

    if "nivel2" in df.columns and predict_bert_n2 is not None:
        y_true_n2 = df["nivel2"].astype(str).tolist()
        report["nivel2"]["bert"] = evaluate_model(
            y_true_n2, predict_bert_n2(texts), level="nivel2", model_name="bert"
        )

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    return report


def _real_predict_bert(model_dir: str) -> PredictFn | None:
    from pathlib import Path as _P

    from app.classification.bert_classifier import BertClassifier

    clf = BertClassifier(model_dir=_P(model_dir))
    if not clf.is_trained():
        return None

    def fn(texts: list[str]) -> list[str]:
        results = clf.predict_batch(texts)
        return [r["categoria"] for r in results]

    return fn


def _real_predict_svm() -> PredictFn | None:
    from app.classification.classifier import Classifier

    clf = Classifier()
    if not clf.is_trained():
        return None

    def fn(texts: list[str]) -> list[str]:
        results = clf.predict_batch(texts)
        return [r["categoria"] for r in results]

    return fn


def main() -> None:
    parser = argparse.ArgumentParser(description="Avalia BERT vs SVM em CSV rotulado.")
    parser.add_argument("--csv", required=True, type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--bert-n1", default="models/bert/nivel1")
    parser.add_argument("--bert-n2", default="models/bert/nivel2")
    args = parser.parse_args()

    report = build_report(
        args.csv,
        predict_bert_n1=_real_predict_bert(args.bert_n1),
        predict_bert_n2=_real_predict_bert(args.bert_n2),
        predict_svm_n1=_real_predict_svm(),
        output_path=args.output,
    )

    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
