"""Testes de app.domain.organizacoes — integração real contra o Postgres."""

from app.domain.db import SessionLocal
from app.domain.organizacoes import (
    DEFAULT_ORGANIZACAO_NOME,
    get_or_create_default_organizacao,
)


def test_get_or_create_e_idempotente():
    with SessionLocal() as session:
        org_a = get_or_create_default_organizacao(session)
        session.commit()
        id_a = org_a.id

    with SessionLocal() as session:
        org_b = get_or_create_default_organizacao(session)
        session.commit()
        id_b = org_b.id

    assert id_a == id_b


def test_retorna_a_organizacao_com_o_nome_padrao():
    with SessionLocal() as session:
        org = get_or_create_default_organizacao(session)
        assert org.nome == DEFAULT_ORGANIZACAO_NOME
