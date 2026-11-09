"""Testes do BertClassifier."""

from unittest.mock import patch

import pytest
import torch

from app.classification.bert_classifier import BertClassifier


class TestIsTrained:
    def test_returns_false_when_model_dir_missing(self, tmp_path):
        clf = BertClassifier(model_dir=tmp_path / "nao_existe")
        assert clf.is_trained() is False

    def test_returns_true_when_model_dir_has_config(self, tmp_path):
        model_dir = tmp_path / "modelo"
        model_dir.mkdir()
        (model_dir / "config.json").write_text("{}")
        clf = BertClassifier(model_dir=model_dir)
        assert clf.is_trained() is True


class TestPredict:
    def test_returns_none_when_model_not_trained(self, tmp_path):
        clf = BertClassifier(model_dir=tmp_path / "nao_existe")
        assert clf.predict("texto qualquer") is None

    def test_returns_label_and_confidence(self, tmp_path):
        model_dir = tmp_path / "modelo"
        model_dir.mkdir()
        (model_dir / "config.json").write_text("{}")

        fake_logits = torch.tensor([[2.0, 0.5, 0.3, 0.2]])
        fake_labels = {0: "Incidente", 1: "Requisição", 2: "Problema", 3: "Mudança"}

        with (
            patch("app.classification.bert_classifier.AutoTokenizer") as mock_tok,
            patch(
                "app.classification.bert_classifier.AutoModelForSequenceClassification"
            ) as mock_model,
        ):
            mock_tok.from_pretrained.return_value = lambda text, **kw: {
                "input_ids": torch.tensor([[1, 2, 3]]),
                "attention_mask": torch.tensor([[1, 1, 1]]),
            }
            fake_model = mock_model.from_pretrained.return_value
            fake_model.config.id2label = fake_labels
            fake_model.eval.return_value = fake_model
            fake_model.return_value.logits = fake_logits

            clf = BertClassifier(model_dir=model_dir)
            result = clf.predict("vpn caiu")

            assert result["categoria"] == "Incidente"
            assert 0.0 < result["confianca"] < 1.0
            assert result["confianca"] == pytest.approx(
                torch.softmax(fake_logits, dim=-1)[0][0].item(), rel=1e-4
            )

            # Lazy-load idempotency: segunda chamada não recarrega o modelo.
            clf.predict("outro texto")
            assert mock_tok.from_pretrained.call_count == 1
            assert mock_model.from_pretrained.call_count == 1
            fake_model.eval.assert_called_once()


class TestPredictBatch:
    def test_returns_none_when_model_not_trained(self, tmp_path):
        clf = BertClassifier(model_dir=tmp_path / "nao_existe")
        assert clf.predict_batch(["a", "b"]) is None

    def test_returns_list_with_same_length_as_input(self, tmp_path):
        model_dir = tmp_path / "modelo"
        model_dir.mkdir()
        (model_dir / "config.json").write_text("{}")

        fake_logits = torch.tensor([[2.0, 0.5], [0.3, 2.5]])
        fake_labels = {0: "Incidente", 1: "Requisição"}

        with (
            patch("app.classification.bert_classifier.AutoTokenizer") as mock_tok,
            patch(
                "app.classification.bert_classifier.AutoModelForSequenceClassification"
            ) as mock_model,
        ):
            mock_tok.from_pretrained.return_value = lambda text, **kw: {
                "input_ids": torch.tensor([[1, 2], [3, 4]]),
                "attention_mask": torch.tensor([[1, 1], [1, 1]]),
            }
            fake_model = mock_model.from_pretrained.return_value
            fake_model.config.id2label = fake_labels
            fake_model.eval.return_value = fake_model
            fake_model.return_value.logits = fake_logits

            clf = BertClassifier(model_dir=model_dir)
            results = clf.predict_batch(["vpn caiu", "solicito acesso"])

            assert len(results) == 2
            assert results[0]["categoria"] == "Incidente"
            assert results[1]["categoria"] == "Requisição"


class TestHubDownloadFailure:
    def test_predict_returns_none_when_snapshot_download_fails(self, tmp_path):
        with patch(
            "app.classification.bert_classifier.snapshot_download",
            side_effect=OSError("401 Client Error: Unauthorized"),
        ) as mock_dl:
            clf = BertClassifier(
                model_dir=tmp_path / "nao_existe", hub_repo_id="acme/modelo-privado"
            )
            assert clf.is_trained() is True

            assert clf.predict("vpn caiu") is None
            mock_dl.assert_called_once()

    def test_is_trained_flips_to_false_after_failed_download(self, tmp_path):
        with patch(
            "app.classification.bert_classifier.snapshot_download",
            side_effect=OSError("sem rede"),
        ):
            clf = BertClassifier(
                model_dir=tmp_path / "nao_existe", hub_repo_id="acme/modelo-privado"
            )
            clf.predict("vpn caiu")

            assert clf.is_trained() is False

    def test_does_not_retry_download_after_failure(self, tmp_path):
        with patch(
            "app.classification.bert_classifier.snapshot_download",
            side_effect=OSError("sem rede"),
        ) as mock_dl:
            clf = BertClassifier(
                model_dir=tmp_path / "nao_existe", hub_repo_id="acme/modelo-privado"
            )
            clf.predict("primeira")
            clf.predict("segunda")
            clf.predict("terceira")

            mock_dl.assert_called_once()

    def test_predict_batch_returns_none_when_download_fails(self, tmp_path):
        with patch(
            "app.classification.bert_classifier.snapshot_download",
            side_effect=OSError("401 Client Error: Unauthorized"),
        ):
            clf = BertClassifier(
                model_dir=tmp_path / "nao_existe", hub_repo_id="acme/modelo-privado"
            )
            assert clf.predict_batch(["a", "b"]) is None
