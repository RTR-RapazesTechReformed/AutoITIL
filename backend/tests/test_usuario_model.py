"""Smoke test da tabela usuario (schema v12) e do ORM Usuario — confere
que o admin semeado existe e que o mapeamento das colunas está certo.
Não cria linha nova (não há reset de schema entre execuções de teste)."""

from sqlalchemy import select

from app.domain.db import SessionLocal
from app.domain.models import Usuario


def test_admin_semeado_existe_e_e_admin_ativo():
    with SessionLocal() as session:
        admin = session.scalar(
            select(Usuario).where(Usuario.email == "admin@autoitil.local")
        )

    assert admin is not None
    assert admin.is_admin is True
    assert admin.ativo is True
    assert admin.senha_hash.startswith("$2b$")
