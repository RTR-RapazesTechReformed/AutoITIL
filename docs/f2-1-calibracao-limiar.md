# F2-1 — Calibração do limiar de confiança

`limiar_confianca.valor` é o valor abaixo do qual uma classificação do Nível 1 é
sinalizada para revisão humana (status `aguardando_revisao_humana`).

**Valor atual: `0.900`** (antes: `0.750`).

## Como foi calibrado

A confiança de um chamado é a maior probabilidade softmax do BERTimbau de Nível 1.
Para medir o limiar de forma honesta, a validação cruzada estratificada de 5 folds
(os mesmos folds e hiperparâmetros de `pesquisa_dos_modelos/notebooks/bert_nivel1_training.ipynb`)
foi rodada salvando a confiança de cada chamado **quando ele estava no fold de teste**,
isto é, em um chamado que o modelo não viu no treino.

- Dados: `pesquisa_dos_modelos/results/bert_nivel1_oof_probs.csv` (852 linhas).
- Resultado: 817 acertos e 35 erros (F1 macro agregado 0,9593).
- Confiança média: **0,938** nos acertos e **0,782** nos erros (mediana 0,96 e 0,80).
- 8 dos 35 erros tiveram confiança de 0,90 ou mais: o modelo erra com confiança alta.

| Limiar | Chamados abaixo (revisão humana) | Erros capturados |
|------:|----------------------------------:|-----------------:|
| 0,50 | 0,5% | 0,0% |
| 0,60 | 1,8% | 11,4% |
| 0,70 | 3,1% | 28,6% |
| 0,75 | 4,2% | 31,4% |
| 0,80 | 6,6% | 51,4% |
| 0,85 | 9,4% | 62,9% |
| **0,90** | **14,3%** | **77,1%** |
| 0,95 | 31,5% | 91,4% |

## Decisão

O padrão passou de 0,75 para **0,90**. Com 0,75, só 31,4% dos erros iam para revisão;
com 0,90, vão 77,1%, revisando 14,3% dos chamados. Acima disso o volume de revisão
cresce rápido (31,5% em 0,95) sem ganho proporcional.

Limitações: são 35 erros, então a estimativa é grosseira, e não é uma calibração formal
por curva ROC ou precisão-recall. O valor pode ser mudado a qualquer momento, sem
alterar código, na tabela `limiar_confianca`.

## Por que a análise anterior foi descartada

A versão anterior deste documento calculava o limiar rodando o modelo publicado sobre os
mesmos 852 chamados do treino (in-sample), com 63 erros, e chegava a 0,75. Esses números
não se reproduzem com o modelo hoje publicado no Hugging Face, que acerta 842 dos 852
chamados no treino (10 erros). Em dados vistos no treino o modelo é mais confiante do
que seria em chamados novos; por isso só a análise fora do fold vale como estimativa.

## Onde o valor vive

- `db/schema.sql`: `INSERT INTO limiar_confianca` (valor `0.900`). Em um banco já
  criado, use `UPDATE limiar_confianca SET valor = 0.900 WHERE ativo;`.
- `frontend/src/lib/confidence.ts`: `CONFIDENCE_THRESHOLD`, que espelha o valor do banco
  para sinalizar "baixa confiança" no Kanban e na tabela de ingestão.
- `autoitil.limiar_confianca` é lido em runtime por
  `backend/app/tickets/queries.py::dashboard_summary()` e usado para decidir o status
  inicial do ticket em `backend/app/tickets/persistence.py`.
