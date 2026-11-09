"""Testes de app.domain.classification_metrics e da agregação por requisição."""

from __future__ import annotations

from app.api.routes import _acumular_metricas_classificacao


def test_acumula_por_nivel_e_arquitetura():
    """Duas linhas classificadas viram um acumulado por (nível, arquitetura)."""
    acc: dict = {}
    linha = [
        {"nivel": 1, "arquitetura": "bert", "duracao_ms": 10.0, "tokens_entrada": 30, "itens": 1},
        {"nivel": 2, "arquitetura": "bert", "duracao_ms": 12.0, "tokens_entrada": 30, "itens": 1},
    ]
    _acumular_metricas_classificacao(acc, linha)
    _acumular_metricas_classificacao(acc, linha)

    assert set(acc) == {(1, "bert"), (2, "bert")}
    assert acc[(1, "bert")] == {"duracao_ms": 20.0, "tokens_entrada": 60, "itens": 2}
    assert acc[(2, "bert")] == {"duracao_ms": 24.0, "tokens_entrada": 60, "itens": 2}


def test_separa_arquiteturas_no_mesmo_nivel():
    """Fallback pro SVM no meio de um upload não deve somar com o BERT."""
    acc: dict = {}
    _acumular_metricas_classificacao(
        acc, [{"nivel": 1, "arquitetura": "bert", "duracao_ms": 10.0, "tokens_entrada": 30, "itens": 1}]
    )
    _acumular_metricas_classificacao(
        acc, [{"nivel": 1, "arquitetura": "svm", "duracao_ms": 2.0, "tokens_entrada": 0, "itens": 1}]
    )

    assert acc[(1, "bert")]["itens"] == 1
    assert acc[(1, "svm")]["itens"] == 1
    assert acc[(1, "svm")]["tokens_entrada"] == 0


def test_lista_vazia_nao_cria_entradas():
    """Classificador indisponível não deve gerar linha de métrica."""
    acc: dict = {}
    _acumular_metricas_classificacao(acc, [])
    assert acc == {}


def test_cascade_coleta_telemetria_dos_dois_niveis():
    """CascadeClassifier.last_call_metrics reflete os níveis executados."""
    from app.classification.cascade import CascadeClassifier

    class FakeBert:
        def __init__(self, label):
            self.label = label
            self.last_call_duracao_ms = 5.0
            self.last_call_tokens_entrada = 42
            self.last_call_itens = 1

        def is_trained(self):
            return True

        def predict(self, _text):
            return {"categoria": self.label, "confianca": 0.9}

    class FakeSvm:
        def is_trained(self):
            return False

        def predict(self, _text):
            return None

    cascade = CascadeClassifier(FakeBert("Incidente"), FakeBert("Rede"), FakeSvm())
    resultado = cascade.classify("vpn caiu")

    assert resultado["modelo_n1"] == "bert"
    assert len(cascade.last_call_metrics) == 2
    assert [m["nivel"] for m in cascade.last_call_metrics] == [1, 2]
    assert all(m["tokens_entrada"] == 42 for m in cascade.last_call_metrics)


def test_cascade_sem_telemetria_nao_quebra():
    """Dublê sem os atributos last_call_* não deve derrubar a classificação."""
    from app.classification.cascade import CascadeClassifier

    class BertSemTelemetria:
        def is_trained(self):
            return True

        def predict(self, _text):
            return {"categoria": "Incidente", "confianca": 0.8}

    class FakeSvm:
        def is_trained(self):
            return False

        def predict(self, _text):
            return None

    cascade = CascadeClassifier(BertSemTelemetria(), BertSemTelemetria(), FakeSvm())
    resultado = cascade.classify("texto")

    assert resultado["nivel1"] == "Incidente"
    assert cascade.last_call_metrics == []
