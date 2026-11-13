-- =============================================================================
-- AutoITIL — PostgreSQL — v18
-- =============================================================================
-- Mudança em relação à v17 (ver changelog completo no rodapé):
--   1. [REMOVIDO v18] custo_evento, relatorio_custo, relatorio_custo_item e
--      evento_custo — o recurso de relatório de custo por organização foi
--      retirado do produto (API e interface). organizacao permanece, porque
--      usuario.organizacao_id depende dela.
-- =============================================================================
CREATE SCHEMA IF NOT EXISTS autoitil;
SET search_path TO autoitil, public;

-- =============================================================================
-- 1. TABELAS DE REFERÊNCIA
-- =============================================================================

CREATE TABLE prioridade (
    id        SMALLINT     PRIMARY KEY,
    codigo    VARCHAR(2)   NOT NULL UNIQUE,
    descricao VARCHAR(60)  NOT NULL,
    ordem     SMALLINT     NOT NULL UNIQUE,   -- 1 = mais urgente
    CONSTRAINT ck_prioridade_codigo CHECK (codigo IN ('P1', 'P2', 'P3', 'P4'))
);
COMMENT ON TABLE prioridade IS 'RN07 — níveis válidos de prioridade.';

CREATE TABLE tipo_itil (
    id                   SMALLINT    PRIMARY KEY,
    nome                 VARCHAR(30) NOT NULL UNIQUE,
    prioridade_padrao_id SMALLINT    NOT NULL REFERENCES prioridade(id),
    CONSTRAINT ck_tipo_itil_nome
        CHECK (nome IN ('Incidente', 'Requisição', 'Problema', 'Mudança'))
);

CREATE TABLE area_responsavel (
    id   SMALLINT    PRIMARY KEY,
    nome VARCHAR(30) NOT NULL UNIQUE,
    CONSTRAINT ck_area_nome
        CHECK (nome IN ('Aplicações', 'BD', 'Rede', 'Segurança', 'Servidor'))
);

-- Colunas do Kanban. Ordem define a posição visual esquerda->direita.
CREATE TABLE status_ticket (
    id        SMALLINT     PRIMARY KEY,
    codigo    VARCHAR(30)  NOT NULL UNIQUE,
    descricao VARCHAR(60)  NOT NULL,
    ordem     SMALLINT     NOT NULL UNIQUE,
    CONSTRAINT ck_status_ticket_codigo
        CHECK (codigo IN (
            'triagem', 'a_fazer', 'em_progresso',
            'aguardando_revisao_humana', 'concluido'
        ))
);
COMMENT ON TABLE status_ticket IS
    'Colunas do quadro Kanban (frontend F5-1). Substitui o "buraco" da v1, que '
    'não tinha onde persistir a movimentação de um ticket entre estados.';

-- Limiar de confiança versionado, usado para decidir se um ticket nasce em
-- "aguardando_revisao_humana" (backlog F2-1). Índice parcial abaixo garante
-- no máximo um limiar ativo por vez, no mesmo espírito de classificacao.vigente.
CREATE TABLE limiar_confianca (
    id            SMALLINT    GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    valor         NUMERIC(4,3) NOT NULL,
    descricao     VARCHAR(120),
    vigente_desde TIMESTAMPTZ NOT NULL DEFAULT now(),
    ativo         BOOLEAN     NOT NULL DEFAULT TRUE,
    CONSTRAINT ck_limiar_valor CHECK (valor BETWEEN 0 AND 1)
);
COMMENT ON TABLE limiar_confianca IS
    'RN a definir (F2-1) — abaixo deste valor de confianca_n1/n2, o ticket vai '
    'para a coluna "Aguardando Revisão Humana". Versionado para não perder o '
    'threshold vigente no momento em que cada ticket foi roteado.';
CREATE UNIQUE INDEX uq_limiar_confianca_ativo ON limiar_confianca ((1)) WHERE ativo;

-- =============================================================================
-- 2. INGESTÃO
-- =============================================================================

CREATE TABLE arquivo (
    id              BIGINT       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nome_original   VARCHAR(255) NOT NULL,
    extensao        VARCHAR(10)  NOT NULL,
    hash_conteudo   CHAR(64)     NOT NULL,
    tamanho_bytes   INTEGER      NOT NULL,
    total_linhas    INTEGER      NOT NULL,
    storage_backend VARCHAR(10)  NOT NULL DEFAULT 'local',
    storage_uri     VARCHAR(500) NOT NULL,
    data_upload     TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT ck_arquivo_extensao   CHECK (extensao IN ('.csv', '.xlsx')),
    CONSTRAINT ck_arquivo_tamanho    CHECK (tamanho_bytes > 0 AND tamanho_bytes <= 10 * 1024 * 1024),
    CONSTRAINT ck_arquivo_linhas     CHECK (total_linhas BETWEEN 1 AND 5000),
    CONSTRAINT ck_arquivo_storage_backend CHECK (storage_backend IN ('local', 's3')),
    CONSTRAINT ck_arquivo_storage_coerente CHECK (
        (storage_backend = 's3'    AND storage_uri LIKE 's3://%')
        OR
        (storage_backend = 'local' AND storage_uri NOT LIKE 's3://%')
    )
);
COMMENT ON TABLE arquivo IS
    'Metadados de cada upload. O binário em si não fica no Postgres — '
    'storage_uri aponta para onde ele está de fato (S3 em produção, disco '
    'local em dev), e hash_conteudo garante que o arquivo referenciado é '
    'exatamente o que foi processado.';
COMMENT ON COLUMN arquivo.storage_backend IS
    '[NOVO v3] "s3" em produção; "local" em dev/CI para não exigir credenciais '
    'AWS reais rodando a suíte de testes.';
