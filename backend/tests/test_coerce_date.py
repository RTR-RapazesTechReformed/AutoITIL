"""Testes de _coerce_date — conversão da coluna `data` antes do INSERT.

Regressão do bug em que "13/01/2026 08:20" (dia > 12, formato brasileiro)
derrubava o upload inteiro com DatetimeFieldOverflow, porque a string ia
crua para a coluna DATE e o Postgres a lia com datestyle MDY.
"""

from __future__ import annotations

from datetime import date, datetime

import pytest

from app.tickets.persistence import _coerce_date


@pytest.mark.parametrize(
    "entrada,esperado",
    [
        # O caso que quebrava: dia > 12 no formato brasileiro, com hora.
        ("13/01/2026 08:20", date(2026, 1, 13)),
        ("31/12/2025", date(2025, 12, 31)),
        # Dia <= 12 é ambíguo; dayfirst=True resolve para o padrão brasileiro.
        ("04/03/2026", date(2026, 3, 4)),
        # ISO continua funcionando.
        ("2024-03-15", date(2024, 3, 15)),
        # Formato americano: dia-primeiro é impossível (não há mês 20),
        # então o dateutil inverte sozinho.
        ("04/20/2024", date(2024, 4, 20)),
        # Mês por extenso.
        ("20 Apr 2024", date(2024, 4, 20)),
    ],
)
def test_converte_formatos_validos(entrada, esperado):
    assert _coerce_date(entrada) == esperado


def test_datetime_vira_date():
    assert _coerce_date(datetime(2026, 1, 13, 8, 20)) == date(2026, 1, 13)


def test_date_passa_direto():
    assert _coerce_date(date(2026, 1, 13)) == date(2026, 1, 13)


@pytest.mark.parametrize("entrada", ["nao-sei-a-data", "amanha", "em breve", ""])
def test_data_ilegivel_vira_none(entrada):
    """Não derruba o lote: a coluna é nullable e perder uma data é melhor
    que perder o upload (ver sample/csv_15_data_invalida.csv)."""
    assert _coerce_date(entrada) is None


def test_nan_e_none_continuam_none():
    """Preserva o comportamento de _none_if_missing (célula vazia vira NaN
    depois que o pandas lê o CSV)."""
    assert _coerce_date(float("nan")) is None
    assert _coerce_date(None) is None
