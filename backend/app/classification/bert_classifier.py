"""
bert_classifier.py — classificador BERT genérico para um nível ITIL.

Responsabilidade: carregar um modelo HuggingFace fine-tuned (tipicamente
BERTimbau) do disco e expor predição individual seguindo o mesmo contrato
do Classifier SVM existente: dict com chaves 'categoria' e 'confianca'.

Design:
- Cada instância encapsula um único modelo (ex.: nivel1 ou nivel2).
- Carregamento lazy: tokenizer e modelo só são lidos do disco na primeira
  chamada de predict(), evitando custo na inicialização da aplicação.
- Graceful degradation: se o diretório do modelo não existir,
  is_trained() retorna False e predict() retorna None — espelhando o
  comportamento do Classifier SVM para uso uniforme pela camada de API.

Uso:
    clf = BertClassifier(model_dir=Path("models/bert/nivel1"))

    if clf.is_trained():
        resultado = clf.predict("vpn escritorio caiu")
        # → {"categoria": "Incidente", "confianca": 0.91}

Os pesos fine-tuned são pesados demais para o repositório git, então também
podem ser hospedados no Hugging Face Hub: se `model_dir` não existir
localmente e um `hub_repo_id` for informado, o snapshot é baixado do Hub
(e fica cacheado em `model_dir`) na primeira chamada de predict().
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

import torch
from huggingface_hub import snapshot_download
from transformers import AutoModelForSequenceClassification, AutoTokenizer

MAX_LENGTH = 192

logger = logging.getLogger(__name__)


class BertClassifier:
    """
    BertClassifier — classifica tickets de TI usando um modelo BERT fine-tuned.

    Cada instância carrega exatamente 1 modelo HuggingFace a partir de
    `model_dir`. O carregamento é lazy: o modelo só vai para a memória na
    primeira chamada de predict(), e é mantido em cache na instância para
    chamadas subsequentes (idempotência garantida por _load()).

    O retorno de predict() segue o contrato {'categoria', 'confianca'},
    idêntico ao do Classifier SVM, permitindo uso intercambiável pela
    camada de API.

    Graceful degradation: quando o diretório do modelo não contém um
    config.json válido, is_trained() retorna False e predict() retorna
    None, permitindo que a aplicação continue funcionando sem
    classificação BERT.

    Exemplo:
        clf = BertClassifier(model_dir=Path("models/bert/nivel1"))

        if clf.is_trained():
            resultado = clf.predict("vpn escritorio caiu")
            # → {"categoria": "Incidente", "confianca": 0.91}
    """

    def __init__(self, model_dir: Path, hub_repo_id: str | None = None) -> None:
        self.model_dir = Path(model_dir)
        self.hub_repo_id = hub_repo_id
        self._tokenizer = None
        self._model = None
        self._load_failed = False
        # Telemetria da última chamada — mesmo contrato de
        # DescriptionEnricher: o chamador (rota) lê e persiste, o
        # classificador não conhece banco. None até a primeira predição
        # bem-sucedida.
        self.last_call_duracao_ms: float | None = None
        self.last_call_tokens_entrada: int | None = None
        self.last_call_itens: int | None = None

    def is_trained(self) -> bool:
        """Verifica se há um modelo treinado disponível localmente ou no Hub."""
        if self._load_failed:
            return False
        return (self.model_dir / "config.json").exists() or self.hub_repo_id is not None

    def _load(self) -> None:
        """Carrega tokenizer e modelo apenas na primeira chamada.

        Baixa do Hugging Face Hub para `model_dir` se ainda não estiver em disco.
        """
        if self._model is not None or self._load_failed:
            return
        try:
            if not (self.model_dir / "config.json").exists() and self.hub_repo_id:
                snapshot_download(repo_id=self.hub_repo_id, local_dir=self.model_dir)
            self._tokenizer = AutoTokenizer.from_pretrained(str(self.model_dir))
            self._model = AutoModelForSequenceClassification.from_pretrained(
                str(self.model_dir)
            )
            self._model.eval()
        except Exception as exc:
            logger.warning(
                "BERT indisponível (model_dir=%s, hub_repo_id=%s): %s. "
                "Seguindo sem este nível — a cascata usa o fallback SVM.",
                self.model_dir,
                self.hub_repo_id,
                exc,
            )
            self._load_failed = True
            self._tokenizer = None
            self._model = None

    def predict(self, text: str) -> dict | None:
        """
        Classifica um único texto usando o modelo BERT fine-tuned.

        Dispara o carregamento lazy do modelo na primeira chamada.

        Args:
            text: Texto a ser classificado (pode ser bruto; o tokenizer
                do HuggingFace cuida da normalização).

        Returns:
            Dict com 'categoria' (label do id2label do modelo) e
            'confianca' (probabilidade softmax arredondada a 4 casas),
            ou None se o modelo não estiver treinado.
        """
        if not self.is_trained():
            return None
        self._load()
        if self._model is None or self._tokenizer is None:
            return None

        start = time.perf_counter()
        inputs = self._tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            padding=True,
            max_length=MAX_LENGTH,
        )
        with torch.no_grad():
            logits = self._model(**inputs).logits

        probs = torch.softmax(logits, dim=-1)[0]
        idx = int(torch.argmax(probs).item())
        label = self._model.config.id2label[idx]

        self.last_call_duracao_ms = (time.perf_counter() - start) * 1000
        self.last_call_tokens_entrada = int(inputs["input_ids"].numel())
        self.last_call_itens = 1

        return {
            "categoria": label,
            "confianca": round(float(probs[idx].item()), 4),
        }

    def predict_batch(self, texts: list[str]) -> list[dict] | None:
        """
        Classifica uma lista de textos. Mais eficiente que chamar predict() em loop.

        Args:
            texts: Lista de textos já limpos pelo TextCleaner.

        Returns:
            Lista de dicts com 'categoria' e 'confianca', ou None se modelo não treinado.
        """
        if not self.is_trained():
            return None
        self._load()
        if self._model is None or self._tokenizer is None:
            return None

        start = time.perf_counter()
        inputs = self._tokenizer(
            texts,
            return_tensors="pt",
            truncation=True,
            padding=True,
            max_length=MAX_LENGTH,
        )
        with torch.no_grad():
            logits = self._model(**inputs).logits

        probs = torch.softmax(logits, dim=-1)
        id2label = self._model.config.id2label

        self.last_call_duracao_ms = (time.perf_counter() - start) * 1000
        # numel() e não shape[1]: com padding o tensor é (lote, maior_seq), e
        # o total de tokens realmente processados pelo modelo é o produto.
        self.last_call_tokens_entrada = int(inputs["input_ids"].numel())
        self.last_call_itens = len(texts)

        results = []
        for row in probs:
            idx = int(torch.argmax(row).item())
            results.append(
                {
                    "categoria": id2label[idx],
                    "confianca": round(float(row[idx].item()), 4),
                }
            )
        return results