COMMENT ON COLUMN arquivo.storage_uri IS
    '[NOVO v3] URI completa do arquivo bruto. Convenção sugerida em S3: '
    's3://<bucket>/uploads/<hash_conteudo>/<nome_original> — prefixar pelo '
    'hash evita colisão entre arquivos homônimos de uploads diferentes.';

CREATE TABLE mapeamento_coluna (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    arquivo_id      BIGINT       NOT NULL REFERENCES arquivo(id) ON DELETE CASCADE,
    campo_canonico  VARCHAR(20)  NOT NULL,
    coluna_origem   VARCHAR(255) NOT NULL,
    confianca       NUMERIC(4,3),
    confirmado      BOOLEAN      NOT NULL DEFAULT FALSE,
    CONSTRAINT ck_mapeamento_campo
        CHECK (campo_canonico IN ('descricao', 'data', 'responsavel')),
    CONSTRAINT ck_mapeamento_confianca
        CHECK (confianca IS NULL OR confianca BETWEEN 0 AND 1),
    CONSTRAINT uq_mapeamento_campo_por_arquivo
        UNIQUE (arquivo_id, campo_canonico)
);
COMMENT ON TABLE mapeamento_coluna IS
    'Persiste a sugestão do SemanticMapper e a confirmação humana. Trata o passo '
    'de confirmação como decisão de projeto auditável.';
COMMENT ON COLUMN mapeamento_coluna.confirmado IS
    'FALSE = sugestão automática; TRUE = revisada pelo usuário.';

CREATE TABLE registro (
    id                 BIGINT       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    arquivo_id         BIGINT       NOT NULL REFERENCES arquivo(id) ON DELETE CASCADE,
    linha_origem       INTEGER      NOT NULL,
    descricao_original TEXT         NOT NULL,
    data_registro      DATE,
    responsavel        VARCHAR(120),
    CONSTRAINT ck_registro_descricao   CHECK (length(btrim(descricao_original)) > 0),
    CONSTRAINT ck_registro_linha       CHECK (linha_origem > 0),
    CONSTRAINT uq_registro_linha       UNIQUE (arquivo_id, linha_origem)
);
COMMENT ON TABLE registro IS
    'Cada registro pertence a exatamente um arquivo. Descrição '
    'textual obrigatória (data e responsavel são opcionais).';
COMMENT ON COLUMN registro.linha_origem IS
    'Número da linha no arquivo de origem. Com arquivo.hash_conteudo, permite o '
    'trace_back() exigido.';
CREATE INDEX ix_registro_arquivo ON registro (arquivo_id);

CREATE TABLE historico_upload (
    id              BIGINT       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nome_original   VARCHAR(255) NOT NULL,
    extensao        VARCHAR(10)  NOT NULL,
    hash_conteudo   CHAR(64)     NOT NULL,
    tamanho_bytes   INTEGER      NOT NULL,
    storage_uri     VARCHAR(500) NOT NULL,
    status          VARCHAR(20)  NOT NULL DEFAULT 'recebido',
    total_linhas    INTEGER,
    mensagem_erro   TEXT,
    criado_em       TIMESTAMPTZ  NOT NULL DEFAULT now(),
    atualizado_em   TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT ck_historico_upload_status CHECK (
        status IN ('recebido', 'pre_visualizado', 'tickets_gerados', 'falhou')
    ),
    CONSTRAINT ck_historico_upload_extensao CHECK (extensao IN ('.csv', '.xlsx')),
    CONSTRAINT ck_historico_upload_tamanho CHECK (
        tamanho_bytes > 0 AND tamanho_bytes <= 10 * 1024 * 1024
    )
);
COMMENT ON TABLE historico_upload IS
    'Log de todo upload recebido pela aplicação, independente de arquivo/'
    'registro/ticket (sem FK) — inclui uploads abandonados ou que falham '
    'antes de virar tickets. Correlacionado por storage_uri (não por FK), '
    'já que não há threading de um id entre as requisições HTTP do fluxo '
    'de upload -> preview -> geração.';
COMMENT ON COLUMN historico_upload.status IS
    'recebido = arquivo salvo no storage; pre_visualizado = parse/preview '
    'funcionou, total_linhas conhecido; tickets_gerados = fluxo completo; '
    'falhou = erro em qualquer etapa (mensagem_erro populado). Uploads '
    'abandonados simplesmente ficam parados em recebido/pre_visualizado — '
    'não há job de limpeza/expiração.';

CREATE INDEX ix_historico_upload_storage_uri_status
    ON historico_upload (storage_uri, status);

-- =============================================================================
-- 3. PRÉ-PROCESSAMENTO
-- =============================================================================

