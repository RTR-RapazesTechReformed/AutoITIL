"""Testes de app.domain.upload_history — integração real contra o Postgres
do docker-compose.yml (mesmo padrão de test_persistence.py). Sem mock de
banco."""

from app.domain.db import SessionLocal
from app.domain.models import HistoricoUpload
from app.domain.upload_history import (
    list_recent_uploads,
    mark_failed,
    mark_previewed,
    mark_tickets_generated,
    record_upload_received,
)

_HASH_X = "x" * 64
_HASH_Y = "y" * 64


def _record(session, nome="historico_x.csv", storage_uri=None):
    return record_upload_received(
        session,
        nome_original=nome,
        extensao=".csv",
        hash_conteudo=_HASH_X,
        tamanho_bytes=100,
        storage_uri=storage_uri or f"s3://autoitil-uploads/uploads/{_HASH_X}/{nome}",
    )


def test_record_upload_received_inserts_with_status_recebido():
    with SessionLocal() as session:
        entry_id = _record(session, nome="historico_a.csv")
        session.commit()

        entry = session.get(HistoricoUpload, entry_id)
        assert entry.status == "recebido"
        assert entry.nome_original == "historico_a.csv"
        assert entry.total_linhas is None
        assert entry.mensagem_erro is None


def test_mark_previewed_updates_most_recent_open_entry():
    storage_uri = f"s3://autoitil-uploads/uploads/{_HASH_X}/historico_b.csv"
    with SessionLocal() as session:
        entry_id = _record(session, nome="historico_b.csv", storage_uri=storage_uri)
        session.commit()

        mark_previewed(session, storage_uri, total_linhas=42)
        session.commit()

        entry = session.get(HistoricoUpload, entry_id)
        assert entry.status == "pre_visualizado"
        assert entry.total_linhas == 42


def test_mark_failed_sets_mensagem_erro():
    storage_uri = f"s3://autoitil-uploads/uploads/{_HASH_X}/historico_c.csv"
    with SessionLocal() as session:
        entry_id = _record(session, nome="historico_c.csv", storage_uri=storage_uri)
        session.commit()

        mark_failed(session, storage_uri, mensagem_erro="arquivo corrompido")
        session.commit()

        entry = session.get(HistoricoUpload, entry_id)
        assert entry.status == "falhou"
        assert entry.mensagem_erro == "arquivo corrompido"


def test_mark_tickets_generated_sets_status():
    storage_uri = f"s3://autoitil-uploads/uploads/{_HASH_X}/historico_d.csv"
    with SessionLocal() as session:
        entry_id = _record(session, nome="historico_d.csv", storage_uri=storage_uri)
        session.commit()

        mark_tickets_generated(session, storage_uri)
        session.commit()

        entry = session.get(HistoricoUpload, entry_id)
        assert entry.status == "tickets_gerados"


def test_mark_functions_are_noop_when_no_open_entry_found():
    with SessionLocal() as session:
        # Não lança mesmo sem nenhuma linha correspondente:
        mark_previewed(session, "s3://autoitil-uploads/uploads/inexistente/x.csv", 1)
        mark_failed(session, "s3://autoitil-uploads/uploads/inexistente/x.csv", "erro")
        mark_tickets_generated(
            session, "s3://autoitil-uploads/uploads/inexistente/x.csv"
        )
        session.commit()


def test_correlation_picks_most_recent_open_entry_when_two_share_storage_uri():
    storage_uri = f"s3://autoitil-uploads/uploads/{_HASH_Y}/historico_e.csv"
    with SessionLocal() as session:
        first_id = record_upload_received(
            session,
            nome_original="historico_e.csv",
            extensao=".csv",
            hash_conteudo=_HASH_Y,
            tamanho_bytes=10,
            storage_uri=storage_uri,
        )
        session.commit()

        second_id = record_upload_received(
            session,
            nome_original="historico_e.csv",
            extensao=".csv",
            hash_conteudo=_HASH_Y,
            tamanho_bytes=10,
            storage_uri=storage_uri,
        )
        session.commit()

        mark_previewed(session, storage_uri, total_linhas=7)
        session.commit()

        first_entry = session.get(HistoricoUpload, first_id)
        second_entry = session.get(HistoricoUpload, second_id)
        assert first_entry.status == "recebido"
        assert second_entry.status == "pre_visualizado"
        assert second_entry.total_linhas == 7


def test_list_recent_uploads_orders_by_criado_em_desc():
    with SessionLocal() as session:
        _record(session, nome="historico_f1.csv")
        session.commit()
        _record(session, nome="historico_f2.csv")
        session.commit()

        uploads = list_recent_uploads(session, limit=2)

        assert len(uploads) == 2
        assert uploads[0]["nome_original"] == "historico_f2.csv"
        assert uploads[1]["nome_original"] == "historico_f1.csv"
        assert "id" in uploads[0]
        assert "criado_em" in uploads[0]
