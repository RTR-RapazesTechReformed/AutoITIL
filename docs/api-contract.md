# AutoITIL — Contrato de API (F0-3)

Documenta os endpoints REST da API, tanto os já implementados quanto os que o
backlog (Fase 1) ainda vai implementar — contrato definido antes do código,
para o frontend (F3+) poder ser construído em paralelo.

## Autenticação

Toda rota sob `/api/*` — hoje, toda a superfície do backend, já que o
fluxo legado em Jinja2 (`/`, `/upload`, `/process`, `/classificar`,
`/metricas`) foi removido junto com esta entrega — exige o header
`Authorization: Bearer <token>`, com um JWT emitido por
`POST /api/auth/login`. Sem o header, com token malformado/expirado, ou
se o usuário do token foi desativado no banco, a resposta é `401`:

```json
{ "error": { "code": "UNAUTHORIZED", "message": "Token ausente ou inválido." } }
```

Exceções ao gate (`EXEMPT_PATHS` em `app/api/auth.py`): `/api/health`
(health check de orquestrador) e `/api/auth/login` (o próprio endpoint
que emite o token).

O frontend guarda o token em `localStorage` (ver `frontend/src/lib/auth.ts`)
e injeta o header automaticamente em toda chamada (`frontend/src/lib/api.ts`).

Convenção de envelope, usada em todos os endpoints JSON deste projeto:

```json
// sucesso
{ "success": true, "message": "...", "data": { ... } }

// erro
{ "success": false, "error": { "code": "VALIDATION_ERROR", "message": "..." } }
```

`GET /api/health`, `GET /api/tickets`, `GET /api/models/quality`, `GET /api/models/performance/system-history`,
`GET /api/models/performance/enrichment-history`, `GET /api/models/quality/reviews`,
`GET /api/models/quality/enrichment-feedback`, `GET /api/models/performance/classification-history`,
`GET /api/models/performance/throughput`, `GET /api/operations/ingestion-funnel`,
`GET /api/models/quality/confusion-matrix` e
`GET /api/operations/summary` retornam o `data` diretamente (sem o envelope
`success`/`message`), já que são leituras simples sem passos intermediários
de validação — segue o mesmo padrão do `GET /api/health` já implementado.
Endpoints que fazem alguma ação com passos que podem falhar de formas
diferentes (`POST /api/upload`, `POST /api/process`, `PATCH /api/tickets/{id}`)
usam o envelope completo.

---

## 1. Endpoints já implementados

### `GET /api/health`

Smoke test de conectividade (usado pelo proxy do frontend, F0-4).

**Response 200:**
```json
{ "status": "ok" }
```

### `POST /api/upload`

Recebe um arquivo (`multipart/form-data`, campo `file`), valida extensão/tamanho,
gera preview com sugestão de mapeamento de colunas (`SemanticMapper`).

**Request:** `multipart/form-data` — `file`: arquivo `.csv` ou `.xlsx` (máx. 10MB, 5000 linhas).

> Nota (F0-5): `file_id` deixou de ser apenas o nome do arquivo — a partir da migração para
> armazenamento S3/MinIO, ele é a key S3 completa sob a qual o upload foi salvo (prefixo
> `uploads/<hash>/`, ex.: `uploads/3a7f.../happy_path.csv`). Clientes devem tratar `file_id` como
> um identificador opaco e reenviá-lo tal como recebido em `POST /api/process`, sem assumir que é
> igual a `filename` ou que corresponde a um caminho local em disco.

**Response 200:**
```json
{
  "success": true,
  "message": "Arquivo lido com sucesso.",
  "data": {
    "file_id": "uploads/<hash>/happy_path.csv",
    "filename": "happy_path.csv",
    "row_count": 42,
    "column_count": 3,
    "columns": ["Descrição", "Data", "Responsável"],
    "suggestions": [
      { "source_column": "Descrição", "target_field": "descricao", "confidence": 0.95 }
    ],
    "suggested_mapping": { "descricao": "Descrição" },
    "preview_rows": [ { "Descrição": "erro no servidor", "Data": "2026-01-10" } ],
    "limits": { "max_rows": 5000, "max_upload_bytes": 10485760, "supported_extensions": [".csv", ".xlsx"] }
  }
}
```

