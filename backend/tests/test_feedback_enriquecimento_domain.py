"""Testes de record_feedback — integração real contra o Postgres do
docker-compose.yml. Sem mock de banco."""

from sqlalchemy import select

from app.domain.db import SessionLocal
from app.domain.models import FeedbackEnriquecimento
from app.tickets.feedback import record_feedback
from app.tickets.persistence import persist_generated_tickets


def _row(linha_origem=1):
    return {
        "linha_origem": linha_origem,
        "descricao_original": "VPN do escritorio caiu",
        "descricao_limpa": "vpn escritorio caiu",
        "data": None,
        "responsavel": None,
        "classification": {
            "nivel1": "Incidente",
            "nivel2": "Rede",
            "confianca_n1": 0.94,
            "confianca_n2": 0.88,
            "modelo_n1": "bert",
            "modelo_n2": "bert",
        },
        "prioridade_codigo": "P1",
        "titulo_sugerido": "VPN do escritorio caiu — Incidente",
    }


def _seed_ticket(hash_suffix):
    hash_ = hash_suffix * 64
    with SessionLocal() as session:
        created = persist_generated_tickets(
            session,
            file_key=f"uploads/{hash_}/teste.csv",
            bucket="autoitil-uploads",
            tamanho_bytes=10,
            rows=[_row()],
        )
        session.commit()
        return created[0]


def test_primeiro_voto_cria_a_linha():
    ticket = _seed_ticket("a")

    with SessionLocal() as session:
        resultado = record_feedback(session, ticket["id"], "up")
        session.commit()

        assert resultado == {"ticket_id": ticket["id"], "valor": "up"}

        feedback = session.scalar(
            select(FeedbackEnriquecimento).where(FeedbackEnriquecimento.ticket_id == ticket["id"])
        )
        assert feedback.valor == "up"


def test_segundo_voto_sobrescreve_o_primeiro_sem_duplicar_linha():
    ticket = _seed_ticket("c")

    with SessionLocal() as session:
        record_feedback(session, ticket["id"], "up")
        session.commit()

    with SessionLocal() as session:
        record_feedback(session, ticket["id"], "down")
        session.commit()

    with SessionLocal() as session:
        linhas = session.scalars(
            select(FeedbackEnriquecimento).where(FeedbackEnriquecimento.ticket_id == ticket["id"])
        ).all()
        assert len(linhas) == 1
        assert linhas[0].valor == "down"


def test_retorna_none_para_ticket_inexistente():
    with SessionLocal() as session:
        assert record_feedback(session, 999999999, "up") is None


def test_levanta_value_error_para_valor_invalido():
    ticket = _seed_ticket("i")

    with SessionLocal() as session:
        try:
            record_feedback(session, ticket["id"], "sideways")
            raise AssertionError("deveria ter levantado ValueError")
        except ValueError:
            pass
