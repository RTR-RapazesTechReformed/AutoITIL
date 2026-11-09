# Nível 2 (área responsável) — SetFit

> **Status: em execução.** Este documento registra a decisão e a configuração; os números finais (dataset de 852 tickets) serão preenchidos assim que o treino no Colab terminar. Enquanto isso, os números de uma rodada anterior (dataset de 185 tickets, antes da expansão) ficam abaixo só como referência histórica — **não usar no TCC**, servem apenas de sanidade.

## Por que SetFit

SetFit ([Tunstall et al., 2022](https://arxiv.org/abs/2209.11055)) é uma técnica de fine-tuning **contrastivo** para few-shot learning: em vez de treinar um classificador do zero, ajusta um *sentence-transformer* pré-treinado usando pares de exemplos (similar/diferente) e depois treina uma cabeça de classificação leve (logistic regression) sobre os embeddings resultantes.

Foi trazida ao projeto como uma terceira via de comparação, complementar ao SVM (baseline clássico) e ao BERT (fine-tuning supervisionado tradicional): o interesse específico é testar se uma técnica desenhada para **poucos exemplos por classe** consegue superar o BERT no cenário mais difícil do projeto (Nível 2), especialmente relevante porque, mesmo após a expansão para 852 tickets, o dataset ainda é pequeno para os padrões de deep learning tradicional.

## Configuração

- Modelo base: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (sentence-transformer multilíngue, leve).
- Entrada: `descricao` (texto bruto) — mesmo raciocínio do BERT: o modelo já é pré-treinado para entender linguagem natural, não se beneficia de normalização agressiva.
- Sem mecanismo explícito de balanceamento de classes (diferente do SVM e do BERT) — a abordagem contrastiva do próprio SetFit já lida melhor com classes minoritárias por construção, gerando pares de treino balanceados internamente.
- Avaliado com a mesma metodologia dos outros modelos: CV 5-fold estratificado, OOF, F1 macro.

## Resultado (dataset de 852 tickets)

*A preencher quando o treino no Colab terminar.*

## Referência histórica (dataset de 185 tickets, pré-expansão — não citar no TCC)

- F1 macro: 0,616 (± 0,094) — abaixo do SVM (0,651) e do BERT (0,528, também da época) da mesma rodada.
- Pior classe: `BD`, com apenas 13 exemplos no dataset da época (F1 0,52) — o mesmo gargalo de dados que afetava o BERT nesse período.

Esses números antigos por si só já sugerem uma hipótese a testar na rodada atual: como o SetFit é desenhado para poucos exemplos, é possível que ele tivesse se saído relativamente melhor que o BERT com dataset pequeno (delta menor de queda) mas seja superado pelo BERT agora que o dataset cresceu e deixou de ser o regime few-shot para o qual o SetFit foi otimizado. Vale comentar essa hipótese no TCC e confirmar (ou refutar) com o número real.
