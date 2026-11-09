# F2-1 — Calibração do limiar de confiança

Item do backlog: `F2-1 | Modelos | Calibrar limiar de confiança (D8)`.

## Contexto

`autoitil.limiar_confianca` guarda o valor abaixo do qual uma classificação
automática deve ser sinalizada para revisão humana (status
`aguardando_revisao_humana`). Desde o schema v3 esse valor era um placeholder
(`0.750`, comentário "provisório — recalibrar em F2-1 com dados reais de CV").

## O que os artefatos de pesquisa já tinham

`pesquisa_dos_modelos/notebooks/bert_nivel1_cv_results.json` guarda apenas
métricas agregadas da validação cruzada 5-fold: `f1_macro_mean`,
`f1_macro_std`, `oof_classification_report`. **Não guarda a confiança
(probabilidade softmax) por exemplo**, então não é possível reconstruir uma
curva ROC / precisão-recall por limiar a partir do que já foi produzido pela
pesquisa — isso exigiria rodar novamente a validação cruzada salvando as
probabilidades OOF, o que está fora do escopo deste item (seria uma mudança
na pesquisa, não na aplicação).

## O que foi feito em vez disso

Para chegar a um valor defensável sem essa reformulação da pesquisa, rodei o
`BertClassifier` de nível 1 já treinado e publicado (`app.classification.
bert_classifier.BertClassifier`, baixado do Hugging Face Hub via
`hub_repo_id`) contra os 852 exemplos rotulados de
`pesquisa_dos_modelos/data/dataset.csv` e comparei a confiança (softmax do
argmax) entre previsões corretas e incorretas.

**Importante — isso é in-sample, não out-of-fold.** O modelo foi treinado
usando esses mesmos 852 exemplos (com CV para validação, mas o modelo final
publicado é treinado no dataset inteiro). Os números abaixo são indicativos
da forma da distribuição de confiança do modelo, não uma medida honesta de
erro em dados nunca vistos — o erro real em produção tende a ser mais alto
do que os "confiança média em erros" sugerem aqui, porque em dados de treino
o modelo tende a estar mais confiante (inclusive nos erros) do que estaria em
dados genuinamente novos.

### Resultado

- 852 exemplos, 789 acertos / 63 erros
- confiança média em acertos: **0.908**
- confiança média em erros: **0.682** (min 0.403, max 0.952)

| limiar | % tickets abaixo (revisão humana) | % dos erros capturados |
|-------:|-----------------------------------:|------------------------:|
| 0.50   | 2.0%  | 14.3% |
| 0.60   | 4.7%  | 34.9% |
| 0.70   | 8.8%  | 55.6% |
| **0.75** | **11.7%** | **60.3%** |
| 0.80   | 15.6% | 69.8% |
| 0.85   | 19.7% | 79.4% |
| 0.90   | 27.5% | 93.7% |
| 0.95   | 56.6% | 98.4% |

## Decisão

Mantive **0.750** como valor de `limiar_confianca.valor`. É o ponto em que a
curva já capturou a maioria dos erros claros (60.3%) sem empurrar um volume
grande demais de tickets para revisão humana (11.7%) — subir para 0.80 ou
0.85 aumenta a captura de erros de forma modesta (+9.5pp e +19.1pp) ao custo
de quase dobrar o volume de revisão (15.6% e 19.7%). Como a curva real
(out-of-fold) tende a ser mais achatada que a in-sample, um limiar mais
conservador que 0.75 arriscaria sinalizar uma fração enorme dos tickets para
revisão manual sem ganho proporcional — o que na prática anularia o valor da
automação.

**Isso não é uma calibração ROC rigorosa** — é uma estimativa honesta com o
que os artefatos existentes permitem, documentada explicitamente como tal.
Se a pesquisa vier a salvar as probabilidades OOF por fold no futuro, esse
valor deve ser recalibrado com uma curva precisão-recall de verdade.

## Onde o valor vive

- `db/autoitil_schema_v5.sql` (carregado integralmente em v6, F2-4) —
  `INSERT INTO limiar_confianca` (comentário atualizado para refletir esta
  calibração, valor numérico inalterado).
- `autoitil.limiar_confianca` é lido em runtime por
  `backend/app/tickets/queries.py::dashboard_summary()` e usado para decidir
  o status inicial do ticket em `backend/app/tickets/persistence.py`.
