import os

MAX_ROWS = 5000

MAX_UPLOAD_BYTES = 10 * 1024 * 1024

SUPPORTED_EXTENSIONS = [".csv", ".xlsx"]

# Pesos BERT fine-tuned hospedados no Hugging Face Hub (fallback quando
# models/bert/nivelX não existe localmente, ex.: clone novo do repo).
BERT_N1_HUB_REPO = "EdsonMorro/autoitil-bert-nivel1"
BERT_N2_HUB_REPO = "EdsonMorro/autoitil-bert-nivel2"

# F2-4 — modelo pequeno usado para reescrever a descrição de um ticket de
# forma mais legível, sob demanda (ver app.enrichment.enricher). Gemma 3 1B
# é gated no Hub (exige aceitar a licença + HF_TOKEN autenticado antes de
# baixar) — resolvido via variável de ambiente HF_TOKEN, lida automaticamente
# por transformers/huggingface_hub tanto em dev local (lazy load em
# request-time) quanto no build da imagem Docker (ver backend/Dockerfile e
# docker-compose.yml, HF_TOKEN como build arg). Roda em CPU com latência
# aceitável para uso sob demanda (não em lote): ~15-23s por chamada nos
# testes manuais, um pouco mais lento que o Qwen 0.5B anterior (~10-12s),
# mas com qualidade de saída melhor.
ENRICHMENT_MODEL = "google/gemma-3-1b-it"

# Observabilidade — nível do root logger da aplicação (ver app.logging_config).
# Configurável sem redeploy de código: útil pra ligar DEBUG numa investigação
# pontual em qualquer ambiente, só mudando a variável.
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")

# Observabilidade — backend de métricas de aplicação (ver
# app.observability.metrics). "noop" (default, sem efeito nenhum) ou
# "cloudwatch" (loga em formato EMF, convertido em métricas reais pelo
# CloudWatch quando os logs do container são coletados por ele).
METRICS_BACKEND = os.environ.get("METRICS_BACKEND", "noop")

# Namespace CloudWatch usado pelo CloudWatchEmfMetricsSink — configurável
# pra separar ambientes/contas sem mudar código.
METRICS_NAMESPACE = os.environ.get("METRICS_NAMESPACE", "AutoITIL")

# Autenticação — segredo de assinatura dos JWT emitidos em app.auth. Default
# só serve pra dev local; SEMPRE trocar em qualquer ambiente que não seja a
# máquina do desenvolvedor (mesmo aviso que já valia pra API_KEY, que esta
# entrega substitui).
JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "dev-local-only-change-me")

# Quantas horas um token emitido em /api/auth/login continua válido antes de
# exigir novo login. Sem renovação automática nesta entrega — expirado, a
# pessoa loga de novo.
JWT_EXPIRATION_HOURS = int(os.environ.get("JWT_EXPIRATION_HOURS", "168"))

# CORS — origens autorizadas a chamar a API de um browser, separadas por
# vírgula (ex.: "http://localhost:5173,chrome-extension://<id>"). Vazio por
# padrão (nenhuma origem cross-origin liberada) — configurável sem mudança
# de código pra quando um consumidor externo (ex.: extensão de navegador)
# precisar de uma origem nova.
CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("CORS_ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]
