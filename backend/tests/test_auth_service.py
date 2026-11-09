"""Testes de app.auth.service — integração real contra o Postgres do
docker-compose.yml. Cada teste usa um email único (sufixo por teste) pra
não colidir com outras execuções, já que não há reset de schema entre
rodadas (mesma convenção de hash_suffix usada em
test_feedback_enriquecimento_endpoint.py, adaptada pra email)."""

import uuid

from app.auth.service import (
    authenticate,
    create_user,
    list_users,
    set_user_admin,
    set_user_ativo,
)
from app.domain.db import SessionLocal

_RUN = uuid.uuid4().hex[:8]


def test_create_user_and_authenticate_with_correct_password():
    with SessionLocal() as session:
        usuario = create_user(
            session, f"svc-a-{_RUN}@autoitil.test", "senha-correta", is_admin=False
        )
        session.commit()
        user_id = usuario.id

    with SessionLocal() as session:
        autenticado = authenticate(session, f"svc-a-{_RUN}@autoitil.test", "senha-correta")

    assert autenticado is not None
    assert autenticado.id == user_id


def test_authenticate_rejects_wrong_password():
    with SessionLocal() as session:
        create_user(session, f"svc-b-{_RUN}@autoitil.test", "senha-correta")
        session.commit()

    with SessionLocal() as session:
        autenticado = authenticate(session, f"svc-b-{_RUN}@autoitil.test", "senha-errada")

    assert autenticado is None


def test_authenticate_rejects_nonexistent_email():
    with SessionLocal() as session:
        autenticado = authenticate(session, "nao-existe-svc@autoitil.test", "qualquer")

    assert autenticado is None


def test_authenticate_rejects_inactive_user():
    with SessionLocal() as session:
        usuario = create_user(session, f"svc-c-{_RUN}@autoitil.test", "senha-correta")
        session.commit()
        user_id = usuario.id

    with SessionLocal() as session:
        set_user_ativo(session, user_id, False)
        session.commit()

    with SessionLocal() as session:
        autenticado = authenticate(session, f"svc-c-{_RUN}@autoitil.test", "senha-correta")

    assert autenticado is None


def test_list_users_includes_created_user():
    with SessionLocal() as session:
        create_user(session, f"svc-d-{_RUN}@autoitil.test", "senha-correta")
        session.commit()

    with SessionLocal() as session:
        usuarios = list_users(session)

    assert any(u.email == f"svc-d-{_RUN}@autoitil.test" for u in usuarios)


def test_set_user_admin_promotes_user():
    with SessionLocal() as session:
        usuario = create_user(session, f"svc-e-{_RUN}@autoitil.test", "senha-correta")
        session.commit()
        user_id = usuario.id

    with SessionLocal() as session:
        atualizado = set_user_admin(session, user_id, True)
        session.commit()

    assert atualizado is not None
    assert atualizado.is_admin is True


def test_set_user_ativo_returns_none_for_nonexistent_id():
    with SessionLocal() as session:
        resultado = set_user_ativo(session, 999999999, False)

    assert resultado is None


def test_create_user_without_organizacao_id_uses_default():
    from app.domain.organizacoes import DEFAULT_ORGANIZACAO_NOME

    with SessionLocal() as session:
        usuario = create_user(session, f"svc-org-default-{_RUN}@autoitil.test", "senha-correta")
        session.commit()
        user_id = usuario.id

    with SessionLocal() as session:
        from app.domain.models import Organizacao, Usuario

        lido = session.get(Usuario, user_id)
        org = session.get(Organizacao, lido.organizacao_id)
        assert org.nome == DEFAULT_ORGANIZACAO_NOME


def test_create_user_with_explicit_organizacao_id():
    from app.domain.models import Organizacao, Usuario

    with SessionLocal() as session:
        outra_org = Organizacao(nome=f"Outra Org {_RUN}")
        session.add(outra_org)
        session.flush()
        outra_org_id = outra_org.id

        usuario = create_user(
            session,
            f"svc-org-explicita-{_RUN}@autoitil.test",
            "senha-correta",
            organizacao_id=outra_org_id,
        )
        session.commit()
        user_id = usuario.id

    with SessionLocal() as session:
        lido = session.get(Usuario, user_id)
        assert lido.organizacao_id == outra_org_id


def test_list_users_filters_by_organizacao_id():
    from app.domain.models import Organizacao

    with SessionLocal() as session:
        outra_org = Organizacao(nome=f"Lista Org {_RUN}")
        session.add(outra_org)
        session.flush()
        outra_org_id = outra_org.id

        create_user(
            session,
            f"svc-lista-outra-{_RUN}@autoitil.test",
            "senha-correta",
            organizacao_id=outra_org_id,
        )
        create_user(session, f"svc-lista-default-{_RUN}@autoitil.test", "senha-correta")
        session.commit()

    with SessionLocal() as session:
        usuarios_outra_org = list_users(session, organizacao_id=outra_org_id)

    emails = {u.email for u in usuarios_outra_org}
    assert f"svc-lista-outra-{_RUN}@autoitil.test" in emails
    assert f"svc-lista-default-{_RUN}@autoitil.test" not in emails
