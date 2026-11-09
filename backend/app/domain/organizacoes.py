"""organizacoes.py — organização "default" pra contas criadas sem
organizacao_id explícito (ex.: auth_helpers.py de teste, ou qualquer
chamador de app.auth.service.create_user que não escolhe organização).

A migração 008 já semeia essa linha ('Organização Padrão') pra backfill de
instalações pré-existentes — get_or_create_default_organizacao() busca
por esse MESMO nome, então o Postgres já populado nunca cria uma segunda
linha; só ambientes muito antigos que ainda não rodaram a migração 008
(ex.: um banco de teste novo criado fora do fluxo normal) acionariam o
create."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.models import Organizacao

DEFAULT_ORGANIZACAO_NOME = "Organização Padrão"


def get_or_create_default_organizacao(session: Session) -> Organizacao:
    org = session.scalar(
        select(Organizacao).where(Organizacao.nome == DEFAULT_ORGANIZACAO_NOME)
    )
    if org is not None:
        return org

    # organizacao.nome é UNIQUE (migração 009) — sob dois escritores
    # concorrentes que viram o SELECT acima vazio ao mesmo tempo, só um
    # INSERT vence; o outro recua até o SAVEPOINT (sem derrubar a
    # transação externa, que pode ter outro trabalho pendente na mesma
    # sessão) e re-seleciona a linha que o vencedor acabou de criar.
    try:
        with session.begin_nested():
            org = Organizacao(nome=DEFAULT_ORGANIZACAO_NOME)
            session.add(org)
            session.flush()
    except IntegrityError:
        org = session.scalar(
            select(Organizacao).where(Organizacao.nome == DEFAULT_ORGANIZACAO_NOME)
        )
        if org is None:
            raise
    return org