**Response 400 (erro de validação):**
```json
{ "success": false, "error": { "code": "FILE_TOO_LARGE", "message": "Arquivo excede o limite de 10 MB." } }
```
Códigos de erro possíveis: `INVALID_FILENAME`, `FILE_TOO_LARGE`, `INVALID_EXTENSION` (ver `FileReader.validate_extension`).

### `POST /api/process`

Confirma o mapeamento de colunas (sugerido ou ajustado pelo usuário) e roda o
pipeline de ingestão + limpeza + classificação sobre o arquivo já enviado.

**Request:** `application/x-www-form-urlencoded` —
`file_id` (do `/api/upload`), `descricao` (nome da coluna de origem, obrigatório),
`data`, `responsavel` (nomes de coluna, opcionais).

**Response 200:**
```json
{
  "success": true,
  "message": "Arquivo processado com sucesso.",
  "data": {
    "file_id": "uploads/<hash>/happy_path.csv",
    "filename": "happy_path.csv",
    "row_count": 42,
    "model_trained": true,
    "mapping": { "Descrição": "descricao" },
    "records": [
      { "descricao": "erro no servidor", "descricao_limpa": "erro servidor", "nivel1": "Incidente", "confianca_n1": 0.94 }
    ]
  }
}
```

**Response 400:** mesmo formato de erro do `/api/upload` (`FILE_NOT_FOUND`, `STORAGE_ERROR`, etc).

### `POST /api/classify`

Classifica um texto avulso (sem upload de arquivo).

**Request:**
```json
{ "texto": "não consigo acessar o sistema, erro 500" }
```

**Response 200:**
```json
{ "nivel1": "Incidente", "nivel2": "Aplicações", "confianca_n1": 0.94, "confianca_n2": 0.81 }
```
Nota: este endpoint não usa o envelope `success/data` — retorna o resultado do `CascadeClassifier.classify()` diretamente. Mantido como está por compatibilidade com consumidores já existentes desse formato.

**Response 503 (nenhum modelo treinado):**
```json
{ "detail": "Classificador indisponível: nenhum modelo treinado encontrado." }
```

### `POST /api/tickets/generate`

Gera tickets estruturados a partir de uma lista de linhas já classificadas manualmente (sem upload).

**Request:**
```json
{
  "rows": [ { "id": "L0001", "descricao": "erro no servidor de produção" } ],
  "format": "json"
}
```

**Response 200:** arquivo para download (`Content-Disposition: attachment`), `application/json` ou `text/csv` conforme `format`:
```json
[
  {
    "id_ticket": "TCK-0001",
    "titulo_sugerido": "erro no servidor de produção — Incidente",
    "tipo_itil": "Incidente",
    "area_responsavel": "Servidor",
    "prioridade": "P1",
    "descricao_original": "erro no servidor de produção",
    "data_geracao": "2026-08-14T12:00:00+00:00",
    "id_origem": "L0001",
    "confianca_n1": 0.94,
    "confianca_n2": 0.88
  }
]
```

### `POST /api/tickets/generate-from-file`

Mesma geração de tickets, mas a partir de um arquivo já enviado/mapeado (form fields iguais ao `/api/process`, mais `format`). Response idêntica ao `/api/tickets/generate`.

> Nota (F1-1): desde esta fase, cada ticket gerado aqui também é persistido no Postgres
> (cadeia `arquivo → registro → texto_processado → classificacao → ticket`, status inicial
> `triagem`) — o download continua funcionando como antes. Se a persistência falhar, a
> request inteira falha com `{ "success": false, "error": { "code": "DB_ERROR", ... } }`
> (sem download). O `id_ticket` no arquivo baixado é o `codigo` real atribuído pela sequence
> `autoitil.ticket_codigo_seq` — o mesmo identificador que aparece depois no Kanban (F1-2).
> `POST /api/tickets/generate` (sem upload) **não** persiste.

