"""Testes para app/preprocessing/cleaner.py"""

import pandas as pd
import pytest

from app.preprocessing.cleaner import TextCleaner


@pytest.fixture
def cleaner():
    return TextCleaner()


def test_clean_removes_email(cleaner):
    result = cleaner.clean("Vi com joao@empresa.com.br que o servidor caiu")
    assert "@" not in result
    assert "joao" not in result
    assert result == "vi servidor caiu"


def test_clean_removes_chamado_number(cleaner):
    result = cleaner.clean("Relacionado ao chamado #4521 de ontem")
    assert "#" not in result
    assert "4521" not in result


def test_clean_removes_stopwords(cleaner):
    result = cleaner.clean("não consigo acessar o sistema")
    tokens = result.split()
    assert "o" not in tokens


def test_clean_empty_string_returns_empty(cleaner):
    assert cleaner.clean("") == ""
    assert cleaner.clean("   ") == ""


def test_clean_normalizes_accents(cleaner):
    result = cleaner.clean("autenticação falhou no sistema")
    assert "autenticacao" in result


def test_clean_removes_hora_grudada(cleaner):
    result = cleaner.clean("sistema caiu as14h30 sem aviso")
    assert "14h30" not in result
    assert "14h" not in result


@pytest.mark.parametrize(
    "text, expected",
    [
        ("VPN do escritório caiu, erro na porta 443 desde 14h30.", "vpn"),
        ("Violação do SLA", "sla"),
        ("Clusters do K8S com falhas", "k8s"),
        ("Erro no LDAP do domínio empresa.local", "ldap"),
        ("Problemas com meu SSH remoto", "ssh"),
    ],
)
def test_clean_preserves_protected_terms(cleaner, text, expected):
    result = cleaner.clean(text)
    assert expected in result


def test_clean_handles_none_gracefully(cleaner):
    assert cleaner.clean(None) == ""  # type: ignore


def test_clean_removes_url(cleaner):
    result = cleaner.clean("erro em https://portal.empresa.com.br/login ao acessar")
    assert "https" not in result
    assert "portal" not in result


def test_clean_dataframe_adds_descricao_limpa_column(cleaner):
    df = pd.DataFrame(
        {
            "descricao": [
                "VPN do escritório caiu desde as14h30",
                "Solicito acesso ao ERP para emitir NF-e",
            ]
        }
    )
    result = cleaner.clean_dataframe(df, col="descricao")
    assert "descricao_limpa" in result.columns
    assert len(result) == 2
    assert result["descricao"].iloc[0] == "VPN do escritório caiu desde as14h30"


def test_clean_dataframe_does_not_modify_original(cleaner):
    df = pd.DataFrame({"descricao": ["servidor fora do ar"]})
    original_cols = list(df.columns)
    cleaner.clean_dataframe(df)
    assert list(df.columns) == original_cols


def test_clean_dataframe_handles_empty_descriptions(cleaner):
    df = pd.DataFrame({"descricao": ["", None, "sistema lento"]})
    result = cleaner.clean_dataframe(df)
    assert result["descricao_limpa"].iloc[0] == ""
    assert result["descricao_limpa"].iloc[1] == ""
    assert result["descricao_limpa"].iloc[2] != ""


def test_clean_dataframe_applies_cleaning(cleaner):
    df = pd.DataFrame({"descricao": ["VPN caiu as14h30", "Erro em joao@empresa.com"]})

    result = cleaner.clean_dataframe(df)

    assert result["descricao_limpa"].iloc[0] == "vpn caiu"
    assert "@" not in result["descricao_limpa"].iloc[1]


def test_clean_preserves_multiword_terms(cleaner):
    result = cleaner.clean("falha no active directory do dominio")

    assert "activedirectory" in result


def test_clean_preserves_slash_terms(cleaner):
    result = cleaner.clean("pipeline ci/cd apresentou erro")

    assert "ci cd" in result


def test_clean_does_not_replace_partial_words(cleaner):
    result = cleaner.clean("equipamento apresentou falha")

    assert "ip" not in result.split()


def test_clean_does_not_break_admin_word(cleaner):
    result = cleaner.clean("administrador reiniciou sistema")

    assert "ad" not in result.split()


def test_clean_does_not_break_spicy_word(cleaner):
    result = cleaner.clean("Essa comida mexicana está muito apimentada!")

    assert "api" not in result.split()


def test_clean_is_idempotent(cleaner):
    text = "VPN do escritório caiu"

    once = cleaner.clean(text)
    twice = cleaner.clean(once)

    assert once == twice


@pytest.mark.parametrize(
    "text, expected",
    [
        ("vpn!!! caiu???", "vpn caiu"),
        ("erro $$$ no sistema", "erro sistema"),
        ("falha---ssh", "falha ssh"),
    ],
)
def test_clean_removes_special_characters(
    cleaner,
    text,
    expected,
):
    assert cleaner.clean(text) == expected


def test_clean_handles_missing_protected_file():
    cleaner = TextCleaner(protected_terms_path="arquivo_inexistente.txt")

    result = cleaner.clean("vpn caiu")

    assert isinstance(result, str)
