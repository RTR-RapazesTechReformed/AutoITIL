TARGET_FIELDS = {
    "descricao": {
        "required": True,
        "aliases": [
            "descricao",
            "descrição",
            "desc",
            "problema",
            "ocorrencia",
            "ocorrência",
            "relato",
            "titulo",
            "assunto",
            "comentario",
            "comentário",
            "o que aconteceu",
        ],
    },
    "data": {
        "required": False,
        "aliases": [
            "data",
            "dt",
            "timestamp",
            "created_at",
            "data abertura",
        ],
    },
    "responsavel": {
        "required": False,
        "aliases": [
            "responsavel",
            "responsável",
            "owner",
            "analista",
            "usuario",
            "usuário",
        ],
    },
}

# F2-2 — catálogo fechado de área responsável (Nível 2 de classificação).
# Espelha exatamente:
#   - o CHECK ck_area_nome em db/autoitil_schema_v5.sql (autoitil.area_responsavel)
#   - os rótulos que o BertClassifier de Nível 2 já produz (id2label do
#     modelo, ver backend/models/bert/nivel2/config.json)
# Antes do F2-2, area_responsavel era tratado como texto livre vindo do
# modelo, sem uma lista fechada documentada no código da aplicação — o
# filtro por área em GET /api/tickets (F1-2) e no Kanban (F5-4) já dependia
# implicitamente desse catálogo fechado; esta constante só torna isso
# explícito e documentado, sem mudar nenhum comportamento em runtime.
AREA_RESPONSAVEL_CATALOG = [
    "Aplicações",
    "BD",
    "Rede",
    "Segurança",
    "Servidor",
]
