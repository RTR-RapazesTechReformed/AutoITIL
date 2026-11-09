"""bake_models.py — baixa os pesos ML em build-time da imagem Docker.

Roda uma vez durante `docker build` (ver backend/Dockerfile), populando os
mesmos caminhos que BertClassifier/DescriptionEnricher/TextCleaner checam
em request-time (ver app/classification/bert_classifier.py,
app/enrichment/enricher.py, app/preprocessing/cleaner.py) — assim nenhum
download acontece na primeira requisição em produção.

Uso: python -m scripts.bake_models
(precisa do -m: cwd precisa estar no sys.path pra `from app... import`
funcionar, e os paths relativos como "models/bert/nivel1" resolverem
igual ao resto da app — ver app/api/routes.py:59-63)
"""

from __future__ import annotations

from pathlib import Path

import nltk
import torch
from huggingface_hub import snapshot_download
from transformers import AutoModelForCausalLM, AutoTokenizer

from app.config.settings import BERT_N1_HUB_REPO, BERT_N2_HUB_REPO, ENRICHMENT_MODEL


def bake_bert(hub_repo_id: str, model_dir: Path) -> None:
    if (model_dir / "config.json").exists():
        print(f"[bake] {model_dir} já existe, pulando download.")
        return
    print(f"[bake] baixando {hub_repo_id} -> {model_dir}")
    snapshot_download(repo_id=hub_repo_id, local_dir=model_dir)


def bake_enricher(model_name: str) -> None:
    print(f"[bake] baixando {model_name} (tokenizer + modelo)")
    AutoTokenizer.from_pretrained(model_name)
    AutoModelForCausalLM.from_pretrained(model_name, torch_dtype=torch.float32)


def bake_nltk() -> None:
    print("[bake] baixando corpus NLTK 'stopwords'")
    nltk.download("stopwords", quiet=True)


def main() -> None:
    bake_bert(BERT_N1_HUB_REPO, Path("models/bert/nivel1"))
    bake_bert(BERT_N2_HUB_REPO, Path("models/bert/nivel2"))
    bake_enricher(ENRICHMENT_MODEL)
    bake_nltk()
    print("[bake] concluído.")


if __name__ == "__main__":
    main()
