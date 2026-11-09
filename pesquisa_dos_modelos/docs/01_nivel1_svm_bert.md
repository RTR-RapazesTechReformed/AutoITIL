# Nível 1 (categoria ITIL) SVM e BERT

Classifica o texto do ticket em `Incidente`, `Requisição`, `Problema` ou `Mudança`. Ver [00_metodologia_experimental.md](00_metodologia_experimental.md) para a metodologia de avaliação (CV 5-fold, F1 macro).

## SVM (TF-IDF + LinearSVC) baseline

**Decisão de design**: pipeline `TfidfVectorizer` (`ngram_range=(1,2)`, `min_df=2`, `max_df=0.95`, `sublinear_tf=True`) → `CalibratedClassifierCV(LinearSVC(max_iter=2000, class_weight="balanced"), cv=3)`. A calibração via `CalibratedClassifierCV` existe para o `LinearSVC`, que naturalmente só produz *decision scores*, não probabilidades, poder expor uma confiança utilizável pela aplicação (`predict_proba`), necessária para o campo `confianca_n1` do pipeline em cascata.

Usa `descricao_limpa` (texto normalizado) como entrada, porque TF-IDF é sensível a variações superficiais (maiúsculas, pontuação, stopwords) que não carregam sinal discriminativo para esse método.

**Resultado real (CV 5-fold, 852 tickets):**

- **F1 macro: 0,9112** (± 0,0274)
- Accuracy (OOF): 0,9096

| Classe | Precision | Recall | F1 | Suporte |
|---|---|---|---|---|
| Incidente | 0,898 | 0,865 | 0,881 | 244 |
| Mudança | 0,934 | 0,939 | 0,936 | 196 |
| Problema | 0,928 | 0,919 | 0,923 | 197 |
| Requisição | 0,884 | 0,926 | 0,905 | 215 |

## BERT (BERTimbau fine-tuned)

**Decisão de design**: `neuralmind/bert-base-portuguese-cased` fine-tuned via `Trainer` do HuggingFace, com uma classe `WeightedLossTrainer` (subclasse que sobrescreve `compute_loss` para aplicar pesos de classe balanceados, `compute_class_weight(class_weight="balanced")`). `max_length=192` tokens, 4 épocas na validação cruzada.

Usa `descricao` (texto bruto), diferente do SVM: modelos Transformer pré-treinados capturam sinal semântico da pontuação, acentuação e estrutura da frase natural, normalizar demais descartaria informação que o BERTimbau sabe aproveitar.

**Resultado real (CV 5-fold, 852 tickets):**

- **F1 macro: 0,9594** (± 0,0188)
- Accuracy (OOF): 0,9589

| Classe | Precision | Recall | F1 | Suporte |
|---|---|---|---|---|
| Incidente | 0,967 | 0,947 | 0,957 | 244 |
| Mudança | 0,974 | 0,949 | 0,961 | 196 |
| Problema | 0,960 | 0,985 | 0,972 | 197 |
| Requisição | 0,936 | 0,958 | 0,947 | 215 |

## Discussão

No Nível 1, o BERT supera o SVM em todas as classes (delta de F1 macro de **+0,0482**), mas a diferença é pequena frente ao custo (GPU, tempo de treino, ~420MB de peso do modelo vs. ~110KB do `.pkl` do SVM). Isso é coerente com a literatura: problemas de classificação de texto com poucas classes bem distinguíveis lexicalmente (aqui, os quatro tipos ITIL têm vocabulário bem característico, "solicito"/"preciso de acesso" para Requisição, "RFC"/"janela de manutenção" para Mudança, etc.) já são bem resolvidos por TF-IDF+SVM. O ganho do BERT existe, mas é marginal, o SVM já seria uma escolha defensável em produção para este nível específico, dado seu custo operacional muito menor.

**Modelo BERT publicado em**: [`EdsonMorro/autoitil-bert-nivel1`](https://huggingface.co/EdsonMorro/autoitil-bert-nivel1).