---

## 2. Endpoints novos (contrato — Fase 1 implementa)

### `GET /api/tickets` — F1-2

Listagem paginada de tickets persistidos, com filtros.

**Query params:**
| Param | Tipo | Default | Descrição |
|---|---|---|---|
| `page` | int | 1 | Página (1-indexed) |
| `page_size` | int | 20 | Itens por página (máx. 100) |
| `area` | string | — | Filtra por `area_responsavel.nome` (ex.: `Rede`) |
| `prioridade` | string | — | Filtra por `prioridade.codigo` (`P1`-`P4`) |
| `status` | string | — | Filtra por `status_ticket.codigo` (ex.: `triagem`) |
| `busca` | string | — | Busca textual em `ticket.codigo` ou `ticket.titulo_sugerido` |

`descricao_enriquecida` (F2-4) é `null` até alguém pedir a reescrita daquele
ticket específico via `POST /api/tickets/{id}/enrich` — nunca é gerada
automaticamente na ingestão. Quando não é `null`, é um objeto estruturado
`{ "objetivo": string, "requisicoes": string[] | null, "cargo_recomendado":
string | null }` (mesma forma documentada em `POST .../enrich` abaixo) —
não é mais uma string simples.

**Response 200:**
```json
{
  "success": true,
  "data": {
    "items": [
      {
        "id": 1,
        "codigo": "TCK-0001",
        "titulo_sugerido": "erro no servidor de produção — Incidente",
        "descricao_enriquecida": null,
        "tipo_itil": "Incidente",
        "area_responsavel": "Servidor",
        "prioridade": "P1",
        "status": "triagem",
        "confianca_n1": 0.94,
        "confianca_n2": 0.88,
        "feedback_enriquecimento": null,
        "data_geracao": "2026-08-14T12:00:00+00:00",
        "atualizado_em": "2026-08-14T12:00:00+00:00"
      },
      {
        "id": 2,
        "codigo": "TCK-0002",
        "titulo_sugerido": "VPN não conecta — Incidente",
        "descricao_enriquecida": {
          "objetivo": "Resolver a VPN que não está conectando.",
          "requisicoes": ["Verificar configuração de rede.", "Reiniciar o roteador do escritório."],
          "cargo_recomendado": "Suporte de redes."
        },
        "tipo_itil": "Incidente",
        "area_responsavel": "Rede",
        "prioridade": "P2",
        "status": "triagem",
        "confianca_n1": 0.9,
        "confianca_n2": 0.85,
        "feedback_enriquecimento": "up",
        "data_geracao": "2026-08-14T12:05:00+00:00",
        "atualizado_em": "2026-08-14T12:10:00+00:00"
      }
    ],
    "meta": { "page": 1, "page_size": 20, "total": 137, "total_pages": 7 }
  }
}
```

**Response 422 (parâmetro inválido):**
```json
{ "success": false, "error": { "code": "VALIDATION_ERROR", "message": "status inválido: 'foo'. Use um dos: triagem, a_fazer, em_progresso, aguardando_revisao_humana, concluido." } }
```

### `GET /api/tickets/export`

Exporta os tickets já classificados/persistidos em CSV ou XLSX — mesmos filtros de
`GET /api/tickets`, mas sem paginação (retorna tudo que casa com o filtro).

**Query params:**
| Param | Tipo | Default | Descrição |
|---|---|---|---|
| `format` | `"csv"` \| `"xlsx"` | `"csv"` | Formato do arquivo baixado |
| `area` | string | — | Filtra por `area_responsavel.nome` |
| `prioridade` | string | — | Filtra por `prioridade.codigo` (`P1`-`P4`) |
| `status` | string | — | Filtra por `status_ticket.codigo` |
| `busca` | string | — | Busca textual em `ticket.codigo` ou `ticket.titulo_sugerido` |

