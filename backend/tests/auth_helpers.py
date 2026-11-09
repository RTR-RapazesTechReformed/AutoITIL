"""Helper de autenticação para testes — gera headers Authorization com um
JWT válido para um usuário de verdade, persistido no banco.

JwtAuthMiddleware confere `ativo`/`is_admin` direto no banco a cada
request (não confia só na claim do token — ver app.api.auth), então o
token precisa apontar pra uma linha real de `usuario`, ativa. Cria as
duas linhas (uma comum, uma admin) uma vez por execução da suite, com
email único por run (`_RUN`) pra nunca colidir com o UNIQUE constraint
contra o Postgres persistente e nunca-resetado deste projeto (mesma
convenção de tests/test_auth_service.py)."""

import uuid

from app.auth.security import create_access_token
from app.auth.service import create_user
from app.domain.db import SessionLocal

_RUN = uuid.uuid4().hex[:8]


def _make_auth_headers(*, is_admin: bool) -> dict[str, str]:
    papel = "admin" if is_admin else "comum"
    with SessionLocal() as session:
        usuario = create_user(
            session,
            email=f"auth-helper-{papel}-{_RUN}@autoitil.test",
            senha="SenhaDeTeste!23",
            is_admin=is_admin,
        )
        session.commit()
    token = create_access_token(usuario)
    return {"Authorization": f"Bearer {token}"}


AUTH_HEADERS = _make_auth_headers(is_admin=False)
ADMIN_AUTH_HEADERS = _make_auth_headers(is_admin=True)
