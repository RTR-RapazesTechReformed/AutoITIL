"""Smoke test da tabela usuario e do ORM Usuario — cria um admin de teste e
confere que o mapeamento das colunas está certo. Não há usuário semeado no
schema; o e-mail é único por execução para não colidir com o banco persistente."""

import uuid

from sqlalchemy import select

from app.auth.service import create_user
from app.domain.db import SessionLocal
from app.domain.models import Usuario


def test_admin_criado_e_admin_ativo():
    email = f"admin-teste-{uuid.uuid4().hex[:8]}@exemplo.test"
    with SessionLocal() as session:
        create_user(session, email, "senha-de-teste-123", is_admin=True)
        session.commit()
        admin = session.scalar(select(Usuario).where(Usuario.email == email))

    assert admin is not None
    assert admin.is_admin is True
    assert admin.ativo is True
    assert admin.senha_hash.startswith("$2b$")
