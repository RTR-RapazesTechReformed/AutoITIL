"""Testes do CascadeClassifier."""

from unittest.mock import MagicMock

from app.classification.cascade import CascadeClassifier


def _make_bert(is_trained=True, predict_return=None):
    bert = MagicMock()
    bert.is_trained.return_value = is_trained
    bert.predict.return_value = predict_return
    return bert


def _make_svm(is_trained=True, predict_return=None):
    svm = MagicMock()
    svm.is_trained.return_value = is_trained
    svm.predict.return_value = predict_return
    return svm


class TestIsAvailable:
    def test_true_when_both_bert_models_present(self):
        cascade = CascadeClassifier(
            bert_n1=_make_bert(is_trained=True),
            bert_n2=_make_bert(is_trained=True),
            svm_fallback=_make_svm(is_trained=False),
        )
        assert cascade.is_available() is True

    def test_true_when_only_svm_fallback_present(self):
        cascade = CascadeClassifier(
            bert_n1=_make_bert(is_trained=False),
            bert_n2=_make_bert(is_trained=False),
            svm_fallback=_make_svm(is_trained=True),
        )
        assert cascade.is_available() is True

    def test_false_when_nothing_available(self):
        cascade = CascadeClassifier(
            bert_n1=_make_bert(is_trained=False),
            bert_n2=_make_bert(is_trained=False),
            svm_fallback=_make_svm(is_trained=False),
        )
        assert cascade.is_available() is False


class TestClassifyHappyPath:
    def test_returns_both_levels_when_both_bert_models_available(self):
        bert_n1 = _make_bert(
            is_trained=True,
            predict_return={"categoria": "Incidente", "confianca": 0.92},
        )
        bert_n2 = _make_bert(
            is_trained=True,
            predict_return={"categoria": "Rede", "confianca": 0.88},
        )
        cascade = CascadeClassifier(
            bert_n1=bert_n1,
            bert_n2=bert_n2,
            svm_fallback=_make_svm(is_trained=False),
        )

        result = cascade.classify("vpn caiu")

        assert result == {
            "nivel1": "Incidente",
            "nivel2": "Rede",
            "confianca_n1": 0.92,
            "confianca_n2": 0.88,
            "modelo_n1": "bert",
            "modelo_n2": "bert",
        }
        bert_n1.predict.assert_called_once_with("vpn caiu")
        bert_n2.predict.assert_called_once_with("vpn caiu")


class TestClassifyFallback:
    def test_falls_back_to_svm_when_bert_n1_missing(self):
        cascade = CascadeClassifier(
            bert_n1=_make_bert(is_trained=False),
            bert_n2=_make_bert(is_trained=False),
            svm_fallback=_make_svm(
                is_trained=True,
                predict_return={"categoria": "Incidente", "confianca": 0.70},
            ),
        )

        result = cascade.classify("vpn caiu")

        assert result == {
            "nivel1": "Incidente",
            "nivel2": None,
            "confianca_n1": 0.70,
            "confianca_n2": None,
            "modelo_n1": "svm",
            "modelo_n2": None,
        }

    def test_returns_n2_none_when_only_bert_n2_missing(self):
        cascade = CascadeClassifier(
            bert_n1=_make_bert(
                is_trained=True,
                predict_return={"categoria": "Incidente", "confianca": 0.92},
            ),
            bert_n2=_make_bert(is_trained=False),
            svm_fallback=_make_svm(is_trained=False),
        )

        result = cascade.classify("vpn caiu")

        assert result["nivel1"] == "Incidente"
        assert result["nivel2"] is None
        assert result["confianca_n2"] is None

    def test_returns_none_when_nothing_available(self):
        cascade = CascadeClassifier(
            bert_n1=_make_bert(is_trained=False),
            bert_n2=_make_bert(is_trained=False),
            svm_fallback=_make_svm(is_trained=False),
        )
        assert cascade.classify("qualquer texto") is None


class TestClassifyBertUnreachable:
    def test_falls_back_to_svm_when_bert_n1_predict_returns_none(self):
        bert_n1 = _make_bert(is_trained=True, predict_return=None)
        svm = _make_svm(
            is_trained=True,
            predict_return={"categoria": "Incidente", "confianca": 0.70},
        )
        cascade = CascadeClassifier(
            bert_n1=bert_n1,
            bert_n2=_make_bert(is_trained=True, predict_return=None),
            svm_fallback=svm,
        )

        result = cascade.classify("vpn caiu")

        assert result == {
            "nivel1": "Incidente",
            "nivel2": None,
            "confianca_n1": 0.70,
            "confianca_n2": None,
            "modelo_n1": "svm",
            "modelo_n2": None,
        }
        svm.predict.assert_called_once_with("vpn caiu")

    def test_returns_n2_none_when_bert_n2_predict_returns_none(self):
        cascade = CascadeClassifier(
            bert_n1=_make_bert(
                is_trained=True,
                predict_return={"categoria": "Incidente", "confianca": 0.92},
            ),
            bert_n2=_make_bert(is_trained=True, predict_return=None),
            svm_fallback=_make_svm(is_trained=False),
        )

        result = cascade.classify("vpn caiu")

        assert result["nivel1"] == "Incidente"
        assert result["modelo_n1"] == "bert"
        assert result["nivel2"] is None
        assert result["confianca_n2"] is None
        assert result["modelo_n2"] is None

    def test_returns_none_when_bert_unreachable_and_svm_absent(self):
        cascade = CascadeClassifier(
            bert_n1=_make_bert(is_trained=True, predict_return=None),
            bert_n2=_make_bert(is_trained=True, predict_return=None),
            svm_fallback=_make_svm(is_trained=False),
        )
        assert cascade.classify("vpn caiu") is None
