"""Testes de POST/GET /api/admin/usuarios e PATCH /api/admin/usuarios/{id}
— integração real contra o Postgres do docker-compose.yml."""

import uuid

from fastapi.testclient import TestClient

from app.domain.db import SessionLocal
from app.main import app
from tests.auth_helpers import ADMIN_AUTH_HEADERS, AUTH_HEADERS

admin_client = TestClient(app, headers=ADMIN_AUTH_HEADERS)
regular_client = TestClient(app, headers=AUTH_HEADERS)

# Emails únicos por execução — mesma convenção usada em test_auth_routes.py
# (sem reset de schema entre rodadas de teste, e usuario.email tem UNIQUE).
_RUN = uuid.uuid4().hex[:8]


def test_admin_can_create_user():
    email = f"admin-cria-a-{_RUN}@autoitil.test"
    response = admin_client.post(
        "/api/admin/usuarios",
        json={"email": email, "senha": "senha-correta", "is_admin": False},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["data"]["email"] == email
    assert "senha_hash" not in body["data"]


def test_non_admin_cannot_create_user():
    response = regular_client.post(
        "/api/admin/usuarios",
        json={"email": f"nao-deveria-existir-{_RUN}@autoitil.test", "senha": "x", "is_admin": False},
    )

    assert response.status_code == 403


def test_creating_duplicate_email_returns_409():
    email = f"admin-cria-dup-{_RUN}@autoitil.test"
    admin_client.post(
        "/api/admin/usuarios",
        json={"email": email, "senha": "senha-correta", "is_admin": False},
    )

    response = admin_client.post(
        "/api/admin/usuarios",
        json={"email": email, "senha": "outra-senha", "is_admin": False},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "EMAIL_ALREADY_EXISTS"


def test_non_admin_cannot_list_users():
    response = regular_client.get("/api/admin/usuarios")
    assert response.status_code == 403


def test_admin_can_list_users():
    email = f"admin-lista-a-{_RUN}@autoitil.test"
    admin_client.post(
        "/api/admin/usuarios",
        json={"email": email, "senha": "senha-correta", "is_admin": False},
    )

    response = admin_client.get("/api/admin/usuarios")

    assert response.status_code == 200
    assert any(u["email"] == email for u in response.json())


def test_admin_can_deactivate_user():
    with SessionLocal() as session:
        from app.auth.service import create_user

        usuario = create_user(
            session, f"admin-desativa-a-{_RUN}@autoitil.test", "senha-correta"
        )
        session.commit()
        user_id = usuario.id

    response = admin_client.patch(
        f"/api/admin/usuarios/{user_id}", json={"ativo": False}
    )

    assert response.status_code == 200
    assert response.json()["data"]["ativo"] is False


def test_non_admin_cannot_patch_user():
    response = regular_client.patch("/api/admin/usuarios/1", json={"ativo": False})
    assert response.status_code == 403


def test_patch_nonexistent_user_returns_404():
    response = admin_client.patch(
        "/api/admin/usuarios/999999999", json={"ativo": False}
    )
    assert response.status_code == 404


def test_patch_with_empty_body_does_not_404_an_existing_user():
    with SessionLocal() as session:
        from app.auth.service import create_user

        usuario = create_user(
            session, f"admin-patch-vazio-{_RUN}@autoitil.test", "senha-correta"
        )
        session.commit()
        user_id = usuario.id

    response = admin_client.patch(f"/api/admin/usuarios/{user_id}", json={})

    assert response.status_code == 200
