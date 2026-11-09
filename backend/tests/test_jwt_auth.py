"""Garante que /api/* (toda a superfície do backend — o fluxo legado em
Jinja2 fora de /api/* foi removido) exige um JWT válido (Authorization:
Bearer) de um usuário ativo. Substitui o antigo test_api_key_auth.py."""

import uuid
from datetime import UTC, datetime, timedelta

import jwt
from fastapi.testclient import TestClient

from app.auth.security import create_access_token
from app.auth.service import create_user, set_user_ativo
from app.config import settings
from app.domain.db import SessionLocal
from app.main import app
from tests.auth_helpers import AUTH_HEADERS

client_no_token = TestClient(app)
client_with_token = TestClient(app, headers=AUTH_HEADERS)


def test_api_route_without_token_is_rejected():
    response = client_no_token.get("/api/models/quality")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_api_route_with_invalid_token_is_rejected():
    client = TestClient(app, headers={"Authorization": "Bearer token-invalido"})
    response = client.get("/api/models/quality")
    assert response.status_code == 401


def test_api_route_with_valid_token_is_accepted():
    response = client_with_token.get("/api/models/quality")
    assert response.status_code == 200


def test_api_route_with_expired_token_is_rejected():
    payload = {
        "sub": "1",
        "email": "expirado@autoitil.test",
        "is_admin": False,
        "exp": datetime.now(UTC) - timedelta(hours=1),
    }
    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm="HS256")
    client = TestClient(app, headers={"Authorization": f"Bearer {token}"})

    response = client.get("/api/models/quality")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_deactivated_user_token_is_rejected_even_before_expiration():
    """Cobre a revogação por desativação: o middleware confere `ativo`
    direto no banco a cada request (não confia só na claim do token), então
    desativar um usuário derruba o acesso imediatamente, sem esperar o
    token expirar."""
    email = f"desativado-{uuid.uuid4().hex[:8]}@autoitil.test"
    with SessionLocal() as session:
        usuario = create_user(session, email=email, senha="SenhaDeTeste!23")
        session.commit()
        token = create_access_token(usuario)
        set_user_ativo(session, usuario.id, False)
        session.commit()

    client = TestClient(app, headers={"Authorization": f"Bearer {token}"})
    response = client.get("/api/models/quality")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_health_route_is_exempt_from_token_requirement():
    """/api/health precisa responder sem token — é o endpoint que health
    checks de orquestrador (ALB/ECS) batem sem autenticação."""
    response = client_no_token.get("/api/health")
    assert response.status_code == 200


def test_me_includes_organizacao_id():
    response = client_with_token.get("/api/auth/me")
    assert response.status_code == 200
    assert "organizacao_id" in response.json()
    assert isinstance(response.json()["organizacao_id"], int)