`descricao_enriquecida` (objeto estruturado quando existe) vira uma string JSON dentro da célula
— CSV/XLSX não representam valor aninhado, e não há colunas separadas pra
`objetivo`/`requisicoes`/`cargo_recomendado` neste endpoint.

Valores de texto que começam com `=`, `+`, `-` ou `@` (podem ser interpretados como fórmula por
Excel/LibreOffice, já que vêm de dado de upload do usuário) recebem um `'` de prefixo antes de
serializar — mitigação de CSV injection.

As colunas do arquivo exportado são derivadas dinamicamente das chaves do dicionário de cada
ticket, então o CSV/XLSX também inclui uma coluna `feedback_enriquecimento` (`"up"`, `"down"` ou
vazia) junto com os demais campos.

**Response 200:** arquivo binário (`Content-Type: text/csv` ou
`application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`), com
`Content-Disposition: attachment; filename="tickets-classificados.<format>"`.

**Response 422 (`format` ou `status` inválido):** mesmo formato de erro de `GET /api/tickets`
acima (`status` inválido é checado à mão; `format` fora de `csv`/`xlsx` é rejeitado
automaticamente pelo FastAPI antes de chegar no handler, com o formato de erro padrão do
framework, não o envelope `{success, error}`).

### `PATCH /api/tickets/{id}` — F1-3

Move um ticket entre colunas do Kanban (atualiza `status_id`). Transição livre
entre quaisquer das 5 colunas — a única validação é que o `status` enviado
exista no catálogo (`status_ticket`); não há restrição de ordem/sequência.

**Request:**
```json
{ "status": "em_progresso" }
```

**Response 200:**
```json
{
  "success": true,
  "message": "Ticket atualizado.",
  "data": {
    "id": 1,
    "codigo": "TCK-0001",
    "status": "em_progresso",
    "atualizado_em": "2026-08-14T13:05:00+00:00"
  }
}
```

**Response 404 (ticket não existe):**
```json
{ "success": false, "error": { "code": "TICKET_NOT_FOUND", "message": "Ticket com id 999 não encontrado." } }
```

**Response 422 (status inválido):**
```json
{ "success": false, "error": { "code": "VALIDATION_ERROR", "message": "status inválido: 'foo'." } }
```

### `PATCH /api/tickets/{id}/revisao`

Registra a revisão humana de Tipo ITIL ou Área de um ticket — a
"confirmação" (mesmo valor) e a "correção" (valor diferente) são tratadas
igual: qualquer revisão vira um rótulo verdadeiro pra acurácia real do
classificador (ver `GET /api/models/quality/reviews`). Além de registrar a
revisão, atualiza a classificação do ticket in-place com o valor
escolhido — o ticket passa a exibir esse valor em todo o resto do sistema.
A Prioridade do ticket nunca muda por causa desta rota.

**Request:**
```json
{ "nivel": "tipo_itil", "valor": "Problema" }
```

`nivel` é `"tipo_itil"` ou `"area"`. `valor` é o nome, não o id (mesma
convenção do `status` em `PATCH /api/tickets/{id}`).

**Response 200:**
```json
{
  "success": true,
  "message": "Revisão registrada.",
  "data": { "id": 1, "codigo": "TCK-0001", "tipo_itil": "Problema", "area_responsavel": "Rede", "...": "..." }
}
```

`data` tem o mesmo formato de item de `GET /api/tickets`.

**Response 404 (ticket não existe):**
```json
{ "success": false, "error": { "code": "TICKET_NOT_FOUND", "message": "Ticket com id 999 não encontrado." } }
```

**Response 422 (nivel ou valor inválido):**
```json
{ "success": false, "error": { "code": "VALIDATION_ERROR", "message": "nivel inválido: 'foo'. Use um dos: tipo_itil, area." } }
```

### `PATCH /api/tickets/{id}/feedback-enriquecimento`

Registra o feedback humano (👍/👎) sobre a descrição enriquecida de um
ticket. Um voto por ticket, sempre o mais recente — chamar de novo com um
`valor` diferente sobrescreve o voto anterior, sem manter histórico. Não
valida se o ticket já tem `descricao_enriquecida` (a UI decide quando
mostrar os botões).

