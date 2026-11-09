"""Testes de GET /api/operations/summary — integração real contra o
Postgres do docker-compose.yml (Postgres + schema v5). Sem mock de banco."""

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.domain.db import SessionLocal
from app.main import app
from app.tickets.persistence import persist_generated_tickets
from app.tickets.queries import _average_time_per_status, save_enriched_description
from tests.auth_helpers import AUTH_HEADERS

client = TestClient(app, headers=AUTH_HEADERS)


def _row(descricao, nivel1="Incidente", nivel2="Rede", prioridade="P1", c1=0.9, c2=0.8):
    return {
        "linha_origem": 1,
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
        "prioridade_codigo": prioridade,
        "titulo_sugerido": f"{descricao} — {nivel1}",
    }


def _seed(hash_suffix, row):
    hash_ = hash_suffix * 64
    with SessionLocal() as session:
        persist_generated_tickets(
            session,
            file_key=f"uploads/{hash_}/teste.csv",
            bucket="autoitil-uploads",
            tamanho_bytes=10,
            rows=[row],
        )
        session.commit()


def test_summary_has_expected_shape():
    _seed("8", _row("erro no servidor", nivel2="Servidor", prioridade="P1"))

    response = client.get("/api/operations/summary")
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    data = payload["data"]

    assert data["total_tickets"] >= 1
    assert isinstance(data["por_area"], list)
    assert isinstance(data["por_prioridade"], list)
    assert set(["area", "total"]).issubset(data["por_area"][0].keys())
    assert set(["prioridade", "total"]).issubset(data["por_prioridade"][0].keys())
    assert "nivel1" in data["confianca_media"]
    assert "nivel2" in data["confianca_media"]
    assert "limiar_ativo" in data["abaixo_do_limiar"]
    assert "total" in data["abaixo_do_limiar"]


def test_counts_tickets_below_active_threshold():
    # limiar ativo (seed do schema) é 0.750 — confianca_n1 abaixo disso
    # deve contar em abaixo_do_limiar.total
    _seed("9", _row("ticket com confianca baixa", c1=0.3, c2=0.2))

    response = client.get("/api/operations/summary")
    payload = response.json()
    assert payload["data"]["abaixo_do_limiar"]["limiar_ativo"] == 0.75
    assert payload["data"]["abaixo_do_limiar"]["total"] >= 1


def test_tempo_medio_por_coluna_shape_and_ordering():
    ticket = None
    with SessionLocal() as session:
        created = persist_generated_tickets(
            session,
            file_key=f"uploads/{'a' * 64}/teste_tempo_coluna.csv",
            bucket="autoitil-uploads",
            tamanho_bytes=10,
            rows=[_row("ticket de teste de tempo por coluna")],
        )
        session.commit()
        ticket = created[0]

    # Gera pelo menos uma transição COMPLETA (triagem -> a_fazer) — o
    # ticket sai da coluna "triagem", então "triagem" ganha uma amostra de
    # duração completa na agregação. Não afirma quais status EXATOS
    # aparecem no total (é Postgres real, compartilhado entre execuções da
    # suíte — outros testes também geram transições), só a forma dos dados.
    client.patch(f"/api/tickets/{ticket['id']}", json={"status": "a_fazer"})

    response = client.get("/api/operations/summary")
    data = response.json()["data"]
    tempo_por_coluna = data["tempo_medio_por_coluna"]

    ordem_kanban = [
        "triagem",
        "a_fazer",
        "em_progresso",
        "aguardando_revisao_humana",
        "concluido",
    ]

    assert isinstance(tempo_por_coluna, list)
    assert len(tempo_por_coluna) >= 1
    for row in tempo_por_coluna:
        assert set(row.keys()) == {"status", "descricao", "media_horas"}
        assert row["status"] in ordem_kanban
        assert row["media_horas"] >= 0

    # ordenado pela ordem visual das colunas do Kanban
    posicoes = [ordem_kanban.index(row["status"]) for row in tempo_por_coluna]
    assert posicoes == sorted(posicoes)


