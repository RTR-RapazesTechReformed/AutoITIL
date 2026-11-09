"""
classifier.py — módulo de classificação de tickets para AutoITIL.

Responsabilidade: carregar o modelo treinado (TF-IDF + LinearSVC) e
classificar textos pré-processados pelo TextCleaner.

Design:
- Classe Classifier segue o padrão stateless do projeto.
- Graceful degradation: se o modelo não estiver treinado, is_trained()
  retorna False e os métodos predict/predict_batch retornam None.
- Singleton de pipeline via _pipeline_cache para evitar leitura repetida
  do disco a cada requisição.

Uso:
    classifier = Classifier()

    if classifier.is_trained():
        result = classifier.predict("vpn escritorio caiu")
        # → {"categoria": "Incidente", "confianca": 0.91}

    batch = classifier.predict_batch(["vpn caiu", "solicito acesso erp"])
    # → [{"categoria": "Incidente", ...}, {"categoria": "Requisição", ...}]
"""

from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
from sklearn.pipeline import Pipeline

MODELS_DIR = Path("models/baseline")
MODEL_PATH = MODELS_DIR / "svm.pkl"

LABELS = ["Incidente", "Requisição", "Problema", "Mudança"]

_pipeline_cache: Pipeline | None = None


def _load_pipeline() -> Pipeline | None:
    global _pipeline_cache
    if _pipeline_cache is None:
        if not MODEL_PATH.exists():
            return None
        _pipeline_cache = joblib.load(MODEL_PATH)
    return _pipeline_cache


class Classifier:
    """
    Classifier — classifica tickets de TI nas categorias ITIL usando TF-IDF + LinearSVC.

    O modelo é carregado de models/baseline/svm.pkl e mantido em cache na
    memória do processo. Suporta classificação individual e em lote (batch).

    Graceful degradation: quando o modelo não está treinado (arquivo .pkl
    ausente), is_trained() retorna False e os métodos de predição retornam None,
    permitindo que a aplicação continue funcionando sem classificação.

    Exemplo:
        classifier = Classifier()

        if classifier.is_trained():
            resultado = classifier.predict("vpn escritorio caiu")
            # → {"categoria": "Incidente", "confianca": 0.91}
    """

    def is_trained(self) -> bool:
        """Verifica se o modelo treinado está disponível em disco."""
        return MODEL_PATH.exists()

    def predict(self, text: str) -> dict | None:
        """
        Classifica um único texto pré-processado.

        Args:
            text: Texto já limpo pelo TextCleaner.

        Returns:
            Dict com 'categoria' e 'confianca', ou None se modelo não treinado.
        """
        pipeline = _load_pipeline()
        if pipeline is None:
            return None

        proba = pipeline.predict_proba([text])[0]
        idx = int(np.argmax(proba))
        classes = pipeline.classes_

        return {
            "categoria": classes[idx],
            "confianca": round(float(proba[idx]), 4),
        }

    def predict_batch(self, texts: list[str]) -> list[dict] | None:
        """
        Classifica uma lista de textos. Mais eficiente que chamar predict() em loop.

        Args:
            texts: Lista de textos já limpos pelo TextCleaner.

        Returns:
            Lista de dicts com 'categoria' e 'confianca', ou None se modelo não treinado.
        """
        pipeline = _load_pipeline()
        if pipeline is None:
            return None

        probas = pipeline.predict_proba(texts)
        classes = pipeline.classes_

        results = []
        for proba in probas:
            idx = int(np.argmax(proba))
            results.append(
                {
                    "categoria": classes[idx],
                    "confianca": round(float(proba[idx]), 4),
                }
            )
        return results
