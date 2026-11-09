"""Testes de persist_generated_tickets — integração real contra o Postgres
do docker-compose.yml (Postgres + schema v5). Sem mock de banco."""

from app.domain.db import SessionLocal
from app.domain.models import Arquivo, Classificacao, Registro, TextoProcessado, Ticket
from app.tickets.persistence import persist_generated_tickets


def _sample_row(linha_origem=1, nivel2="Rede"):
    return {
        "linha_origem": linha_origem,
        "descricao_original": "VPN do escritorio caiu",
        "descricao_limpa": "vpn escritorio caiu",
        "data": None,
        "responsavel": None,
        "classification": {
            "nivel1": "Incidente",
            "nivel2": nivel2,
            "confianca_n1": 0.94,
            "confianca_n2": 0.88,
            "modelo_n1": "bert",
            "modelo_n2": "bert",
        },
        "prioridade_codigo": "P1",
        "titulo_sugerido": "VPN do escritorio caiu — Incidente",
    }


_HASH_DEADBEEF = (
    "deadbeef" + "0" * 56
)  # CHAR(64) — usar um hash de 64 chars, como o SHA-256 real
_HASH_A = "a" * 64
_HASH_B = "b" * 64
_HASH_C = "c" * 64


def test_persists_full_chain_for_single_row():
    with SessionLocal() as session:
        created = persist_generated_tickets(
            session,
            file_key=f"uploads/{_HASH_DEADBEEF}/teste.csv",
            bucket="autoitil-uploads",
            tamanho_bytes=123,
            rows=[_sample_row()],
        )
        session.commit()

        assert len(created) == 1
        assert created[0]["codigo"].startswith("TCK-")

        ticket = session.get(Ticket, created[0]["id"])
        assert ticket.codigo == created[0]["codigo"]
        assert ticket.titulo_sugerido == "VPN do escritorio caiu — Incidente"

        classificacao = session.get(Classificacao, ticket.classificacao_id)
        assert float(classificacao.confianca_n1) == 0.94

        texto = session.get(TextoProcessado, classificacao.texto_processado_id)
        assert texto.descricao_limpa == "vpn escritorio caiu"

        registro = session.get(Registro, texto.registro_id)
        assert registro.descricao_original == "VPN do escritorio caiu"

        arquivo = session.get(Arquivo, registro.arquivo_id)
        assert arquivo.hash_conteudo == _HASH_DEADBEEF
        assert arquivo.nome_original == "teste.csv"
        assert (
            arquivo.storage_uri
            == f"s3://autoitil-uploads/uploads/{_HASH_DEADBEEF}/teste.csv"
        )


def test_generates_unique_codigo_across_calls():
    with SessionLocal() as session:
        created_a = persist_generated_tickets(
            session,
            file_key=f"uploads/{_HASH_A}/a.csv",
            bucket="autoitil-uploads",
            tamanho_bytes=10,
            rows=[_sample_row()],
        )
        session.commit()
        created_b = persist_generated_tickets(
            session,
            file_key=f"uploads/{_HASH_B}/b.csv",
            bucket="autoitil-uploads",
            tamanho_bytes=10,
            rows=[_sample_row()],
        )
        session.commit()

        assert created_a[0]["codigo"] != created_b[0]["codigo"]


def test_persists_multiple_rows_in_one_call():
    with SessionLocal() as session:
        rows = [_sample_row(linha_origem=1), _sample_row(linha_origem=2, nivel2=None)]
        rows[1]["classification"]["nivel2"] = None
        rows[1]["classification"]["confianca_n2"] = None
        rows[1]["classification"]["modelo_n2"] = None

        created = persist_generated_tickets(
            session,
            file_key=f"uploads/{_HASH_C}/c.csv",
            bucket="autoitil-uploads",
            tamanho_bytes=20,
            rows=rows,
        )
        session.commit()

        assert len(created) == 2
        segunda = session.get(Ticket, created[1]["id"])
        classificacao = session.get(Classificacao, segunda.classificacao_id)
        assert classificacao.area_id is None
        assert classificacao.confianca_n2 is None


def test_persists_row_with_nan_date_as_null():
    """Bug real de producao: uma celula de 'data' vazia numa planilha real
    chega aqui como NaN (float), nao None -- e NaN e truthy em Python, entao
    `row.get("data") or None` nao convertia pra NULL e o INSERT numa coluna
    DATE quebrava com 'cannot cast type double precision to date'."""
    row = _sample_row(linha_origem=1)
    row["data"] = float("nan")
    row["responsavel"] = float("nan")

    with SessionLocal() as session:
        created = persist_generated_tickets(
            session,
            file_key=f"uploads/{_HASH_A}/nan.csv",
            bucket="autoitil-uploads",
            tamanho_bytes=20,
            rows=[row],
        )
        session.commit()

        ticket = session.get(Ticket, created[0]["id"])
        classificacao = session.get(Classificacao, ticket.classificacao_id)
        texto = session.get(TextoProcessado, classificacao.texto_processado_id)
        registro = session.get(Registro, texto.registro_id)
        assert registro.data_registro is None
        assert registro.responsavel is None


def test_created_includes_arquivo_id():
    with SessionLocal() as session:
        created = persist_generated_tickets(
            session,
            file_key=f"uploads/{_HASH_B}/arquivo-id.csv",
            bucket="autoitil-uploads",
            tamanho_bytes=5,
            rows=[_sample_row()],
        )
        session.commit()

        ticket = session.get(Ticket, created[0]["id"])
        classificacao = session.get(Classificacao, ticket.classificacao_id)
        texto = session.get(TextoProcessado, classificacao.texto_processado_id)
        registro = session.get(Registro, texto.registro_id)

        assert created[0]["arquivo_id"] == registro.arquivo_id
