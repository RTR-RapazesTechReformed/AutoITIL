"""Testes do DescriptionEnricher (F2-4). Mesmo padrão de
test_bert_classifier.py: tokenizer/modelo mockados via patch, sem baixar
pesos reais — a inferência real de fato já foi validada manualmente contra
google/gemma-3-1b-it."""

from unittest.mock import patch

import torch

from app.enrichment.enricher import DescriptionEnricher, _parse_structured_output


class TestIsAvailable:
    def test_false_when_model_fails_to_load(self):
        with patch(
            "app.enrichment.enricher.AutoTokenizer.from_pretrained",
            side_effect=OSError("sem rede"),
        ):
            enricher = DescriptionEnricher(model_name="algum/modelo")
            assert enricher.is_available() is False

    def test_true_when_model_loads(self):
        with (
            patch("app.enrichment.enricher.AutoTokenizer"),
            patch("app.enrichment.enricher.AutoModelForCausalLM") as mock_model,
        ):
            fake_model = mock_model.from_pretrained.return_value
            fake_model.eval.return_value = fake_model

            enricher = DescriptionEnricher(model_name="algum/modelo")
            assert enricher.is_available() is True

    def test_load_is_lazy_and_idempotent(self):
        with (
            patch("app.enrichment.enricher.AutoTokenizer") as mock_tok,
            patch("app.enrichment.enricher.AutoModelForCausalLM") as mock_model,
        ):
            fake_model = mock_model.from_pretrained.return_value
            fake_model.eval.return_value = fake_model

            enricher = DescriptionEnricher(model_name="algum/modelo")
            assert mock_tok.from_pretrained.call_count == 0

            enricher.is_available()
            enricher.is_available()
            assert mock_tok.from_pretrained.call_count == 1
            assert mock_model.from_pretrained.call_count == 1


class TestEnrich:
    def test_returns_none_when_model_unavailable(self):
        with patch(
            "app.enrichment.enricher.AutoTokenizer.from_pretrained",
            side_effect=OSError("sem rede"),
        ):
            enricher = DescriptionEnricher(model_name="algum/modelo")
            assert enricher.enrich("vpn caiu") is None

    def test_returns_decoded_text_via_generate(self):
        with (
            patch("app.enrichment.enricher.AutoTokenizer") as mock_tok,
            patch("app.enrichment.enricher.AutoModelForCausalLM") as mock_model,
        ):
            fake_tokenizer = mock_tok.from_pretrained.return_value
            fake_tokenizer.apply_chat_template.return_value = "<prompt>"
            input_ids = torch.tensor([[1, 2, 3]])
            attention_mask = torch.tensor([[1, 1, 1]])
            fake_tokenizer.side_effect = lambda text, return_tensors: {
                "input_ids": input_ids,
                "attention_mask": attention_mask,
            }
            fake_tokenizer.decode.return_value = (
                "OBJETIVO: Resolver a VPN que não está conectando.\n"
                "REQUISIÇÕES: Verificar configuração de rede; Testar conectividade.\n"
                "CARGO: Suporte de redes."
            )

            fake_model = mock_model.from_pretrained.return_value
            fake_model.eval.return_value = fake_model
            # generate() devolve o prompt original concatenado com os
            # tokens novos gerados (mesmo contrato real da API) — os
            # valores exatos dos tokens novos não importam, só o
            # comprimento e o que .decode() (mockado acima) devolve.
            fake_model.generate.return_value = torch.tensor([[1, 2, 3, 4, 5]])

            enricher = DescriptionEnricher(model_name="algum/modelo")
            resultado = enricher.enrich("vpn nao conecta")

            assert resultado == {
                "objetivo": "Resolver a VPN que não está conectando.",
                "requisicoes": [
                    "Verificar configuração de rede",
                    "Testar conectividade",
                ],
                "cargo_recomendado": "Suporte de redes.",
            }
            fake_model.generate.assert_called_once()
            _, call_kwargs = fake_model.generate.call_args
            assert call_kwargs["max_new_tokens"] == 150
            assert call_kwargs["do_sample"] is False
            assert torch.equal(call_kwargs["input_ids"], input_ids)
            assert torch.equal(call_kwargs["attention_mask"], attention_mask)
            fake_tokenizer.decode.assert_called_once()

    def test_records_last_call_metrics_on_success(self):
        with (
            patch("app.enrichment.enricher.AutoTokenizer") as mock_tok,
            patch("app.enrichment.enricher.AutoModelForCausalLM") as mock_model,
        ):
            fake_tokenizer = mock_tok.from_pretrained.return_value
            fake_tokenizer.apply_chat_template.return_value = "<prompt>"
            input_ids = torch.tensor([[1, 2, 3]])
            attention_mask = torch.tensor([[1, 1, 1]])
            fake_tokenizer.side_effect = lambda text, return_tensors: {
                "input_ids": input_ids,
                "attention_mask": attention_mask,
            }
            fake_tokenizer.decode.return_value = (
                "OBJETIVO: X.\nREQUISIÇÕES: Y.\nCARGO: Z."
            )

            fake_model = mock_model.from_pretrained.return_value
            fake_model.eval.return_value = fake_model
            fake_model.generate.return_value = torch.tensor([[1, 2, 3, 4, 5]])

            enricher = DescriptionEnricher(model_name="algum/modelo")
            assert enricher.last_call_duration_ms is None

            resultado = enricher.enrich("vpn nao conecta")

            assert resultado is not None
            assert enricher.last_call_duration_ms is not None
            assert enricher.last_call_duration_ms >= 0
            assert enricher.last_call_tokens_entrada == 3
            assert enricher.last_call_tokens_saida == 2

    def test_last_call_metrics_stay_none_when_generation_fails(self):
        with (
            patch("app.enrichment.enricher.AutoTokenizer") as mock_tok,
            patch("app.enrichment.enricher.AutoModelForCausalLM") as mock_model,
        ):
            fake_tokenizer = mock_tok.from_pretrained.return_value
            fake_tokenizer.apply_chat_template.side_effect = RuntimeError("boom")

            fake_model = mock_model.from_pretrained.return_value
            fake_model.eval.return_value = fake_model

            enricher = DescriptionEnricher(model_name="algum/modelo")
            assert enricher.enrich("vpn nao conecta") is None
            assert enricher.last_call_duration_ms is None
            assert enricher.last_call_tokens_entrada is None
            assert enricher.last_call_tokens_saida is None

    def test_returns_none_when_generation_raises(self):
        with (
            patch("app.enrichment.enricher.AutoTokenizer") as mock_tok,
            patch("app.enrichment.enricher.AutoModelForCausalLM") as mock_model,
        ):
            fake_tokenizer = mock_tok.from_pretrained.return_value
            fake_tokenizer.apply_chat_template.side_effect = RuntimeError("boom")

            fake_model = mock_model.from_pretrained.return_value
            fake_model.eval.return_value = fake_model

            enricher = DescriptionEnricher(model_name="algum/modelo")
            assert enricher.enrich("vpn nao conecta") is None


