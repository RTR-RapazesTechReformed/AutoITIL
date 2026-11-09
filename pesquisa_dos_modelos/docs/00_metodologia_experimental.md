# Metodologia experimental de classificação (NLP)

Este documento registra as decisões técnicas por trás dos modelos de classificação do AutoITIL, com os números reais de desempenho. É a base para a seção de Metodologia/Resultados do TCC, os textos abaixo podem ser adaptados diretamente.

## 1. Dataset

- **852 tickets** sintéticos de TI em português, rotulados em dois níveis:
  - **Nível 1** (categoria ITIL): `Incidente`, `Requisição`, `Problema`, `Mudança`.
  - **Nível 2** (área responsável): `Aplicações`, `Rede`, `Segurança`, `Servidor`, `BD`.
- Distribuição balanceada entre as 5 áreas de Nível 2 (~170 tickets cada), e razoavelmente balanceada entre as 4 categorias de Nível 1 (196–244 cada).
- O dataset cresceu de um núcleo inicial de 185 tickets (85 reais/anonimizados + 100 sintéticos de rodadas anteriores) para 852, via geração sintética adicional voltada a corrigir o desbalanceamento, a classe `BD`, por exemplo, tinha originalmente só 13 exemplos e era a pior classe do Nível 2 (F1 0,52), hoje tem 172 exemplos e é a melhor classe (F1 0,88–0,90).
- Colunas: `id`, `descricao` (texto bruto), `descricao_limpa` (normalizado, minúsculas, sem acentos/pontuação, stopwords removidas, termos técnicos como VPN/SLA/CI-CD preservados), `categoria` (Nível 1), `area_responsavel` (Nível 2).

## 2. Por que dois modelos (SVM baseline + BERT) e um terceiro (SetFit)

A decisão de comparar múltiplos modelos, em vez de escolher um só a priori, foi deliberada:

- **TF-IDF + SVM linear** é o **baseline**: uma técnica clássica, leve, rápida de treinar (segundos) e que historicamente performa bem em datasets pequenos/médios de classificação de texto. Serve de "chão", qualquer modelo mais sofisticado precisa justificar seu custo superando esse baseline.
- **BERTimbau** (`neuralmind/bert-base-portuguese-cased`) é um modelo **Transformer** pré-treinado em português, fine-tuned para as duas tarefas de classificação. Representa o estado da arte em compreensão de linguagem natural, à custa de mais tempo de treino e necessidade de GPU.
- **SetFit** foi adicionado depois, como uma terceira via experimental focada em **few-shot learning**: fine-tuning contrastivo de um sentence-transformer + uma cabeça de classificação leve (logistic regression), pensado para cenários com poucos dados rotulados por classe, relevante porque o dataset, mesmo após a expansão, ainda é pequeno para os padrões de deep learning.

Essa comparação a três permite discutir no TCC não só "qual modelo classifica melhor", mas **sob que condições cada abordagem se paga**, um argumento mais forte para a banca do que apresentar um único modelo.

## 3. Metodologia de avaliação

- **Validação cruzada estratificada com 5 folds** (`StratifiedKFold`, `k=5`, `shuffle=True`, `random_state=42`) com predições fora da amostra (**out-of-fold = OOF**), em vez de um único split 80/20.
  - Motivo: com classes minoritárias (a pior tinha 13 exemplos antes da expansão do dataset), um único split de teste é instável, o resultado varia bastante dependendo de quais poucos exemplos caem no conjunto de teste. CV com 5 folds usa 100% dos dados tanto para treino quanto para avaliação (em folds diferentes), dando uma estimativa muito mais confiável do desempenho real.
- **F1 macro** como métrica principal (em vez de accuracy ou F1 weighted): trata todas as classes com peso igual, independente do tamanho, essencial num problema onde nem todas as categorias têm a mesma quantidade de exemplos nem a mesma importância operacional.
- **Balanceamento de classes**: cada modelo trata o desbalanceamento à sua maneira:
  - SVM: `class_weight="balanced"` no `LinearSVC`.
  - BERT: função de perda com pesos por classe (`WeightedLossTrainer`, subclasse do `Trainer` do HuggingFace que sobrescreve `compute_loss`), pesos calculados via `compute_class_weight(class_weight="balanced")`.
  - SetFit: a própria natureza contrastiva/few-shot do método já lida melhor com poucos exemplos por classe, dispensando um mecanismo de peso explícito.
- **Texto de entrada por modelo**: o SVM usa `descricao_limpa` (texto normalizado, TF-IDF se beneficia de tokens limpos e consistentes) BERT e SetFit usam `descricao` (texto bruto, já que ambos são pré-treinados para entender linguagem natural com pontuação e acentuação, e normalizar demais joga fora sinal que o modelo saberia aproveitar).
- **Nota de reprodutibilidade**: treinos em GPU não são 100% determinísticos mesmo com seed fixa (comportamento do cuDNN), então re-executar os notebooks pode produzir números ligeiramente diferentes dos aqui documentados, dentro da margem do desvio-padrão entre folds.

## 4. Onde estão os artefatos

- Notebooks de treino: `notebooks/svm_nivel1_training.ipynb`, `notebooks/svm_nivel2_training.ipynb`, `notebooks/bert_nivel1_training.ipynb`, `notebooks/bert_nivel2_training.ipynb`, `notebooks/setfit_nivel2_training.ipynb`.
- Notebook de comparação (mini-paper): `notebooks/comparacao_svm_bert.ipynb`.
- Resultados de CV em JSON (números exatos, por fold): `notebooks/*_cv_results.json`.
- Modelos SVM finais: `models/baseline/svm.pkl` (Nível 1), `models/baseline/svm_nivel2.pkl` (Nível 2).
- Modelos BERT finais: hospedados no Hugging Face Hub [`EdsonMorro/autoitil-bert-nivel1`](https://huggingface.co/EdsonMorro/autoitil-bert-nivel1) e [`EdsonMorro/autoitil-bert-nivel2`](https://huggingface.co/EdsonMorro/autoitil-bert-nivel2) (pesos fine-tuned de ~420MB cada, pesados demais para o Git o `BertClassifier` da aplicação baixa automaticamente do Hub quando não encontra o modelo localmente).

## 5. Pendências conhecidas (para a próxima rodada de documentação)

- **SetFit Nível 2**: em execução no momento da escrita deste documento, resultados a atualizar em `05_setfit_nivel2.md` assim que o treino no Colab terminar.
- **Tempo de execução/inferência e consumo de memória**: ainda não medidos formalmente para nenhum modelo, só temos F1/precision/recall por enquanto. Precisa virar uma seção própria (`06_comparacao_recursos.md`, a criar) comparando latência de inferência e footprint de memória entre SVM, BERT e SetFit, relevante porque é um dos eixos de comparação que o time de redação já sinalizou que quer incluir.
- **SetFit Nível 1**: não foi testado (nem estava no escopo), o Nível 1 já tem desempenho muito alto com SVM/BERT (F1 > 0,91), então não havia motivo para investir tempo de GPU nele. Pode ser adicionado por completude se sobrar tempo.
