"""Cria o usuário administrador (ou redefine a senha, se ele já existir).

Nenhuma credencial fica no repositório: e-mail e senha vêm do ambiente.

Uso, a partir de backend/:
    ADMIN_EMAIL=voce@exemplo.com ADMIN_PASSWORD='<sua-senha>' python -m scripts.create_admin
"""

from __future__ import annotations

import os
import sys

from sqlalchemy import select

from app.auth.security import hash_password
from app.auth.service import create_user
from app.domain.db import SessionLocal
from app.domain.models import Usuario


def main() -> int:
    email = os.environ.get("ADMIN_EMAIL", "").strip()
    senha = os.environ.get("ADMIN_PASSWORD", "")
    if not email or not senha:
        print("Defina ADMIN_EMAIL e ADMIN_PASSWORD no ambiente.", file=sys.stderr)
        return 1
    if len(senha) < 12:
        print("ADMIN_PASSWORD deve ter pelo menos 12 caracteres.", file=sys.stderr)
        return 1

    with SessionLocal() as session:
        usuario = session.scalar(select(Usuario).where(Usuario.email == email))
        if usuario is None:
            create_user(session, email, senha, is_admin=True)
            acao = "criado"
        else:
            usuario.senha_hash = hash_password(senha)
            usuario.is_admin = True
            usuario.ativo = True
            acao = "atualizado"
        session.commit()
    print(f"Administrador {email} {acao}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
