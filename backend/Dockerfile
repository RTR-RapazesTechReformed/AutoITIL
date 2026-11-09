# ---- Stage 1: builder — instala dependências Python num venv isolado ----
FROM python:3.12-slim AS builder

WORKDIR /app

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Wheel CPU-only do PyTorch primeiro — evita puxar dependências CUDA que não
# são usadas (instâncias AWS planejadas não têm GPU).
COPY requirements.txt .
RUN pip install --no-cache-dir torch==2.5.0 --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt

# ---- Stage 2: imagem final ----
FROM python:3.12-slim

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copia só o necessário pro bake (scripts/ + app/config/, que tem as
# constantes BERT_N1_HUB_REPO/BERT_N2_HUB_REPO/ENRICHMENT_MODEL) antes do
# resto de app/ — evita invalidar o layer de bake (~1.8GB de download) a
# cada mudança de código de aplicação não relacionada aos modelos.
COPY app/__init__.py app/__init__.py
COPY app/config/ app/config/
COPY scripts/ scripts/

# ENRICHMENT_MODEL (google/gemma-3-1b-it) é gated no Hugging Face — exige
# um HF_TOKEN autenticado com a licença do modelo aceita. huggingface_hub/
# transformers leem HF_TOKEN do ambiente automaticamente, então só precisa
# chegar como variável de ambiente neste estágio do build (ver README pra
# como obter o token e aceitar a licença).
ARG HF_TOKEN

# Baixa os pesos ML e o corpus NLTK em build-time, não em request-time —
# ver Task 1 (backend/scripts/bake_models.py) e o design em
#
# HF_TOKEN só precisa existir durante este RUN (não como ENV persistente
# na imagem final — evita expor o token no ambiente de todo container que
# rodar essa imagem depois).
RUN HF_TOKEN=$HF_TOKEN python -m scripts.bake_models

COPY app/ app/
COPY data/ data/
# SVM fallback (backend/models/baseline/*.pkl) — usado por
# app/classification/cascade.py quando BERT não está disponível; ver C1.
COPY models/baseline/ models/baseline/

HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health', timeout=2)" || exit 1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
