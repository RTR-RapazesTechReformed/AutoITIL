"""Testes de GET /api/tickets — integração real contra o Postgres do
docker-compose.yml (Postgres + schema v5). Sem mock de banco."""

from fastapi.testclient import TestClient

from app.domain.db import SessionLocal
from app.main import app
from app.tickets.persistence import persist_generated_tickets
from app.tickets.queries import export_tickets_rows
from tests.auth_helpers import AUTH_HEADERS

client = TestClient(app, headers=AUTH_HEADERS)


def _row(
    linha_origem,
    descricao,
    nivel1="Incidente",
    nivel2="Rede",
    titulo=None,
    prioridade="P1",
):
    titulo = titulo or f"{descricao} — {nivel1}"
    return {
        "linha_origem": linha_origem,
        "descricao_original": descricao,
        "descricao_limpa": descricao.lower(),
        "data": None,
        "responsavel": None,
        "classification": {
            "nivel1": nivel1,
            "nivel2": nivel2,
            "confianca_n1": 0.90,
            "confianca_n2": 0.80 if nivel2 is not None else None,
            "modelo_n1": "bert",
            "modelo_n2": "bert" if nivel2 is not None else None,
        },
        "prioridade_codigo": prioridade,
        "titulo_sugerido": titulo,
    }


def _seed(file_key, rows):
    with SessionLocal() as session:
        created = persist_generated_tickets(
            session,
            file_key=file_key,
            bucket="autoitil-uploads",
            tamanho_bytes=10,
            rows=rows,
        )
        session.commit()
        return created


def test_lists_tickets_with_pagination_meta():
    hash_ = "1" * 64
    _seed(
        f"uploads/{hash_}/lote1.csv",
        [_row(1, "erro no servidor de producao")],
    )

    response = client.get("/api/tickets?page=1&page_size=20")
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert "items" in payload["data"]
    assert "meta" in payload["data"]
    meta = payload["data"]["meta"]
    assert meta["page"] == 1
    assert meta["page_size"] == 20
    assert meta["total"] >= 1
    assert meta["total_pages"] >= 1

    item = payload["data"]["items"][0]
    assert set(
        [
            "id",
            "codigo",
            "titulo_sugerido",
            "tipo_itil",
            "area_responsavel",
            "prioridade",
            "status",
            "confianca_n1",
            "confianca_n2",
            "data_geracao",
            "atualizado_em",
        ]
    ).issubset(item.keys())
    assert item["status"] == "triagem"


def test_filters_by_area_prioridade_status():
    hash_ = "2" * 64
    _seed(
        f"uploads/{hash_}/lote2.csv",
        [
            _row(1, "falha na rede corporativa", nivel2="Rede", prioridade="P1"),
            _row(
                2,
                "solicitacao de acesso",
                nivel1="Requisição",
                nivel2="Aplicações",
                prioridade="P3",
            ),
        ],
    )

    response = client.get("/api/tickets?area=Rede&page_size=100")
    payload = response.json()
    assert all(item["area_responsavel"] == "Rede" for item in payload["data"]["items"])

    response = client.get("/api/tickets?prioridade=P3&page_size=100")
    payload = response.json()
    assert all(item["prioridade"] == "P3" for item in payload["data"]["items"])

    response = client.get("/api/tickets?status=triagem&page_size=100")
    payload = response.json()
    assert all(item["status"] == "triagem" for item in payload["data"]["items"])


def test_busca_textual_by_titulo():
    hash_ = "3" * 64
    _seed(
        f"uploads/{hash_}/lote3.csv",
        [_row(1, "problema muito especifico de vpn xyz123")],
    )

    response = client.get("/api/tickets?busca=xyz123&page_size=100")
    payload = response.json()
    assert len(payload["data"]["items"]) >= 1
    assert all(
        "xyz123" in item["titulo_sugerido"].lower() for item in payload["data"]["items"]
    )


def test_invalid_status_returns_422():
    response = client.get("/api/tickets?status=nao_existe")
    assert response.status_code == 422
    payload = response.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "VALIDATION_ERROR"


def test_page_size_over_100_is_rejected():
    response = client.get("/api/tickets?page_size=101")
    assert response.status_code == 422


class TestExportTicketsRows:
    def test_returns_all_matching_rows_without_pagination(self):
        hash_ = "2" * 64
        _seed(
            f"uploads/{hash_}/lote-export.csv",
            [
                _row(1, "erro no servidor de producao um"),
                _row(2, "erro no servidor de producao dois"),
                _row(3, "erro no servidor de producao tres"),
            ],
        )

        with SessionLocal() as session:
            rows = export_tickets_rows(session, busca="erro no servidor de producao")

        assert len(rows) >= 3
        codigos = {r["codigo"] for r in rows}
        assert len(codigos) == len({r["id"] for r in rows})  # sem duplicata

    def test_applies_area_filter(self):
        hash_ = "3" * 64
        _seed(
            f"uploads/{hash_}/lote-export-area.csv",
            [_row(1, "falha exclusiva desta area de teste", nivel2="Rede")],
        )

        with SessionLocal() as session:
            rows = export_tickets_rows(
                session, area="Rede", busca="falha exclusiva desta area de teste"
            )

        # >=1 (não ==1): _seed não é idempotente — reexecutar a suíte sem
        # limpar o banco entre rodadas acumula tickets com o mesmo hash/busca
        # (mesmo motivo pelo qual os testes de list_tickets acima usam
        # meta["total"] >= 1, não uma contagem exata). O que importa aqui é
        # que TODO resultado do filtro area="Rede" tem area_responsavel="Rede".
        assert len(rows) >= 1
        assert all(r["area_responsavel"] == "Rede" for r in rows)

    def test_area_filter_excludes_other_areas(self):
        hash_ = "4" * 64
        _seed(
            f"uploads/{hash_}/lote-export-area2.csv",
            [_row(1, "outra falha exclusiva de outra area", nivel2="Rede")],
        )

        with SessionLocal() as session:
            rows = export_tickets_rows(
                session, area="Segurança", busca="outra falha exclusiva de outra area"
            )

        assert rows == []
