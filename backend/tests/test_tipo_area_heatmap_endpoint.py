"""Testes de GET /api/operations/type-area — a grade tipo ITIL x área que
alimenta o heatmap do dashboard. Integração real contra o Postgres do
docker-compose, no mesmo estilo de test_dashboard_summary_endpoint.py."""

from fastapi.testclient import TestClient

from app.domain.db import SessionLocal
from app.main import app
from app.tickets.persistence import persist_generated_tickets
from tests.auth_helpers import AUTH_HEADERS

client = TestClient(app, headers=AUTH_HEADERS)


def _row(descricao, nivel1="Incidente", nivel2="Rede", c1=0.9, c2=0.8, linha=1):
    return {
        # (arquivo_id, linha_origem) é único: duas linhas do mesmo arquivo
        # precisam de números diferentes.
        "linha_origem": linha,
        "descricao_original": descricao,
        "descricao_limpa": descricao.lower(),
        "data": None,
        "responsavel": None,
        "classification": {
            "nivel1": nivel1,
            "nivel2": nivel2,
            "confianca_n1": c1,
            "confianca_n2": c2 if nivel2 is not None else None,
            "modelo_n1": "bert",
            "modelo_n2": "bert" if nivel2 is not None else None,
        },
        "prioridade_codigo": "P1",
        "titulo_sugerido": f"{descricao} — {nivel1}",
    }


def _seed(hash_suffix, rows):
    hash_ = hash_suffix * 64
    with SessionLocal() as session:
        persist_generated_tickets(
            session,
            file_key=f"uploads/{hash_}/teste.csv",
            bucket="autoitil-uploads",
            tamanho_bytes=10,
            rows=rows,
        )
        session.commit()


def _celula(celulas, tipo, area):
    return next(c for c in celulas if c["tipo"] == tipo and c["area"] == area)


def test_grade_vem_densa_com_todas_as_combinacoes():
    _seed("a", [_row("rede fora do ar", nivel1="Incidente", nivel2="Rede")])

    response = client.get("/api/operations/type-area")
    assert response.status_code == 200
    data = response.json()

    # 4 tipos ITIL x 5 áreas = 20 células, inclusive as zeradas: o heatmap
    # desenha a grade inteira sem precisar preencher buracos.
    assert len(data["tipos"]) == 4
    assert len(data["areas"]) == 5
    assert len(data["celulas"]) == 20
    assert {"tipo", "area", "total", "confianca_media"} == set(data["celulas"][0])


def test_conta_chamado_na_celula_certa_com_a_confianca_media():
    _seed(
        "b",
        [
            _row(
                "firewall bloqueando",
                nivel1="Incidente",
                nivel2="Segurança",
                c2=0.6,
                linha=1,
            ),
            _row(
                "vpn instável",
                nivel1="Incidente",
                nivel2="Segurança",
                c2=0.8,
                linha=2,
            ),
        ],
    )

    data = client.get("/api/operations/type-area").json()
    celula = _celula(data["celulas"], "Incidente", "Segurança")

    assert celula["total"] >= 2
    assert celula["confianca_media"] is not None
    assert 0 <= celula["confianca_media"] <= 1


def test_chamado_sem_area_fica_fora_da_grade_mas_e_contado():
    _seed("c", [_row("sem nivel 2", nivel1="Mudança", nivel2=None)])

    data = client.get("/api/operations/type-area").json()

    assert data["sem_area"] >= 1
    # O total da grade conta só o que tem os dois níveis; o resto vai em
    # sem_area, para fechar com o total do dashboard.
    assert data["total"] == sum(c["total"] for c in data["celulas"])


def test_celula_vazia_tem_total_zero_e_confianca_nula():
    data = client.get("/api/operations/type-area").json()

    vazias = [c for c in data["celulas"] if c["total"] == 0]
    for celula in vazias:
        assert celula["confianca_media"] is None