def test_tempo_medio_por_coluna_conta_so_transicoes_completas():
    # Prova a regra "só conta transições completas" (spec F4-1) direto na
    # função de agregação — mais confiável que inferir pelo endpoint num
    # Postgres real e compartilhado entre execuções da suíte, onde não dá
    # pra afirmar totais exatos nem a ausência de uma categoria.
    with SessionLocal() as session:
        antes_criacao = _average_time_per_status(session)

    with SessionLocal() as session:
        created = persist_generated_tickets(
            session,
            file_key=f"uploads/{'d' * 64}/teste_so_transicoes_completas.csv",
            bucket="autoitil-uploads",
            tamanho_bytes=10,
            rows=[_row("ticket que fica parado sem transicionar")],
        )
        session.commit()
        ticket = created[0]

    # Recua a linha inicial de histórico pra 2h atrás — sem isso, a
    # transição abaixo levaria frações de segundo e arredondaria pra
    # 0.0h, igual à média já existente de outras execuções da suíte,
    # mascarando a mudança que este teste quer detectar.
    with SessionLocal() as session:
        session.execute(
            text(
                "UPDATE ticket_status_historico SET data_transicao = data_transicao - INTERVAL '2 hours' "
                "WHERE ticket_id = :ticket_id"
            ),
            {"ticket_id": ticket["id"]},
        )
        session.commit()

    # Criar o ticket só grava a linha inicial em "triagem" via trigger
    # (trg_ticket_status) — uma única linha de histórico, sem par de
    # transição. Sem uma segunda transição não há duração completa, então
    # a agregação inteira não deve mudar em nada.
    with SessionLocal() as session:
        depois_criacao_sem_transicao = _average_time_per_status(session)

    assert depois_criacao_sem_transicao == antes_criacao

    # Agora uma transição COMPLETA (triagem -> a_fazer): deve alterar a
    # agregação (nova amostra de duração real contribuindo pra "triagem").
    client.patch(f"/api/tickets/{ticket['id']}", json={"status": "a_fazer"})

    with SessionLocal() as session:
        depois_transicao_completa = _average_time_per_status(session)

    assert depois_transicao_completa != antes_criacao

    # O ticket agora está parado em "a_fazer" (aberto, sem transição
    # seguinte ainda) — a garantia estrutural é a mesma de antes: sem um
    # próximo par, essa permanência atual não entra em nenhuma soma.
    with SessionLocal() as session:
        depois_parado_em_a_fazer = _average_time_per_status(session)

    assert depois_parado_em_a_fazer == depois_transicao_completa


def test_taxa_enriquecimento_conta_tickets_enriquecidos_e_nao_enriquecidos():
    # A suíte roda contra Postgres real e compartilhado — nunca afirma
    # totais exatos, só o delta que este teste controla (um ticket criado
    # e enriquecido aqui, comparado a um snapshot ANTES dessa criação).
    antes = client.get("/api/operations/summary").json()["data"]["taxa_enriquecimento"]

    with SessionLocal() as session:
        created = persist_generated_tickets(
            session,
            file_key=f"uploads/{'e' * 64}/teste_taxa_enriquecimento.csv",
            bucket="autoitil-uploads",
            tamanho_bytes=10,
            rows=[_row("ticket para taxa de enriquecimento")],
        )
        session.commit()
        ticket = created[0]

    with SessionLocal() as session:
        save_enriched_description(
            session,
            ticket["id"],
            {
                "objetivo": "teste de enriquecimento",
                "requisicoes": ["requisito a", "requisito b"],
                "cargo_recomendado": "analista de suporte",
            },
        )
        session.commit()

    depois = client.get("/api/operations/summary").json()["data"]["taxa_enriquecimento"]

    assert depois["total"] == antes["total"] + 1
    assert depois["enriquecidos"] == antes["enriquecidos"] + 1
    assert depois["percentual"] == round((depois["enriquecidos"] / depois["total"]) * 100, 1)


def test_volume_diario_por_area_e_prioridade_shape():
    _seed("b", _row("ticket pra serie temporal", nivel2="Rede", prioridade="P2"))

    response = client.get("/api/operations/summary")
    data = response.json()["data"]

    for chave in ("volume_diario_por_area", "volume_diario_por_prioridade"):
        serie = data[chave]
        assert isinstance(serie, list)
        assert len(serie) >= 1
        for linha in serie:
            assert "data" in linha
            for nome_chave, valor in linha.items():
                if nome_chave == "data":
                    continue
                assert isinstance(valor, int)
                assert valor >= 0


def test_taxa_enriquecimento_shape():
    response = client.get("/api/operations/summary")
    data = response.json()["data"]
    taxa = data["taxa_enriquecimento"]

    assert set(taxa.keys()) == {"enriquecidos", "total", "percentual"}
    assert taxa["total"] >= 0
    assert taxa["enriquecidos"] >= 0
    assert taxa["enriquecidos"] <= taxa["total"]
    assert 0 <= taxa["percentual"] <= 100
