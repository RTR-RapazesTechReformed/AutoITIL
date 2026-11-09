"""Testes de record_revisao — integração real contra o Postgres do
docker-compose.yml. Sem mock de banco."""

from sqlalchemy import select

from app.domain.db import SessionLocal
from app.domain.models import (
    AreaResponsavel,
    Classificacao,
    RevisaoClassificacao,
    Ticket,
    TipoItil,
)
from app.tickets.persistence import persist_generated_tickets
from app.tickets.revisao import record_revisao


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


def test_primeira_revisao_grava_original_a_partir_da_predicao_atual():
    ticket = _seed_ticket("k")

    with SessionLocal() as session:
        resultado = record_revisao(session, ticket["id"], "tipo_itil", "Problema")
        session.commit()

        assert resultado == {
            "ticket_id": ticket["id"],
            "nivel": "tipo_itil",
            "valor": "Problema",
        }

        revisao = session.scalar(
            select(RevisaoClassificacao).where(RevisaoClassificacao.ticket_id == ticket["id"])
        )
        assert revisao.tipo_itil_original_id is not None
        assert revisao.tipo_itil_revisado_id is not None
        assert revisao.tipo_itil_revisado_em is not None
        # o ticket nasceu classificado como "Incidente" — o snapshot deve
        # ter capturado esse id, não o de "Problema" (já revisado)
        original = session.get(TipoItil, revisao.tipo_itil_original_id)
        assert original.nome == "Incidente"


def test_segunda_revisao_nao_sobrescreve_original():
    ticket = _seed_ticket("m")

    with SessionLocal() as session:
        record_revisao(session, ticket["id"], "tipo_itil", "Problema")
        session.commit()

    with SessionLocal() as session:
        revisao_antes = session.scalar(
            select(RevisaoClassificacao).where(RevisaoClassificacao.ticket_id == ticket["id"])
        )
        original_id_antes = revisao_antes.tipo_itil_original_id

        record_revisao(session, ticket["id"], "tipo_itil", "Mudança")
        session.commit()

    with SessionLocal() as session:
        revisao_depois = session.scalar(
            select(RevisaoClassificacao).where(RevisaoClassificacao.ticket_id == ticket["id"])
        )
        assert revisao_depois.tipo_itil_original_id == original_id_antes
        revisado = session.get(TipoItil, revisao_depois.tipo_itil_revisado_id)
        assert revisado.nome == "Mudança"


def test_revisao_atualiza_classificacao_in_place_sem_tocar_prioridade():
    ticket = _seed_ticket("n")

    with SessionLocal() as session:
        ticket_antes = session.get(Ticket, ticket["id"])
        prioridade_antes = ticket_antes.prioridade_id

        record_revisao(session, ticket["id"], "area", "Servidor")
        session.commit()

    with SessionLocal() as session:
        ticket_depois = session.get(Ticket, ticket["id"])
        classificacao = session.get(Classificacao, ticket_depois.classificacao_id)
        area = session.get(AreaResponsavel, classificacao.area_id)
        assert area.nome == "Servidor"
        assert ticket_depois.prioridade_id == prioridade_antes


def test_retorna_none_para_ticket_inexistente():
    with SessionLocal() as session:
        assert record_revisao(session, 999999999, "tipo_itil", "Incidente") is None


def test_levanta_value_error_para_valor_invalido():
    ticket = _seed_ticket("p")

    with SessionLocal() as session:
        try:
            record_revisao(session, ticket["id"], "tipo_itil", "Categoria Inexistente")
            raise AssertionError("deveria ter levantado ValueError")
        except ValueError:
            pass