**Request:**
```json
{ "valor": "up" }
```

`valor` é `"up"` ou `"down"`.

**Response 200:**
```json
{
  "success": true,
  "message": "Feedback registrado.",
  "data": { "id": 1, "codigo": "TCK-0001", "feedback_enriquecimento": "up", "...": "..." }
}
```

`data` tem o mesmo formato de item de `GET /api/tickets` (agora incluindo
`feedback_enriquecimento: "up" | "down" | null`).

**Response 404 (ticket não existe):**
```json
{ "success": false, "error": { "code": "TICKET_NOT_FOUND", "message": "Ticket com id 999 não encontrado." } }
```

**Response 422 (valor inválido):**
```json
{ "success": false, "error": { "code": "VALIDATION_ERROR", "message": "valor inválido: 'foo'. Use um dos: up, down." } }
```

### `POST /api/tickets/{id}/enrich` — F2-4

Reescreve a descrição original do ticket via LLM pequeno (protótipo).
Sob demanda — nunca chamado em lote — e idempotente: se
`descricao_enriquecida` já existe, devolve o valor em cache sem rodar o
modelo de novo. Sem corpo de request.

**Response 200 (gerado agora):**
```json
{
  "success": true,
  "message": "Descrição enriquecida com sucesso.",
  "data": { "id": 1, "codigo": "TCK-0001", "descricao_enriquecida": { "objetivo": "Resolver a VPN que não está conectando.", "requisicoes": ["Verificar configuração de rede.", "Reiniciar o roteador do escritório."], "cargo_recomendado": "Suporte de redes." } }
}
```

**Response 200 (já em cache):**
```json
{
  "success": true,
  "message": "Descrição já enriquecida anteriormente (cache).",
  "data": { "id": 1, "descricao_enriquecida": { "objetivo": "Resolver a VPN que não está conectando.", "requisicoes": ["Verificar configuração de rede.", "Reiniciar o roteador do escritório."], "cargo_recomendado": "Suporte de redes." } }
}
```

**Response 404 (ticket não existe):**
```json
{ "success": false, "error": { "code": "TICKET_NOT_FOUND", "message": "Ticket com id 999 não encontrado." } }
```

**Response 503 (modelo indisponível ou geração falhou):**
```json
{ "success": false, "error": { "code": "ENRICHMENT_UNAVAILABLE", "message": "..." } }
```

### `GET /api/models/quality` — F1-4

Expõe `backend/data/processed/metrics_report.json` como JSON puro — consumido
pela tela Métricas do frontend React.

**Response 200:** o conteúdo bruto de `metrics_report.json`:
```json
{
  "generated_at": "2026-08-14T10:00:00+00:00",
  "source": "cv_results",
  "nivel1": {
    "svm_baseline": { "model_name": "svm_baseline", "level": "nivel1", "macro_f1": 0.9112, "per_class": { } },
    "bert": { "model_name": "bert", "level": "nivel1", "macro_f1": 0.9594, "per_class": { } }
  },
  "nivel2": { "svm_baseline": { "macro_f1": 0.7431 }, "bert": { "macro_f1": 0.8048 } }
}
```

**Response 200 (sem relatório gerado ainda):**
```json
{ "nivel1": {}, "nivel2": {} }
```
Não é erro — só ausência de dado.

### `GET /api/models/performance/system-history`

Retorna o histórico de amostras periódicas de CPU%/memória do processo backend, coletadas a cada 60s por uma tarefa em background (ver `app.main`). Aceita `?limit=N` (default 200, máximo 1000). Ordenado por data ascendente (mais antiga primeiro) — pronto pra plotar como série temporal.

**Response 200:**
```json
[
  {
    "cpu_percent": 12.5,
    "memory_rss_mb": 256.3,
    "memory_percent": 15.2,
    "uptime_seconds": 3600.0,
    "coletado_em": "2026-08-28T14:00:00+00:00"
  }
]
```

### `GET /api/models/performance/enrichment-history`