CREATE TABLE texto_processado (
    id                  BIGINT      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    registro_id         BIGINT      NOT NULL UNIQUE REFERENCES registro(id) ON DELETE CASCADE,
    descricao_limpa     TEXT        NOT NULL,
    glossario_versao    VARCHAR(20),
    data_processamento  TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE texto_processado IS
    '1 registro gera exatamente 1 texto limpo (garantido pelo UNIQUE em '
    'registro_id). Mantido como tabela separada, e não como coluna de registro, '
    'porque protected_terms.txt é explicitamente revisável: reprocessar o mesmo '
    'registro com outro glossário é cenário previsto.';
COMMENT ON COLUMN texto_processado.glossario_versao IS
    'Versão de data/config/protected_terms.txt usada na limpeza.';

-- =============================================================================
-- 4. CLASSIFICAÇÃO
-- =============================================================================

CREATE TABLE modelo (
    id             SMALLINT     GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nome           VARCHAR(80)  NOT NULL,
    arquitetura    VARCHAR(20)  NOT NULL,
    nivel          SMALLINT     NOT NULL,
    versao         VARCHAR(20)  NOT NULL,
    f1_macro       NUMERIC(5,4),
    dataset_versao VARCHAR(20),
    dataset_tamanho INTEGER,
    artefato_uri   VARCHAR(255),
    data_treino    DATE,
    ativo          BOOLEAN      NOT NULL DEFAULT TRUE,
    CONSTRAINT ck_modelo_arquitetura CHECK (arquitetura IN ('svm', 'bert', 'setfit')),
    CONSTRAINT ck_modelo_nivel       CHECK (nivel IN (1, 2, 3)),
    CONSTRAINT ck_modelo_f1          CHECK (f1_macro IS NULL OR f1_macro BETWEEN 0 AND 1),
    CONSTRAINT ck_modelo_dataset_tamanho CHECK (dataset_tamanho IS NULL OR dataset_tamanho > 0),
    CONSTRAINT uq_modelo             UNIQUE (nome, versao)
);
COMMENT ON COLUMN modelo.dataset_versao IS
    'Proveniência do score: docs/modelos mostram que o F1 do BERT Nível 2 '
    'saltou de 0,52 para 0,80 só por mudar de dataset (185 -> 852 tickets). '
    'Sem essa coluna, dois f1_macro diferentes do mesmo modelo ficam ambíguos.';
-- No máximo um modelo ativo por combinação (arquitetura, nível) — evita
-- ambiguidade sobre qual versão o CascadeClassifier deveria carregar.
CREATE UNIQUE INDEX uq_modelo_ativo_por_nivel ON modelo (arquitetura, nivel) WHERE ativo;

CREATE TABLE classificacao (
    id                  BIGINT      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    texto_processado_id BIGINT      NOT NULL REFERENCES texto_processado(id) ON DELETE CASCADE,
    tipo_itil_id        SMALLINT    NOT NULL REFERENCES tipo_itil(id),
    area_id             SMALLINT             REFERENCES area_responsavel(id),
    modelo_n1_id        SMALLINT    NOT NULL REFERENCES modelo(id),
    modelo_n2_id        SMALLINT             REFERENCES modelo(id),
    confianca_n1        NUMERIC(6,5) NOT NULL,
    confianca_n2        NUMERIC(6,5),
    vigente             BOOLEAN     NOT NULL DEFAULT TRUE,
    data_classificacao  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_classificacao_conf_n1 CHECK (confianca_n1 BETWEEN 0 AND 1),
    CONSTRAINT ck_classificacao_conf_n2 CHECK (confianca_n2 IS NULL
                                               OR confianca_n2 BETWEEN 0 AND 1),
    CONSTRAINT ck_classificacao_n2_coerente
        CHECK (num_nulls(area_id, modelo_n2_id, confianca_n2) IN (0, 3))
);
COMMENT ON TABLE classificacao IS
    'RN05 — todo texto processado tem classificação. [DESVIO] O rascunho define '
    '1 texto -> 1 classificação; aqui são permitidas N, com no máximo uma '
    'vigente, para que o mesmo texto possa ser classificado por SVM, BERT e '
    'SetFit e os resultados comparados — que é o objeto do trabalho.';
COMMENT ON COLUMN classificacao.vigente IS
    'Classificação atualmente em uso. O índice parcial abaixo garante no máximo '
    'uma por texto, preservando o espírito do RN05.';
CREATE UNIQUE INDEX uq_classificacao_vigente
    ON classificacao (texto_processado_id)
    WHERE vigente;
CREATE INDEX ix_classificacao_texto  ON classificacao (texto_processado_id);
CREATE INDEX ix_classificacao_modelo ON classificacao (modelo_n1_id, modelo_n2_id);

-- =============================================================================
-- 5. GERAÇÃO DE TICKETS E KANBAN
-- =============================================================================

CREATE TABLE ticket (
    id                   BIGINT       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    classificacao_id     BIGINT       NOT NULL UNIQUE REFERENCES classificacao(id)
                                      ON DELETE RESTRICT,
    codigo               VARCHAR(12)  NOT NULL UNIQUE,
    titulo_sugerido      VARCHAR(120) NOT NULL,
    prioridade_id        SMALLINT     NOT NULL REFERENCES prioridade(id),
    status_id            SMALLINT     NOT NULL REFERENCES status_ticket(id),
    limiar_confianca_id  SMALLINT              REFERENCES limiar_confianca(id),
    descricao_enriquecida TEXT,
    data_geracao         TIMESTAMPTZ  NOT NULL DEFAULT now(),
    atualizado_em        TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT ck_ticket_titulo CHECK (length(titulo_sugerido) BETWEEN 1 AND 120),
    CONSTRAINT ck_ticket_codigo CHECK (codigo ~ '^TCK-[0-9]{4,}$')
);
COMMENT ON TABLE ticket IS
    'RN06 — uma classificação gera 0 ou 1 ticket (UNIQUE em classificacao_id). '
    'RN07 — título, tipo ITIL, área e prioridade obrigatórios: tipo e área vêm '
    'da classificação, evitando duplicar o dado.';
COMMENT ON COLUMN ticket.prioridade_id IS
    'Materializada no momento da geração: se tipo_itil.prioridade_padrao_id '
    'mudar depois, os tickets já emitidos preservam a prioridade original.';
COMMENT ON COLUMN ticket.classificacao_id IS
    'CASCADE -> RESTRICT (desde v2). Protege vw_ticket_rastreavel: não é '
    'possível apagar arquivo/registro/texto_processado/classificacao em '
    'cascata se um ticket já foi emitido a partir deles.';
COMMENT ON COLUMN ticket.status_id IS
    'Coluna atual do Kanban. Mutável — toda alteração deve ser espelhada em '
    'ticket_status_historico pelos triggers abaixo.';
COMMENT ON COLUMN ticket.limiar_confianca_id IS
    'Qual limiar_confianca estava ativo quando o ticket nasceu em '
    '"aguardando_revisao_humana" (ou não). NULL para tickets antigos migrados '
    'antes de o limiar existir.';
COMMENT ON COLUMN ticket.descricao_enriquecida IS
    '[RENOMEADA v7, era descricao_humanizada; NOVO v6, F2-4] Reescrita da '
    'descrição original via LLM pequeno (sob demanda, POST '
    '/api/tickets/{id}/enrich — nunca gerada em massa na ingestão, para '
    'não pagar custo de inferência LLM em lotes de até 5000 linhas). NULL '
    'até o usuário pedir o enriquecimento daquele ticket específico; '
    'depois de gerado, fica em cache aqui (nunca recalculado '
    'automaticamente). Formato: JSON com objetivo (str), requisicoes '
    '(list[str]), cargo_recomendado (str).';
CREATE INDEX ix_ticket_prioridade ON ticket (prioridade_id);
CREATE INDEX ix_ticket_data       ON ticket (data_geracao);
CREATE INDEX ix_ticket_status     ON ticket (status_id);

-- Histórico de movimentação no Kanban — dá rastreabilidade de estado e
-- permite calcular "tempo médio por coluna" para o dashboard operacional
-- (backlog F4-1) sem esforço extra de modelagem.
CREATE TABLE ticket_status_historico (
    id             BIGINT      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ticket_id      BIGINT      NOT NULL REFERENCES ticket(id) ON DELETE CASCADE,
    status_id      SMALLINT    NOT NULL REFERENCES status_ticket(id),
    data_transicao TIMESTAMPTZ NOT NULL DEFAULT now(),
    observacao     VARCHAR(255)
);
COMMENT ON TABLE ticket_status_historico IS
    'Uma linha por transição de status do ticket, incluindo a criação (status '
    'inicial). Alimentada automaticamente pelo trigger trg_ticket_status '
    '(AFTER, desde v4).';
CREATE INDEX ix_ticket_status_historico_ticket
    ON ticket_status_historico (ticket_id, data_transicao);

-- Trigger 1/2: mantém ticket.atualizado_em coerente. Precisa ser BEFORE
-- porque só um trigger BEFORE pode alterar a linha (NEW) antes de gravar.
CREATE OR REPLACE FUNCTION fn_atualizar_ticket_timestamp() RETURNS TRIGGER AS $$
BEGIN
    -- Em INSERT, OLD não existe (não apenas NULL — não-atribuído): checar
    -- TG_OP = 'INSERT' primeiro e nunca referenciar OLD nesse ramo, já que o
    -- Postgres não garante short-circuit em OR.
    IF TG_OP = 'INSERT' THEN
        NEW.atualizado_em := now();
    ELSIF NEW.status_id IS DISTINCT FROM OLD.status_id THEN
        NEW.atualizado_em := now();
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_ticket_atualizado_em
    BEFORE INSERT OR UPDATE OF status_id ON ticket
    FOR EACH ROW
    EXECUTE FUNCTION fn_atualizar_ticket_timestamp();

-- Trigger 2/2: registra a transição em ticket_status_historico. Precisa ser
-- AFTER — [FIX v4] em BEFORE INSERT a linha de ticket ainda não existe na
-- tabela, e a FK ticket_status_historico.ticket_id -> ticket.id falhava em
-- toda inserção de ticket (violação de FK). Em AFTER, o ticket já foi
-- gravado e NEW.id é uma referência válida.
CREATE OR REPLACE FUNCTION fn_registrar_transicao_status() RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO ticket_status_historico (ticket_id, status_id)
        VALUES (NEW.id, NEW.status_id);
    ELSIF NEW.status_id IS DISTINCT FROM OLD.status_id THEN
        INSERT INTO ticket_status_historico (ticket_id, status_id)
        VALUES (NEW.id, NEW.status_id);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_ticket_status
    AFTER INSERT OR UPDATE OF status_id ON ticket
    FOR EACH ROW
    EXECUTE FUNCTION fn_registrar_transicao_status();

-- =============================================================================
-- 6. VISÃO DE RASTREABILIDADE
-- Dado um código de ticket, devolve a origem completa do dado — incluindo,
-- desde v3, onde o arquivo bruto está fisicamente armazenado.
-- =============================================================================

CREATE VIEW vw_ticket_rastreavel AS
SELECT
    t.codigo                AS ticket,
    t.titulo_sugerido,
    st.descricao            AS status,
    ti.nome                 AS tipo_itil,
    ar.nome                 AS area_responsavel,
    p.codigo                AS prioridade,
    c.confianca_n1,
    c.confianca_n2,
    m1.nome                 AS modelo_nivel1,
    m2.nome                 AS modelo_nivel2,
    r.descricao_original,
    r.linha_origem,
    a.nome_original         AS arquivo,
    a.hash_conteudo,
    a.storage_backend,      -- [NOVO v3]
    a.storage_uri,          -- [NOVO v3]
    a.data_upload,
    t.atualizado_em
FROM ticket t
    JOIN classificacao     c  ON c.id  = t.classificacao_id
    JOIN texto_processado  tx ON tx.id = c.texto_processado_id
    JOIN registro          r  ON r.id  = tx.registro_id
    JOIN arquivo           a  ON a.id  = r.arquivo_id
    JOIN tipo_itil         ti ON ti.id = c.tipo_itil_id
    JOIN prioridade        p  ON p.id  = t.prioridade_id
    JOIN status_ticket     st ON st.id = t.status_id
    JOIN modelo            m1 ON m1.id = c.modelo_n1_id
    LEFT JOIN area_responsavel ar ON ar.id = c.area_id
    LEFT JOIN modelo           m2 ON m2.id = c.modelo_n2_id;

-- =============================================================================
-- 7. CARGA INICIAL DOS DOMÍNIOS
-- =============================================================================

INSERT INTO prioridade (id, codigo, descricao, ordem) VALUES
    (1, 'P1', 'Crítica — indisponibilidade ou impacto amplo', 1),
    (2, 'P2', 'Alta — degradação relevante do serviço',       2),
    (3, 'P3', 'Média — demanda planejável',                   3),
    (4, 'P4', 'Baixa — sem impacto operacional imediato',     4);

-- Reproduz data/config/priority_rules.json
INSERT INTO tipo_itil (id, nome, prioridade_padrao_id) VALUES
    (1, 'Incidente',  1),
    (2, 'Problema',   2),
    (3, 'Requisição', 3),
    (4, 'Mudança',    4);

INSERT INTO area_responsavel (id, nome) VALUES
    (1, 'Aplicações'),
    (2, 'BD'),
    (3, 'Rede'),
    (4, 'Segurança'),
    (5, 'Servidor');

-- Colunas do Kanban (backlog F5-1)
INSERT INTO status_ticket (id, codigo, descricao, ordem) VALUES
    (1, 'triagem',                   'Triagem',                    1),
    (2, 'a_fazer',                   'A Fazer',                    2),
    (3, 'em_progresso',              'Em Progresso',               3),
    (4, 'aguardando_revisao_humana', 'Aguardando Revisão Humana',  4),
    (5, 'concluido',                 'Concluído',                  5);

-- F2-1 — limiar de confiança do Nível 1: 0.900, recalibrado com as probabilidades
-- do BERTimbau fora do fold (validação cruzada de 5 folds sobre os 852 exemplos de
-- pesquisa_dos_modelos/data/dataset.csv; dados em
-- pesquisa_dos_modelos/results/bert_nivel1_oof_probs.csv). Nesse corte, são 35
-- erros em 852 chamados; confiança média em acertos = 0.938, em erros = 0.782:
--   limiar 0.75 -> 4.2% dos chamados abaixo (revisão humana), captura 31.4% dos erros
--   limiar 0.80 -> 6.6% abaixo, captura 51.4%
--   limiar 0.90 -> 14.3% abaixo, captura 77.1%   (valor adotado)
-- O padrão anterior (0.750) vinha de uma estimativa no treino, mais otimista.
-- Ver detalhamento em docs/f2-1-calibracao-limiar.md.
-- Bancos já criados com o valor antigo: UPDATE limiar_confianca SET valor = 0.900 WHERE ativo;
INSERT INTO limiar_confianca (valor, descricao, ativo) VALUES
    (0.900, 'Recalibrado em F2-1 (BERT nível 1, 852 exemplos fora do fold): captura 77.1% dos erros revisando 14.3% dos chamados', TRUE);

-- Modelos publicados (F1 macro em CV 5-fold sobre 852 tickets, ver
-- docs/modelos/04_comparacao_geral.md). artefato_uri NULL = pendente.
INSERT INTO modelo (nome, arquitetura, nivel, versao, f1_macro, dataset_versao, dataset_tamanho, artefato_uri, ativo) VALUES
    ('svm-nivel1',    'svm',    1, '1.0', 0.9112, '852', 852, NULL, TRUE),
    ('svm-nivel2',    'svm',    2, '1.0', 0.7431, '852', 852, NULL, TRUE),
    ('bert-nivel1',   'bert',   1, '1.0', 0.9594, '852', 852, NULL, TRUE),
    ('bert-nivel2',   'bert',   2, '1.0', 0.8048, '852', 852, NULL, TRUE),
    ('setfit-nivel2', 'setfit', 2, '1.0', NULL,   '852', 852, NULL, FALSE);

-- =============================================================================
-- 8. OBSERVABILIDADE E MÉTRICAS
-- =============================================================================

CREATE TABLE metrica_sistema (
    id              BIGINT        GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    cpu_percent     NUMERIC(7,3)  NOT NULL,
    memory_rss_mb   NUMERIC(12,3) NOT NULL,
    memory_percent  NUMERIC(7,3)  NOT NULL,
    uptime_seconds  NUMERIC(14,3) NOT NULL,
    coletado_em     TIMESTAMPTZ   NOT NULL DEFAULT now()
);
COMMENT ON TABLE metrica_sistema IS
    'Amostras periódicas (a cada 60s, via tarefa em background em app.main) '
    'de CPU%/memória do processo do backend, independente de qualquer outra '
    'tabela (sem FK) — histórico pra análise de uso ao longo do tempo.';
CREATE INDEX ix_metrica_sistema_coletado_em ON metrica_sistema (coletado_em);

CREATE TABLE metrica_enriquecimento (
    id              BIGINT        GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ticket_id       BIGINT,
    duracao_ms      NUMERIC(12,3) NOT NULL,
    tokens_entrada  INTEGER       NOT NULL,
    tokens_saida    INTEGER       NOT NULL,
    criado_em       TIMESTAMPTZ   NOT NULL DEFAULT now(),
    CONSTRAINT ck_metrica_enriquecimento_tokens CHECK (
        tokens_entrada > 0 AND tokens_saida >= 0
    )
);
COMMENT ON TABLE metrica_enriquecimento IS
    'Tempo de execução e contagem de tokens de cada chamada bem-sucedida de '
    'DescriptionEnricher.enrich() (Gemma 3). ticket_id é referência solta, '
    'sem FK — não bloqueia a métrica se o ticket for removido/inexistente.';
CREATE INDEX ix_metrica_enriquecimento_criado_em ON metrica_enriquecimento (criado_em);

-- Uma linha por CHAMADA do classificador, não por ticket: predict_batch()
-- processa até MAX_ROWS (5000) textos de uma vez, e uma linha por ticket
-- transformaria a ingestão em milhares de INSERTs. `itens` preserva a
-- divisão duracao_ms/itens para quem quiser custo por chamado.
CREATE TABLE metrica_classificacao (
    id             BIGINT        GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nivel          SMALLINT      NOT NULL,
    arquitetura    VARCHAR(10)   NOT NULL,
    duracao_ms     NUMERIC(12,3) NOT NULL,
    tokens_entrada INTEGER       NOT NULL,
    itens          INTEGER       NOT NULL DEFAULT 1,
    criado_em      TIMESTAMPTZ   NOT NULL DEFAULT now(),
    CONSTRAINT ck_metrica_classificacao_nivel       CHECK (nivel IN (1, 2)),
    CONSTRAINT ck_metrica_classificacao_arquitetura CHECK (arquitetura IN ('bert', 'svm')),
    CONSTRAINT ck_metrica_classificacao_duracao     CHECK (duracao_ms >= 0),
    CONSTRAINT ck_metrica_classificacao_tokens      CHECK (tokens_entrada >= 0),
    CONSTRAINT ck_metrica_classificacao_itens       CHECK (itens > 0)
);
COMMENT ON TABLE metrica_classificacao IS
    'Tempo, tokens e tamanho de lote de cada chamada bem-sucedida do '
    'CascadeClassifier (BertClassifier N1/N2, ou SVM no fallback). Uma linha '
    'por chamada — `itens` diz quantos textos foram classificados nela.';
COMMENT ON COLUMN metrica_classificacao.itens IS
    'Textos processados nesta chamada: 1 em predict(), N em predict_batch().';
COMMENT ON COLUMN metrica_classificacao.tokens_entrada IS
    'Total de tokens de entrada do lote (soma das linhas do input_ids, já '
    'truncado em MAX_LENGTH). Zero quando arquitetura = svm, que não tokeniza '
    'com transformers.';
CREATE INDEX ix_metrica_classificacao_criado_em ON metrica_classificacao (criado_em);

-- =============================================================================
-- 9. REVISÃO HUMANA DE CLASSIFICAÇÃO
-- =============================================================================

CREATE TABLE revisao_classificacao (
    id                      BIGINT      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ticket_id               BIGINT      NOT NULL REFERENCES ticket(id),
    tipo_itil_original_id   SMALLINT    REFERENCES tipo_itil(id),
    tipo_itil_revisado_id   SMALLINT    REFERENCES tipo_itil(id),
    tipo_itil_revisado_em   TIMESTAMPTZ,
    area_original_id        SMALLINT    REFERENCES area_responsavel(id),
    area_revisado_id        SMALLINT    REFERENCES area_responsavel(id),
    area_revisado_em        TIMESTAMPTZ,
    CONSTRAINT uq_revisao_classificacao_ticket UNIQUE (ticket_id)
);
COMMENT ON TABLE revisao_classificacao IS
    'Uma linha por ticket revisado por um humano (Tipo ITIL e/ou Área). '
    '*_original_id só é gravado na primeira revisão daquele nível (snapshot '
    'da predição do modelo) e nunca é sobrescrito depois — é o y_pred fixo '
    'usado por app.evaluation.real_accuracy pra calcular acurácia real sobre '
    'tickets de produção. *_revisado_id/*_revisado_em são atualizados a cada '
    'nova revisão daquele nível — é o y_true mais recente.';

-- =============================================================================
-- 10. FEEDBACK DE ENRIQUECIMENTO
-- =============================================================================

CREATE TABLE feedback_enriquecimento (
    id            BIGINT      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ticket_id     BIGINT      NOT NULL REFERENCES ticket(id),
    valor         VARCHAR(4)  NOT NULL,
    criado_em     TIMESTAMPTZ NOT NULL DEFAULT now(),
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_feedback_enriquecimento_ticket UNIQUE (ticket_id),
    CONSTRAINT ck_feedback_enriquecimento_valor CHECK (valor IN ('up', 'down'))
);
COMMENT ON TABLE feedback_enriquecimento IS
    'Uma linha por ticket com feedback humano sobre a descrição enriquecida '
    'gerada pelo Gemma 3. valor guarda sempre o voto mais recente — sem '
    'histórico de votos anteriores e sem opção de remover, só trocar entre '
    'up e down.';

-- =============================================================================
-- 11. ORGANIZAÇÕES (v14)
-- =============================================================================

CREATE TABLE organizacao (
    id        BIGINT       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nome      VARCHAR(255) NOT NULL,
    ativo     BOOLEAN      NOT NULL DEFAULT true,
    criado_em TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT uq_organizacao_nome UNIQUE (nome)
);
COMMENT ON TABLE organizacao IS
    'Cliente/tenant do AutoITIL, usado pra segmentar o acesso. Onboarding '
    'manual via seed SQL — sem tela de cadastro nesta entrega. usuario.organizacao_id '
    'referencia esta tabela; toda conta pertence a exatamente uma '
    'organização.';

-- Seed da organização padrão
INSERT INTO organizacao (nome) VALUES ('Organização Padrão');

-- =============================================================================
-- 12. USUÁRIOS
-- =============================================================================

CREATE TABLE usuario (
    id            BIGINT       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    organizacao_id BIGINT       NOT NULL REFERENCES organizacao(id),
    email         VARCHAR(255) NOT NULL,
    senha_hash    VARCHAR(255) NOT NULL,
    is_admin      BOOLEAN      NOT NULL DEFAULT false,
    ativo         BOOLEAN      NOT NULL DEFAULT true,
    criado_em     TIMESTAMPTZ  NOT NULL DEFAULT now(),
    atualizado_em TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT uq_usuario_email UNIQUE (email)
);
COMMENT ON TABLE usuario IS
    'Contas do time com acesso à API — autenticação via login (email+senha) '
    'e sessão JWT (ver app.auth). Sem cadastro público: só um usuário '
    'is_admin=true pode criar novas contas (POST /api/admin/usuarios).';

-- Não há usuário semeado: o primeiro administrador é criado com
-- `python -m scripts.create_admin` (ver README), com e-mail e senha lidos de
-- variáveis de ambiente, para que nenhuma credencial fique no repositório.

-- =============================================================================
-- SEQUENCES DE NEGÓCIO
-- =============================================================================

-- Gera o número usado em ticket.codigo (formato TCK-NNNN), desacoplado do
-- ticket.id (PK interna) — permite numeração de negócio estável mesmo se a
-- PK precisar ser recriada/migrada no futuro.
CREATE SEQUENCE IF NOT EXISTS ticket_codigo_seq
    START WITH 1 INCREMENT BY 1;

-- =============================================================================
-- CHANGELOG v14 -> v15
-- =============================================================================
-- ADICIONADO
--   - organizacao, preco_evento, fatura, fatura_item, evento_cobravel —
--     fundação de faturamento multi-tenant. usuario.organizacao_id
--     (NOT NULL) amarra toda conta a uma organização.
-- NÃO ALTERADO
--   - Nenhuma outra tabela/coluna/view mudou nesta versão.
-- =============================================================================

-- =============================================================================
-- CHANGELOG v15 -> v16
-- =============================================================================
-- ALTERADO
--   - fatura.ck_fatura_periodo: periodo_fim > periodo_inicio (era >=) —
--     fecha a brecha de período vazio/invertido.
--   - organizacao.nome agora é UNIQUE (uq_organizacao_nome).
-- NÃO ALTERADO
--   - Nenhuma outra tabela/coluna/view mudou nesta versão.
-- =============================================================================

-- =============================================================================
-- CHANGELOG v16 -> v17
-- =============================================================================
-- RENOMEADO
--   - preco_evento -> custo_evento (e colunas preco_* -> custo_*).
--   - fatura -> relatorio_custo.
--   - fatura_item -> relatorio_custo_item (fatura_id -> relatorio_custo_id,
--     valor_total_centavos -> custo_total_centavos).
--   - evento_cobravel -> evento_custo (preco_unitario_centavos ->
--     custo_unitario_centavos, valor_centavos -> custo_centavos,
--     fatura_id -> relatorio_custo_id).
--   - Constraints/índices correspondentes renomeados (ver migração 011).
-- NÃO ALTERADO
--   - Nenhum dado, coluna nova ou tipo mudou — é rename puro. O recurso
--     nunca foi cobrança real de cliente, é dashboard interna de custo.
-- =============================================================================

-- =============================================================================
-- CHANGELOG v17 -> v18
-- =============================================================================
-- REMOVIDO
--   - custo_evento, relatorio_custo, relatorio_custo_item, evento_custo (e o
--     índice ix_evento_custo_org_periodo) — relatório de custo retirado do
--     produto. Em um banco já criado com a v17:
--       DROP TABLE IF EXISTS autoitil.evento_custo, autoitil.relatorio_custo_item,
--                            autoitil.relatorio_custo, autoitil.custo_evento;
-- NÃO ALTERADO
--   - organizacao e usuario.organizacao_id continuam iguais.
-- =============================================================================

-- =============================================================================
-- CHANGELOG v12 -> v13
-- =============================================================================
-- ADICIONADO
--   - metrica_classificacao -> tempo de execução, tokens de entrada e tamanho
--     de lote de cada chamada do CascadeClassifier (BERT N1/N2 ou SVM no
--     fallback), gravada por app.domain.classification_metrics.
--     Motivação: metrica_enriquecimento (v9) media só o Gemma 3, chamado sob
--     demanda um ticket por vez. A classificação roda em TODA linha de TODO
--     upload — é o caminho mais quente do pipeline e o que mais consome CPU —
--     e não era medida, então não havia como responder "quanto custa triar N
--     chamados".
--     Granularidade por CHAMADA, não por ticket: predict_batch() classifica
--     até MAX_ROWS (5000) textos numa passada; uma linha por ticket faria a
--     ingestão emitir milhares de INSERTs concorrendo com a própria gravação
--     dos tickets. `itens` guarda o tamanho do lote, então duracao_ms/itens
--     continua dando o custo por chamado.
-- NÃO ALTERADO
--   - Nenhuma tabela, coluna, view ou carga inicial existente mudou.
-- =============================================================================

-- =============================================================================
-- CHANGELOG v11 -> v12
-- =============================================================================
-- ADICIONADO
--   - usuario: contas do time com login (email+senha) e sessão JWT,
--     substituindo a API_KEY única compartilhada. O primeiro admin é criado com scripts/create_admin.py (sem senha no repositório).
-- NÃO ALTERADO
--   - Nenhuma tabela/coluna/view existente mudou nesta versão.
-- =============================================================================

-- =============================================================================
-- CHANGELOG v10 -> v11
-- =============================================================================
-- ADICIONADO
--   - feedback_enriquecimento: feedback humano (👍/👎) sobre a descrição
--     enriquecida de um ticket (botões no modal de detalhe do Kanban) —
--     um voto por ticket, sempre o mais recente (trocar de 👍 pra 👎
--     sobrescreve, sem histórico). Agregado em
--     GET /api/metrics/enrichment-feedback.
-- NÃO ALTERADO
--   - Nenhuma outra tabela/coluna/view mudou nesta versão.
-- =============================================================================

-- =============================================================================
-- CHANGELOG v9 -> v10
-- =============================================================================
-- ADICIONADO
--   - revisao_classificacao: revisão humana de Tipo ITIL/Área por ticket
--     (chip editável no modal de detalhe do Kanban), usada para calcular
--     acurácia real do classificador sobre tickets de produção — nunca
--     sobrescreve a predição original snapshotada, só o valor revisado.
--     Revisar também atualiza classificacao.tipo_itil_id/.area_id in-place
--     (Classificacao é 1:1 por ticket, nunca compartilhada), mas nunca
--     ticket.prioridade_id.
-- NÃO ALTERADO
--   - Nenhuma outra tabela/coluna/view mudou nesta versão.
-- =============================================================================

-- =============================================================================
-- CHANGELOG v8 -> v9
-- =============================================================================
-- ADICIONADO
--   - metrica_sistema: amostras periódicas de CPU/memória do processo do
--     backend, coletadas por uma tarefa em background (ver app.main).
--   - metrica_enriquecimento: tempo de execução e tokens de entrada/saída de
--     cada chamada bem-sucedida do Gemma 3 (DescriptionEnricher.enrich()).
--     Ambas independentes (sem FK), mesmo espírito de historico_upload.
-- NÃO ALTERADO
--   - Nenhuma outra tabela/coluna/view mudou nesta versão.
-- =============================================================================

-- =============================================================================
-- CHANGELOG v7 -> v8
-- =============================================================================
-- ADICIONADO
--   - historico_upload: log de todo upload recebido, independente de
--     arquivo/registro/ticket (sem FK) — cobre rastreabilidade de uploads
--     abandonados ou que falham antes de virar tickets.
-- NÃO ALTERADO
--   - Nenhuma outra tabela/coluna/view mudou nesta versão.
-- =============================================================================

-- =============================================================================
-- CHANGELOG v6 -> v7
-- =============================================================================
-- RENOMEADO
--   - ticket.descricao_humanizada -> ticket.descricao_enriquecida (rename da
--     feature F2-4: "Humanização" -> "Enriquecimento"). Mesma
--     coluna TEXT, mesmo propósito; só o nome mudou, para refletir que o
--     LLM complementa a descrição, não a "torna mais humana". O formato do
--     JSON armazenado também muda: campo requisicoes vira uma lista de
--     strings em vez de uma string única.
-- NÃO ALTERADO
--   - Nenhuma outra tabela/coluna/view mudou nesta versão.
-- =============================================================================

-- =============================================================================
-- CHANGELOG v5 -> v6
-- =============================================================================
-- ADICIONADO
--   - ticket.descricao_humanizada (TEXT, nullable) -> cache da reescrita da
--     descrição original via LLM pequeno (F2-4), usada por
--     backend/app/enrichment/humanizer.py e populada sob demanda via
--     POST /api/tickets/{id}/humanize (nunca em massa na ingestão — rodar
--     um LLM por linha em lotes de até 5000 registros seria proibitivamente
--     lento sem GPU dedicada). NULL até o usuário pedir a humanização.
-- NÃO ALTERADO
--   - Nenhuma outra tabela/coluna/view mudou nesta versão.
-- =============================================================================

-- =============================================================================
-- CHANGELOG v4 -> v5
-- =============================================================================
-- ADICIONADO
--   - autoitil.ticket_codigo_seq -> sequence dedicada para gerar ticket.codigo
--     (formato TCK-NNNN) de forma atômica e globalmente única, usada por
--     backend/app/tickets/persistence.py (F1-1). Antes, o código era gerado
--     só dentro do escopo de um request (generate_ticket()), sem garantia de
--     unicidade entre uploads diferentes.
-- NÃO ALTERADO
--   - Nenhuma tabela/coluna/view mudou nesta versão.
-- =============================================================================

-- =============================================================================
-- CHANGELOG v3 -> v4
-- =============================================================================
-- CORRIGIDO
--   - trg_ticket_status era BEFORE INSERT OR UPDATE OF status_id e sua função
--     (fn_registrar_transicao_status) tentava INSERT INTO
--     ticket_status_historico (ticket_id, ...) VALUES (NEW.id, ...) dentro do
--     próprio BEFORE INSERT do ticket. Como o BEFORE roda antes de a linha
--     ser gravada em `ticket`, a FK ticket_status_historico.ticket_id ->
--     ticket.id nunca era satisfeita, e QUALQUER INSERT INTO ticket falhava
--     com IntegrityError (achado durante a revisão final da branch F0-2,
--     rodando o schema pela primeira vez contra um Postgres de verdade).
--   - Dividido em dois triggers:
--       trg_ticket_atualizado_em (BEFORE INSERT OR UPDATE OF status_id) ->
--         só ajusta NEW.atualizado_em, o único efeito que precisa mesmo
--         acontecer antes da gravação.
--       trg_ticket_status (AFTER INSERT OR UPDATE OF status_id) -> grava o
--         histórico, agora com o ticket já existindo de fato na tabela.
-- NÃO ALTERADO
--   - Nenhuma tabela, coluna, view ou carga inicial mudou nesta versão —
--     é uma correção pontual de trigger, sem impacto em nenhum dos módulos
--     Python (nenhum código do backend referencia os triggers diretamente).
-- =============================================================================
