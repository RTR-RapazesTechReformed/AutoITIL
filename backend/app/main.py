import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.auth import JwtAuthMiddleware
from app.api.auth_routes import router as auth_router
from app.api.custos_routes import router as custos_router
from app.api.request_logging import RequestIdMiddleware
from app.api.routes import router
from app.config import settings
from app.domain.db import SessionLocal
from app.domain.system_metrics import record_system_metrics_sample
from app.logging_config import configure_logging, request_id_ctx
from app.observability.metrics import get_metrics_sink

configure_logging()

logger = logging.getLogger(__name__)

if settings.JWT_SECRET_KEY == "dev-local-only-change-me":
    # Não falha o boot (quebraria o docker-compose.yml deste repo, cujo
    # default é justamente não definir a env var em dev local) — mas um
    # segredo previsível, publicado no repositório, deixa qualquer JWT
    # (inclusive admin) forjável por quem ler o código. Ver README.md,
    # seção "Configurações", e a review final do branch feat/jwt-auth.
    logger.warning(
        "jwt_secret_key_is_default",
        extra={
            "hint": (
                "JWT_SECRET_KEY não foi configurado — usando o valor "
                "padrão de dev, publicado no repositório. Defina a env "
                "var JWT_SECRET_KEY antes de expor esta API além de "
                "localhost."
            )
        },
    )

SYSTEM_METRICS_INTERVAL_SECONDS = 60


async def _system_metrics_loop() -> None:
    """Coleta uma amostra de CPU/memória do processo a cada
    SYSTEM_METRICS_INTERVAL_SECONDS, indefinidamente, até a tarefa ser
    cancelada no shutdown. Uma falha isolada (DB fora do ar, psutil com
    erro) não derruba o loop — só pula aquele ciclo e tenta de novo depois."""
    while True:
        await asyncio.sleep(SYSTEM_METRICS_INTERVAL_SECONDS)
        try:
            with SessionLocal() as session:
                record_system_metrics_sample(session)
        except Exception:
            logger.warning("system_metrics_sample_failed", exc_info=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_system_metrics_loop())
    yield
    task.cancel()


app = FastAPI(title="Smart Ingestion Engine", lifespan=lifespan)

# Ordem de registro importa: Starlette envolve o app numa pilha de
# middlewares onde o ÚLTIMO registrado fica mais externo (roda primeiro
# na requisição, por último na resposta). CORSMiddleware é registrado por
# último de propósito, pra responder o preflight OPTIONS antes de
# qualquer gate de auth rodar. RequestIdMiddleware envolve
# JwtAuthMiddleware — assim toda requisição, inclusive as rejeitadas por
# token inválido (401), ganha request_id e X-Request-ID.
app.add_middleware(JwtAuthMiddleware)
app.add_middleware(RequestIdMiddleware, metrics_sink=get_metrics_sink())
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def log_unhandled_exception(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", None) or "-"
    token = request_id_ctx.set(request_id)
    try:
        logger.error("unhandled_exception", exc_info=exc)
    finally:
        request_id_ctx.reset(token)

    response = JSONResponse(
        status_code=500, content={"detail": "Internal Server Error"}
    )
    response.headers["X-Request-ID"] = request_id
    return response


app.include_router(router)
app.include_router(auth_router)
app.include_router(custos_router)
