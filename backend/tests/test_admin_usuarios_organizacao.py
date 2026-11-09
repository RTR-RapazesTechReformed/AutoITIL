"""Admin de uma organização não gerencia usuário de outra ( seção
'Administração de usuários — escopo por organização')."""

import uuid

from fastapi.testclient import TestClient

from app.auth.security import create_access_token
from app.auth.service import create_user
from app.domain.db import SessionLocal
from app.domain.models import Organizacao
from app.main import app
from tests.auth_helpers import ADMIN_AUTH_HEADERS

_RUN = uuid.uuid4().hex[:8]

admin_client = TestClient(app, headers=ADMIN_AUTH_HEADERS)


def _admin_de_outra_organizacao():
    # Sufixo único por chamada (e não só por run): esta fábrica é chamada uma
    # vez por teste nesta suíte, e o Postgres de dev usado nos testes nunca é
    # resetado entre execuções — reusar só `_RUN` faria a 2a chamada dentro
    # da mesma run colidir com o UNIQUE de usuario.email da 1a.
    sufixo = f"{_RUN}-{uuid.uuid4().hex[:8]}"
    with SessionLocal() as session:
        outra_org = Organizacao(nome=f"Org Isolada {sufixo}")
        session.add(outra_org)
        session.flush()
        usuario = create_user(
            session,
            f"admin-outra-org-{sufixo}@autoitil.test",
            "senha-correta",
            is_admin=True,
            organizacao_id=outra_org.id,
        )
        session.commit()
        token = create_access_token(usuario)
    return TestClient(app, headers={"Authorization": f"Bearer {token}"})


def test_novo_usuario_herda_organizacao_de_quem_cria():
    email = f"herdado-{_RUN}@autoitil.test"
    admin_client.post(
        "/api/admin/usuarios", json={"email": email, "senha": "senha-correta", "is_admin": False}
    )

    outra_org_client = _admin_de_outra_organizacao()
    response = outra_org_client.get("/api/admin/usuarios")

    assert response.status_code == 200
    assert all(u["email"] != email for u in response.json())


def test_admin_nao_lista_usuario_de_outra_organizacao():
    outra_org_client = _admin_de_outra_organizacao()
    email_outra_org = f"soh-na-outra-org-{_RUN}@autoitil.test"
    outra_org_client.post(
        "/api/admin/usuarios",
        json={"email": email_outra_org, "senha": "senha-correta", "is_admin": False},
    )

    response = admin_client.get("/api/admin/usuarios")

    assert response.status_code == 200
    assert all(u["email"] != email_outra_org for u in response.json())


def test_admin_nao_atualiza_usuario_de_outra_organizacao():
    outra_org_client = _admin_de_outra_organizacao()
    email_outra_org = f"alvo-patch-outra-org-{_RUN}@autoitil.test"
    criar_response = outra_org_client.post(
        "/api/admin/usuarios",
        json={"email": email_outra_org, "senha": "senha-correta", "is_admin": False},
    )
    user_id = criar_response.json()["data"]["id"]

    patch_response = admin_client.patch(
        f"/api/admin/usuarios/{user_id}", json={"ativo": False}
    )
    assert patch_response.status_code == 404

    verificacao = outra_org_client.get("/api/admin/usuarios")
    alvo = next(u for u in verificacao.json() if u["email"] == email_outra_org)
    assert alvo["ativo"] is True
