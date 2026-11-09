"""Testes de POST /api/auth/login e GET /api/auth/me — integração real
contra o Postgres do docker-compose.yml. Cada teste que precisa de um
usuário próprio usa um email único pra não colidir entre execuções."""

import uuid

from fastapi.testclient import TestClient

from app.auth.service import create_user, set_user_ativo
from app.domain.db import SessionLocal
from app.main import app

client = TestClient(app)

# Emails únicos por execução — a suíte roda contra o Postgres real, sem
# reset entre rodadas (mesma convenção de hash_suffix usada em
# test_feedback_enriquecimento_endpoint.py), e usuario.email tem UNIQUE.
_RUN = uuid.uuid4().hex[:8]


def test_login_with_correct_credentials_returns_token_and_usuario():
    email = f"login-a-{_RUN}@autoitil.test"
    with SessionLocal() as session:
        create_user(session, email, "senha-correta")
        session.commit()

    response = client.post(
        "/api/auth/login",
        json={"email": email, "senha": "senha-correta"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["access_token"]
    assert body["data"]["usuario"]["email"] == email
    assert body["data"]["usuario"]["is_admin"] is False
    assert "ativo" not in body["data"]["usuario"]


def test_login_with_wrong_password_returns_401():
    email = f"login-b-{_RUN}@autoitil.test"
    with SessionLocal() as session:
        create_user(session, email, "senha-correta")
        session.commit()

    response = client.post(
        "/api/auth/login",
        json={"email": email, "senha": "senha-errada"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_login_with_nonexistent_email_returns_401():
    response = client.post(
        "/api/auth/login",
        json={"email": f"nao-existe-login-{_RUN}@autoitil.test", "senha": "qualquer"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_login_with_inactive_user_returns_401():
    email = f"login-c-{_RUN}@autoitil.test"
    with SessionLocal() as session:
        usuario = create_user(session, email, "senha-correta")
        session.commit()
        set_user_ativo(session, usuario.id, False)
        session.commit()

    response = client.post(
        "/api/auth/login",
        json={"email": email, "senha": "senha-correta"},
    )

    assert response.status_code == 401


def test_me_with_valid_token_returns_the_logged_in_user():
    email = f"login-d-{_RUN}@autoitil.test"
    with SessionLocal() as session:
        create_user(session, email, "senha-correta")
        session.commit()

    token = client.post(
        "/api/auth/login",
        json={"email": email, "senha": "senha-correta"},
    ).json()["data"]["access_token"]

    response = client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert response.json()["email"] == email


def test_me_without_token_returns_401():
    response = client.get("/api/auth/me")
    assert response.status_code == 401
