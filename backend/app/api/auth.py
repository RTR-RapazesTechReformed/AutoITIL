"""
auth.py — autenticação das rotas /api/* via JWT (substitui a antiga
X-API-Key única).

Exige o header `Authorization: Bearer <token>` com um JWT válido (emitido
por POST /api/auth/login, ver app.api.auth_routes) em todo request cujo
path comece com `/api/`, exceto EXEMPT_PATHS. O payload decodificado
carrega `sub`/`email`/`is_admin`, mas o gate confere `ativo`/`is_admin`
direto no banco (não confia só na claim do token) antes de liberar o
request — do contrário desativar ou rebaixar alguém em
/api/admin/usuarios não teria efeito nenhum até o token expirar (até
JWT_EXPIRATION_HOURS depois, ver review final do branch feat/jwt-auth).
O resultado final (claims do token + is_admin/ativo já confirmados no
banco) fica em request.state.usuario — rotas /api/admin/* conferem
request.state.usuario["is_admin"] elas mesmas (403 se False), mais simples
que um segundo middleware pra só três rotas.
"""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.auth.security import decode_access_token
from app.domain.db import SessionLocal
from app.domain.models import Usuario

# Exceções ao gate — path exato, sem token. /api/health pra health checks
# de orquestrador (ALB/ECS) não autenticados (ver I3); /api/auth/login
# porque é o próprio endpoint que emite o token.
EXEMPT_PATHS = {"/api/health", "/api/auth/login"}

def _unauthorized() -> JSONResponse:
    # Função, não uma instância compartilhada no módulo: RequestIdMiddleware
    # (que envolve este middleware) muta `response.headers["X-Request-ID"]`
    # depois do retorno (ver app/api/request_logging.py) — uma instância
    # única reaproveitada entre requests concorrentes correria risco de um
    # 401 sair com o X-Request-ID de OUTRO request (achado da review final
    # do branch feat/jwt-auth).
    return JSONResponse(
        status_code=401,
        content={
            "error": {
                "code": "UNAUTHORIZED",
                "message": "Token ausente ou inválido.",
            }
        },
    )


class JwtAuthMiddleware(BaseHTTPMiddleware):
    """Exige um JWT válido (Authorization: Bearer) em qualquer request para
    /api/*, exceto EXEMPT_PATHS. Também confere que o usuário do token
    ainda existe e está ativo, direto no banco — ver módulo docstring."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        if not request.url.path.startswith("/api/"):
            return await call_next(request)

        if request.url.path in EXEMPT_PATHS:
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        token = auth_header[7:] if auth_header.startswith("Bearer ") else None
        payload = decode_access_token(token) if token else None
        if payload is None:
            return _unauthorized()

        try:
            user_id = int(payload["sub"])
        except (KeyError, TypeError, ValueError):
            return _unauthorized()

        with SessionLocal() as session:
            usuario = session.get(Usuario, user_id)
            if usuario is None or not usuario.ativo:
                return _unauthorized()
            payload = {
                **payload,
                "is_admin": usuario.is_admin,
                "organizacao_id": usuario.organizacao_id,
            }

        request.state.usuario = payload
        return await call_next(request)
