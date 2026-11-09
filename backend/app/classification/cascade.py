"""
cascade.py — pipeline em cascata Nível 1 → Nível 2.

Responsabilidade: orquestrar os dois BertClassifier (N1 e N2) e
fornecer fallback para o Classifier SVM quando os modelos BERT não
estão disponíveis em disco.

Contrato de saída do classify(text):
{
    "nivel1": "Incidente",
    "nivel2": "Rede",
    "confianca_n1": 0.92,
    "confianca_n2": 0.88,
    "modelo_n1": "bert",
    "modelo_n2": "bert",
}

Quando algum nível não pode ser classificado (ex: BERT N2 ausente e
fallback ativo), os campos correspondentes retornam None.
"""

from __future__ import annotations

import time


class CascadeClassifier:
    """
    Orquestra BertClassifier(N1) + BertClassifier(N2) com fallback SVM.

    Política de seleção:
    - Se BERT N1 disponível: usa BERT N1.
    - Senão, se SVM disponível: usa SVM para N1 (nivel2 = None).
    - Se nenhum disponível: classify() retorna None.

    Para o Nível 2:
    - Se BERT N2 disponível: usa BERT N2.
    - Senão: nivel2 = None, confianca_n2 = None.
    """

    def __init__(self, bert_n1, bert_n2, svm_fallback) -> None:
        self.bert_n1 = bert_n1
        self.bert_n2 = bert_n2
        self.svm_fallback = svm_fallback
        # Telemetria da última classificação, uma entrada por nível
        # efetivamente executado. A rota lê e persiste em
        # metrica_classificacao; o classificador não conhece banco.
        self.last_call_metrics: list[dict] = []

    def is_available(self) -> bool:
        return self.bert_n1.is_trained() or self.svm_fallback.is_trained()

    def classify(self, text: str) -> dict | None:
        """
        Classifica um texto em Nível 1 (tipo ITIL) e Nível 2 (área responsável).

        Retorna dict plano com nivel1, nivel2, confianca_n1, confianca_n2,
        modelo_n1 e modelo_n2 (arquitetura usada em cada nível).
        Campos não disponíveis vêm como None.

        Returns:
            dict ou None quando nenhum classificador está disponível.
        """
        if not self.is_available():
            return None

        self.last_call_metrics = []

        n1 = self.bert_n1.predict(text) if self.bert_n1.is_trained() else None
        if n1 is not None:
            modelo_n1 = "bert"
            self._coletar(self.bert_n1, nivel=1, arquitetura="bert")
        else:
            # O SVM não é instrumentado internamente (é scikit-learn, sem
            # tokenizer): cronometramos aqui e reportamos tokens_entrada=0,
            # que o CHECK da tabela aceita e o gráfico distingue pela
            # arquitetura.
            start = time.perf_counter()
            n1 = self.svm_fallback.predict(text) if self.svm_fallback.is_trained() else None
            if n1 is None:
                return None
            modelo_n1 = "svm"
            self.last_call_metrics.append(
                {
                    "nivel": 1,
                    "arquitetura": "svm",
                    "duracao_ms": (time.perf_counter() - start) * 1000,
                    "tokens_entrada": 0,
                    "itens": 1,
                }
            )

        nivel1 = n1["categoria"]
        confianca_n1 = n1["confianca"]

        n2 = self.bert_n2.predict(text) if self.bert_n2.is_trained() else None
        if n2 is not None:
            nivel2 = n2["categoria"]
            confianca_n2 = n2["confianca"]
            modelo_n2 = "bert"
            self._coletar(self.bert_n2, nivel=2, arquitetura="bert")
        else:
            nivel2 = None
            confianca_n2 = None
            modelo_n2 = None

        return {
            "nivel1": nivel1,
            "nivel2": nivel2,
            "confianca_n1": confianca_n1,
            "confianca_n2": confianca_n2,
            "modelo_n1": modelo_n1,
            "modelo_n2": modelo_n2,
        }

    def _coletar(self, classificador, *, nivel: int, arquitetura: str) -> None:
        """Copia a telemetria da última chamada do BertClassifier para o
        buffer. Silencioso quando os atributos não existem ou estão vazios
        (dublês de teste, ou modelo que não chegou a rodar) — telemetria
        nunca deve derrubar uma classificação."""
        duracao = getattr(classificador, "last_call_duracao_ms", None)
        if duracao is None:
            return
        self.last_call_metrics.append(
            {
                "nivel": nivel,
                "arquitetura": arquitetura,
                "duracao_ms": duracao,
                "tokens_entrada": getattr(
                    classificador, "last_call_tokens_entrada", 0
                )
                or 0,
                "itens": getattr(classificador, "last_call_itens", 1) or 1,
            }
        )
