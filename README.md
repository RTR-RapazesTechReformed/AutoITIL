# AutoITIL

Pipeline que transforma planilhas de chamados de TI, com colunas e nomes diferentes em cada fonte, em tickets estruturados e classificados segundo o ITIL. A aplicação lê a planilha, mapeia as colunas, classifica cada chamado com NLP e entrega um quadro Kanban com painéis de acompanhamento.

Este repositório é a versão enxuta do projeto, preparada para a apresentação do TCC.

## O que o sistema faz

1. **Ingestão:** recebe `.csv` ou `.xlsx` e mapeia as colunas da planilha para um esquema padrão (busca aproximada, sinônimos e pesos). O usuário confirma o mapeamento.
2. **Classificação em dois níveis:**
   - Nível 1: tipo de chamado (Incidente, Requisição, Problema ou Mudança).
   - Nível 2: área responsável (Aplicações, Banco de Dados, Rede, Segurança ou Servidor).
3. **Geração do ticket:** o ticket recebe prioridade por regra fixa e índice de confiança. Abaixo do limiar de 0,90, ele vai para a coluna "Aguardando Revisão Humana".
4. **Acompanhamento:** Kanban, painel operacional e painel de modelos (qualidade e desempenho).

## Resultados dos modelos

Dataset de 852 chamados balanceados, validação cruzada de 5 folds, métrica F1 macro. Detalhes em [`pesquisa_dos_modelos/docs`](pesquisa_dos_modelos/docs).

| Nível | SVM + TF-IDF | BERTimbau | SetFit |
|---|---|---|---|
| 1 (tipo ITIL) | 0,9112 | **0,9594** | não avaliado |
| 2 (área) | 0,7431 | **0,8048** | 0,7532 |

Com o dataset inicial de 185 chamados, o SVM superava o BERTimbau nos dois níveis. O fator decisivo foi o volume e o balanceamento dos dados.

**Custo computacional (Nível 2; inferência e memória em CPU de 4 núcleos, treino em GPU T4):**

| Métrica | SVM + TF-IDF | BERTimbau | SetFit |
|---|---|---|---|
| Tamanho em disco | 0,5 MB | 436,6 MB | 487,7 MB |
| Inferência por chamado (média) | 0,89 ms | 47,75 ms | 16,15 ms |
| Pico de memória do processo | 170 MB | 1.201 MB | 1.323 MB |
| Treino (por fold) | 0,05 s (CPU) | 2 min 13 s | 3 min 39 s |

O SetFit foi medido com o encoder pré-treinado e uma cabeça logística, sem o ajuste contrastivo: o custo de inferência depende da arquitetura, não dos pesos.

Os números completos e o script de medição estão em [`pesquisa_dos_modelos/results`](pesquisa_dos_modelos/results) e [`pesquisa_dos_modelos/scripts/benchmark_custo.py`](pesquisa_dos_modelos/scripts/benchmark_custo.py).

## Estrutura

```
backend/               API FastAPI (ingestão, classificação, tickets, métricas, autenticação)
frontend/              Interface React + Vite + TypeScript
db/schema.sql          Esquema do PostgreSQL
pesquisa_dos_modelos/  Dataset, notebooks de treino, resultados e benchmark
sample/                Planilhas de exemplo para a demonstração
docs/                  Contrato da API e calibração do limiar de confiança
docker-compose.yml     Postgres, MinIO e (opcional) backend e frontend
```

## Como rodar

Requisitos: Docker, Python 3.11+ e Node 20+.

```bash
# 0. Segredos: copie o modelo e preencha os valores entre < > (openssl rand -hex 32)
cp .env.example .env

# 1. Infraestrutura (Postgres + MinIO)
docker compose up -d

# 2. Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                         # use as mesmas senhas do .env da raiz

# cria o primeiro administrador (nenhuma senha fica no repositório)
ADMIN_EMAIL=<seu-email> ADMIN_PASSWORD='<senha-com-12+-caracteres>' python -m scripts.create_admin

python -m uvicorn app.main:app --reload      # http://localhost:8000
```

```bash
# 3. Frontend (outro terminal)
cd frontend
cp .env.example .env
npm install
npm run dev                                  # http://localhost:5173
```

Para entrar na aplicação, use o e-mail e a senha definidos em `ADMIN_EMAIL` e `ADMIN_PASSWORD` no passo do backend.

Para subir tudo em contêineres: `docker compose --profile app up --build`. O build baixa os modelos do Hugging Face (`EdsonMorro/autoitil-bert-nivel1` e `-nivel2`) e o modelo de enriquecimento `google/gemma-3-1b-it`, que exige aceitar a licença e exportar `HF_TOKEN`.

Para a demonstração, use as planilhas de `sample/`.

## Testes

```bash
cd backend && python -m pytest
cd frontend && npm test
```

## Limitações

- A prioridade é definida só pelo tipo de chamado. No ITIL, ela resulta de impacto e urgência.
- O dataset é majoritariamente sintético (variações geradas por LLM a partir de chamados escritos pela equipe). Uma validação com chamados reais ainda é necessária.
- A configuração de nuvem atende a demonstração, não um ambiente de produção.
