"""Smoke test de conexão real com o Postgres via SQLAlchemy.

Requer o container do docker-compose.yml rodando (`docker compose up -d`).
Não mocka nada — se este teste falhar, a conexão real está quebrada.
"""

from sqlalchemy import select

from app.domain.db import SessionLocal
from app.domain.models import Prioridade, StatusTicket


def test_conecta_e_le_prioridades_da_carga_inicial():
    with SessionLocal() as session:
        prioridades = session.scalars(
            select(Prioridade).order_by(Prioridade.ordem)
        ).all()

    assert [p.codigo for p in prioridades] == ["P1", "P2", "P3", "P4"]


def test_conecta_e_le_status_ticket_da_carga_inicial():
    with SessionLocal() as session:
        status = session.scalars(
            select(StatusTicket).order_by(StatusTicket.ordem)
        ).all()

    assert [s.codigo for s in status] == [
        "triagem",
        "a_fazer",
        "em_progresso",
        "aguardando_revisao_humana",
        "concluido",
    ]
