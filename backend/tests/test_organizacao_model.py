"""Teste de integração do mapeamento Organizacao <-> tabela organizacao
(schema v15) — confirma que o model bate com a migração 009."""

import uuid

from app.domain.db import SessionLocal
from app.domain.models import Organizacao

_RUN = uuid.uuid4().hex[:8]


def test_cria_e_le_organizacao():
    with SessionLocal() as session:
        org = Organizacao(nome=f"Teste Org {_RUN}")
        session.add(org)
        session.flush()
        org_id = org.id
        session.commit()

    with SessionLocal() as session:
        lida = session.get(Organizacao, org_id)
        assert lida is not None
        assert lida.nome == f"Teste Org {_RUN}"
        assert lida.ativo is True
