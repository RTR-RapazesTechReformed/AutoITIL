# Nível 2 (área responsável) SVM e BERT

Classifica o texto do ticket na área técnica responsável: `Aplicações`, `Rede`, `Segurança`, `Servidor` ou `BD`. Ver [00_metodologia_experimental.md](00_metodologia_experimental.md) para a metodologia de avaliação. Este é o nível **mais difícil** do projeto: 5 classes (vs. 4 no Nível 1) e vocabulário mais próximo entre algumas áreas (ex.: um problema de performance pode ser descrito de forma parecida seja em Servidor, BD ou Aplicações).

## SVM (TF-IDF + LinearSVC)

Mesma arquitetura de pipeline do Nível 1 (`TfidfVectorizer` + `CalibratedClassifierCV(LinearSVC(class_weight="balanced"))`), treinada separadamente com os rótulos de `area_responsavel`.

**Resultado real (CV 5-fold, 852 tickets):**

- **F1 macro: 0,7431** (± 0,0286)
- Accuracy (OOF): 0,7441

| Classe | Precision | Recall | F1 | Suporte |
|---|---|---|---|---|
| Aplicações | 0,695 | 0,712 | 0,703 | 170 |
| BD | 0,879 | 0,884 | 0,881 | 172 |
| Rede | 0,721 | 0,759 | 0,739 | 170 |
| Segurança | 0,712 | 0,641 | 0,675 | 170 |
| Servidor | 0,711 | 0,724 | 0,717 | 170 |

## BERT (BERTimbau fine-tuned)

Mesma arquitetura do Nível 1 (`WeightedLossTrainer`, `max_length=192`), com 6 épocas na validação cruzada (mais épocas que o Nível 1, problema mais difícil, com 5 classes e fronteiras semânticas mais próximas, precisa de mais passadas para convergir).

**Resultado real (CV 5-fold, 852 tickets):**

- **F1 macro: 0,8048** (± 0,0358)
- Accuracy (OOF): 0,8052

| Classe | Precision | Recall | F1 | Suporte |
|---|---|---|---|---|
| Aplicações | 0,782 | 0,759 | 0,770 | 170 |
| BD | 0,905 | 0,890 | 0,897 | 172 |
| Rede | 0,768 | 0,818 | 0,792 | 170 |
| Segurança | 0,824 | 0,718 | 0,767 | 170 |
| Servidor | 0,757 | 0,841 | 0,797 | 170 |

## Discussão

Aqui a diferença entre BERT e SVM é bem mais relevante que no Nível 1: **delta de F1 macro de +0,0617** a favor do BERT, o dobro do ganho observado no Nível 1. Isso reforça a leitura de que, quanto mais difícil o problema (mais classes, vocabulário mais sobreposto entre categorias), maior o valor agregado de um modelo Transformer sobre um baseline TF-IDF.

`BD` é consistentemente a classe mais fácil para os dois modelos (F1 ~0,88–0,90), provavelmente porque tickets de banco de dados usam jargão técnico bem específico (nomes de SGBD, códigos de erro do Oracle/PostgreSQL/MySQL, etc.) que não aparece em outras áreas. `Segurança` é a classe onde o BERT tem a maior queda de recall (0,718), indício de que parte dos tickets de segurança se confunde com outras áreas (ex.: um problema de VPN pode soar como Rede ou Segurança, um problema de acesso pode soar como Aplicações ou Segurança), um ponto interessante para discutir na análise de erros do TCC.

Antes da expansão do dataset (185 → 852 tickets), o BERT tinha F1 macro de apenas 0,52 no Nível 2, abaixo até do baseline SVM da época (0,65), porque a classe `BD` tinha só 13 exemplos, insuficiente para o fine-tuning generalizar. A expansão balanceada do dataset (BD passou para 172 exemplos) foi o que destravou o ganho do BERT sobre o SVM neste nível.

**Modelo BERT publicado em**: [`EdsonMorro/autoitil-bert-nivel2`](https://huggingface.co/EdsonMorro/autoitil-bert-nivel2).