Retorna o histórico de duração e tokens de entrada/saída de cada chamada bem-sucedida do modelo de enriquecimento (Gemma 3, `DescriptionEnricher.enrich()`). Aceita `?limit=N` (default 200, máximo 1000). Ordenado por data ascendente (mais antiga primeiro).

**Response 200:**
```json
[
  {
    "ticket_id": 42,
    "duracao_ms": 18234.5,
    "tokens_entrada": 120,
    "tokens_saida": 60,
    "criado_em": "2026-08-28T14:00:00+00:00"
  }
]
```

### `GET /api/models/performance/classification-history`

Histórico de tempo e tokens de cada chamada do `CascadeClassifier`. Aceita
`?limit=N` (default 200, máximo 1000), ordenado por data ascendente.

Granularidade é por **chamada**, não por ticket: a geração de tickets
classifica linha a linha, e uma linha por ticket faria um upload de 5000
linhas emitir 10.000 INSERTs de telemetria. As chamadas são agregadas por
`(nível, arquitetura)` dentro de cada requisição — `itens` diz quantos
chamados entraram, e `duracao_ms_por_item` já vem dividido, porque lotes de
tamanhos diferentes não são comparáveis por `duracao_ms` cru.

`tokens_entrada` é 0 quando `arquitetura` é `svm` (o baseline não tokeniza
com transformers).

**Response 200:**
```json
[
  {
    "nivel": 1,
    "arquitetura": "bert",
    "duracao_ms": 748.296,
    "tokens_entrada": 304,
    "itens": 15,
    "duracao_ms_por_item": 49.886,
    "criado_em": "2026-09-09T02:33:50+00:00"
  }
]
```

### `GET /api/models/performance/throughput`

Vazão e custo de CPU por chamado, agregados por nível. As divisões são feitas
sobre as **somas** (não como média de médias), porque os lotes têm tamanhos
muito diferentes. `ms_por_chamado_total` é a **soma** dos níveis, não a média:
um chamado atravessa N1 e N2.

`chamados_por_minuto` é a vazão sustentada do modelo em CPU contínua — não
inclui I/O, banco nem rede.

**Response 200:**
```json
{
  "niveis": [
    {
      "nivel": 1,
      "arquitetura": "bert",
      "chamadas": 6,
      "chamados": 78,
      "ms_por_chamado": 54.546,
      "tokens_por_chamado": 20.38,
      "chamados_por_minuto": 1100.0
    }
  ],
  "ms_por_chamado_total": 113.56,
  "chamados_por_minuto_total": 528.4
}
```

### `GET /api/operations/ingestion-funnel`

Funil do pipeline, do upload ao enriquecimento. Cada etapa é contada da sua
própria tabela, nunca derivada da anterior — a diferença entre elas é o
volume perdido no caminho. `percentual_da_base` usa como base a primeira
etapa com volume (normalmente "Linhas lidas"), não o topo fixo: ancorar tudo
em "Uploads" faria as etapas finais sumirem visualmente.

**Response 200:**
```json
{
  "etapas": [
    { "etapa": "Uploads", "total": 2, "percentual_da_base": 0.0667 },
    { "etapa": "Linhas lidas", "total": 30, "percentual_da_base": 1.0 }
  ],
  "base": 30,
  "uploads_falhos": 0,
  "taxa_revisao": 0.2667,
  "taxa_enriquecimento": 0.0
}
```

### `GET /api/models/quality/confusion-matrix`

Matriz de confusão por nível sobre as revisões humanas: `predito` é o que o
modelo classificou, `real` é o que o humano corrigiu. Responde *onde* o
modelo erra, complementando o *quanto* de `/api/models/quality/reviews`.

`celulas` vem **densa** — todas as combinações de rótulos do domínio,
inclusive zeros e classes que nunca apareceram — para o frontend desenhar o
heatmap sem preencher buracos. `acerto: true` marca a diagonal (o humano
confirmou a previsão).