class TestParseStructuredOutput:
    def test_parses_all_three_fields_splitting_requisicoes_by_semicolon(self):
        texto = (
            "OBJETIVO: Resolver a impressora que não imprime.\n"
            "REQUISIÇÕES: Reinstalar o driver da impressora; Verificar a fila de impressão.\n"
            "CARGO: Suporte técnico de TI."
        )
        assert _parse_structured_output(texto) == {
            "objetivo": "Resolver a impressora que não imprime.",
            "requisicoes": [
                "Reinstalar o driver da impressora",
                "Verificar a fila de impressão",
            ],
            "cargo_recomendado": "Suporte técnico de TI.",
        }

    def test_single_item_requisicoes_still_becomes_a_list(self):
        texto = "OBJETIVO: Resolver X.\nREQUISIÇÕES: Fazer Y.\nCARGO: Suporte."
        assert _parse_structured_output(texto)["requisicoes"] == ["Fazer Y"]

    def test_strips_whitespace_and_drops_empty_items(self):
        texto = (
            "OBJETIVO: Resolver X.\n"
            "REQUISIÇÕES:  Item um  ;Item dois;   ; Item três\n"
            "CARGO: Suporte."
        )
        assert _parse_structured_output(texto)["requisicoes"] == [
            "Item um",
            "Item dois",
            "Item três",
        ]

    def test_missing_field_becomes_placeholder_list(self):
        texto = "OBJETIVO: Resolver a VPN que não conecta.\nCARGO: Suporte de redes."
        assert _parse_structured_output(texto) == {
            "objetivo": "Resolver a VPN que não conecta.",
            "requisicoes": ["Não informado pelo modelo."],
            "cargo_recomendado": "Suporte de redes.",
        }

    def test_returns_none_when_no_marker_recognized(self):
        texto = "A VPN não está conectando desde ontem."
        assert _parse_structured_output(texto) is None

    def test_is_case_insensitive_and_tolerates_extra_whitespace(self):
        texto = "objetivo:   Resolver o problema.  \ncargo:Suporte de TI."
        result = _parse_structured_output(texto)
        assert result["objetivo"] == "Resolver o problema."
        assert result["cargo_recomendado"] == "Suporte de TI."
