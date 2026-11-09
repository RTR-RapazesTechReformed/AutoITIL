# Comparação geral dos modelos

## Tabela consolidada (F1 macro, CV 5-fold, dataset de 852 tickets)

| Nível | Modelo | F1 macro | Desvio padrão | Accuracy (OOF) |
|---|---|---|---|---|
| 1 (categoria ITIL) | SVM (TF-IDF+LinearSVC) | 0,9112 | 0,0274 | 0,9096 |
| 1 (categoria ITIL) | BERT (BERTimbau) | **0,9594** | 0,0188 | 0,9589 |
| 2 (área responsável) | SVM (TF-IDF+LinearSVC) | 0,7431 | 0,0286 | 0,7441 |
| 2 (área responsável) | BERT (BERTimbau) | **0,8048** | 0,0358 | 0,8052 |
| 2 (área responsável) | SetFit | *pendente* | — | — |

## Parágrafo pronto — para a seção de Metodologia (stack de NLP)

Sugestão de texto para a parte que fala da stack (adaptar como preferir):

> Para a etapa de classificação semântica, foram comparadas três abordagens de crescente complexidade. Como *baseline*, utilizou-se um modelo TF-IDF + Support Vector Machine (SVM linear), técnica clássica de classificação de texto, leve computacionalmente e que tende a performar bem em conjuntos de dados de menor escala. Em seguida, aplicou-se o BERTimbau (neuralmind/bert-base-portuguese-cased), um modelo da arquitetura Transformer pré-treinado especificamente para a língua portuguesa, submetido a um processo de *fine-tuning* supervisionado para as duas tarefas de classificação (categoria ITIL e área responsável). Por fim, explorou-se o SetFit, uma técnica de *fine-tuning* contrastivo voltada para cenários de *few-shot learning*, isto é, com poucos exemplos rotulados por classe — cenário relevante neste projeto dado o tamanho ainda limitado do conjunto de dados frente aos padrões usuais de *deep learning*. Os três modelos foram avaliados sob o mesmo protocolo — validação cruzada estratificada com 5 partições e métrica de F1-macro, que pondera igualmente todas as classes independentemente de seu tamanho — permitindo uma comparação direta e estatisticamente mais robusta do que a obtida por um único particionamento treino/teste.

## Principais achados (para a seção de Resultados/Discussão)

1. **O ganho do BERT sobre o SVM cresce com a dificuldade do problema.** No Nível 1 (4 classes, vocabulário bem distintivo), o delta de F1 macro é de +0,048. No Nível 2 (5 classes, vocabulário mais sobreposto entre áreas), o delta sobe para +0,062 — o dobro. Isso sugere que a escolha do modelo deveria, idealmente, ser sensível à dificuldade da tarefa: um baseline simples já resolve bem problemas "fáceis", mas o investimento em um Transformer se paga mais em problemas mais ambíguos.
2. **O tamanho e balanceamento do dataset foi o fator decisivo, mais até que a escolha do modelo.** Antes de expandir o dataset de 185 para 852 tickets (com foco em balancear a classe `BD`, que tinha só 13 exemplos), o BERT no Nível 2 tinha F1 macro de apenas 0,52 — pior que o próprio SVM baseline da época (0,65). Depois da expansão, o BERT saltou para 0,80, superando o SVM (que também melhorou, para 0,74). O aprendizado para o TCC: mais dados bem balanceados valem mais que trocar de algoritmo quando o gargalo é a quantidade de exemplos por classe minoritária.
3. **BD é a classe mais fácil em ambos os níveis 2 (SVM e BERT)**, provavelmente pelo vocabulário técnico bem específico (nomes de SGBD, códigos de erro). `Segurança` é a que mais perde recall no BERT — indício de sobreposição semântica com tickets de Rede e Aplicações, ponto interessante para uma seção de análise de erros.
4. *(a completar)* Comparação de tempo de execução/inferência e consumo de memória entre os três modelos — ainda não medida.

## Pendências para fechar esta comparação

- [ ] Resultado real do SetFit Nível 2 (dataset de 852) — atualizar tabela e discussão acima.
- [ ] Benchmark de tempo de inferência (ms/ticket) e consumo de memória (RAM/VRAM) para os três modelos — SVM deve ser ordens de grandeza mais rápido e leve; quantificar exatamente.
- [ ] `metrics_report.json` gerado por `scripts/avaliar_modelos.py` com os modelos BERT reais publicados no Hugging Face Hub.