**Response 200:**
```json
{
  "nivel1": {
    "rotulos": ["Incidente", "Problema", "Requisição", "Mudança"],
    "celulas": [
      { "predito": "Incidente", "real": "Incidente", "total": 5, "acerto": true },
      { "predito": "Incidente", "real": "Problema", "total": 1, "acerto": false }
    ],
    "total_revisado": 6,
    "acertos": 5,
    "acuracia": 0.8333
  },
  "nivel2": { "...": "mesma estrutura, com as 5 áreas responsáveis" }
}
```

### `GET /api/models/quality/reviews`

Macro F1 calculado sobre revisões humanas de tickets reais (não sobre o
holdout de treino, que é `GET /api/models/quality`) — reaproveita a mesma função
de cálculo (`evaluate_model`), só troca a origem de `y_true`/`y_pred` pra
`revisao_classificacao`. `macro_f1: null` quando ainda não há nenhuma
revisão completa daquele nível.

**Response 200:**
```json
{
  "nivel1": { "macro_f1": 0.81, "revisados": 42, "total_tickets": 1585 },
  "nivel2": { "macro_f1": 0.77, "revisados": 38, "total_tickets": 1585 }
}
```

### `GET /api/models/quality/enrichment-feedback`

Agregado do feedback humano (👍/👎) sobre descrições enriquecidas.
`percentual_positivo` é calculado sobre `total_votados` (não sobre
`total_enriquecidos`) e é `null` quando ainda não há nenhum voto.

**Response 200:**
```json
{
  "total_enriquecidos": 320,
  "total_votados": 42,
  "positivos": 35,
  "negativos": 7,
  "percentual_positivo": 0.8333333333333334
}
```

### `GET /api/operations/summary` — F1-5

Agregações operacionais para o dashboard (F4-1).

**Response 200:**
```json
{
  "success": true,
  "data": {
    "total_tickets": 137,
    "por_area": [
      { "area": "Servidor", "total": 42 },
      { "area": "Rede", "total": 30 }
    ],
    "por_prioridade": [
      { "prioridade": "P1", "total": 20 },
      { "prioridade": "P2", "total": 55 }
    ],
    "confianca_media": { "nivel1": 0.91, "nivel2": 0.83 },
    "abaixo_do_limiar": {
      "limiar_ativo": 0.75,
      "total": 12
    },
    "tempo_medio_por_coluna": [
      { "status": "triagem", "descricao": "Triagem", "media_horas": 2.4 },
      { "status": "a_fazer", "descricao": "A Fazer", "media_horas": 5.1 }
    ],
    "volume_diario_por_area": [
      { "data": "2026-08-27", "Servidor": 3, "Rede": 1 },
      { "data": "2026-08-28", "Rede": 2 }
    ],
    "volume_diario_por_prioridade": [
      { "data": "2026-08-27", "P1": 2, "P2": 2 },
      { "data": "2026-08-28", "P2": 2 }
    ],
    "taxa_enriquecimento": { "enriquecidos": 40, "total": 137, "percentual": 29.2 }
  }
}
```

---

## 3. Decisões registradas

- **Envelope misto (não 100% consistente):** `/api/classify` e
  `POST /api/tickets/generate` (sem persistir) já existem em produção sem o
  envelope `success/data` — não foram alterados aqui pra não quebrar
  consumidores já existentes desse formato. Os endpoints novos usam envelope
  onde faz sentido (ação com múltiplos motivos de falha) e retornam `data`
  puro onde é só leitura, seguindo o padrão do `/api/health` já implementado.
- **Paginação:** `page`/`page_size` (não `limit`/`offset`) — mais direto pro
  frontend renderizar um paginador clássico.
- **Transições de status:** livres entre as 5 colunas (sem máquina de estados
  restrita) — compatível com drag & drop arbitrário no Kanban (F5-3).
- **Nomenclatura de campos:** em português, espelhando as colunas do schema
  (`db/autoitil_schema_v4.sql`) e o contrato de ticket já usado por
  `generate_ticket()` (`app/tickets/generator.py`) — sem tradução para inglês,
  para manter consistência com o resto do código já escrito.
