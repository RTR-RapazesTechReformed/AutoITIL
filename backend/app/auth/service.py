"""Operações de banco sobre a tabela usuario — autenticação e
administração de contas (ver app.auth.security pro hashing/JWT puros).

NOTA: Todas as funções que retornam Usuario aplicam session.expunge(usuario)
logo após flush()/antes do return. SessionLocal usa expire_on_commit=True
(default), então sem expunge, ler qualquer atributo depois que o session
fecha levantaria DetachedInstanceError. expunge() preserva os atributos
em cache enquanto o objeto ainda está na sessão, permitindo acesso após
detachment. Essa prática garante que o caller possa ler attributes do
Usuario retornado mesmo depois de fechar a sessão."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.security import hash_password, verify_password
from app.domain.models import Usuario
from app.domain.organizacoes import get_or_create_default_organizacao


def authenticate(session: Session, email: str, senha: str) -> Usuario | None:
    usuario = session.scalar(select(Usuario).where(Usuario.email == email))
    if usuario is None or not usuario.ativo:
        return None
    if not verify_password(senha, usuario.senha_hash):
        return None
    session.expunge(usuario)
    return usuario


def create_user(
    session: Session,
    email: str,
    senha: str,
    is_admin: bool = False,
    organizacao_id: int | None = None,
) -> Usuario:
    if organizacao_id is None:
        organizacao_id = get_or_create_default_organizacao(session).id
    usuario = Usuario(
        email=email,
        senha_hash=hash_password(senha),
        is_admin=is_admin,
        organizacao_id=organizacao_id,
    )
    session.add(usuario)
    session.flush()
    session.expunge(usuario)
    return usuario


def list_users(session: Session, organizacao_id: int | None = None) -> list[Usuario]:
    stmt = select(Usuario).order_by(Usuario.id)
    if organizacao_id is not None:
        stmt = stmt.where(Usuario.organizacao_id == organizacao_id)
    return list(session.scalars(stmt))


def set_user_ativo(session: Session, user_id: int, ativo: bool) -> Usuario | None:
    usuario = session.get(Usuario, user_id)
    if usuario is None:
        return None
    usuario.ativo = ativo
    session.flush()
    session.expunge(usuario)
    return usuario


def set_user_admin(session: Session, user_id: int, is_admin: bool) -> Usuario | None:
    usuario = session.get(Usuario, user_id)
    if usuario is None:
        return None
    usuario.is_admin = is_admin
    session.flush()
    session.expunge(usuario)
    return usuario
