import csv
import io
from collections import Counter
from pathlib import Path

import pandas as pd

from app.config.settings import (
    MAX_ROWS,
    SUPPORTED_EXTENSIONS,
)
from app.domain.errors import IngestionError

CANDIDATE_SEPARATORS = [",", ";", "\t", "|"]
HEADER_SCAN_LINES = 50


def _decode(raw: bytes) -> str:
    """Decodifica bytes tolerando BOM, UTF-16 e encodings legados (Excel/Windows)."""
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16")

    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("cp1252", errors="replace")


def _field_count(line: str, separator: str) -> int:
    try:
        fields = next(csv.reader([line], delimiter=separator))
    except (csv.Error, StopIteration):
        return 0

    # Linha só de separadores (";;;;;") é vazia, não cabeçalho nem dado.
    if not any(field.strip() for field in fields):
        return 0

    return len(fields)


def _detect_layout(text: str):
    """Retorna (separador, índice da linha de cabeçalho).

    Para cada separador candidato, a "forma" da tabela é o número de campos mais
    comum entre as primeiras linhas; o cabeçalho é a primeira linha com essa
    forma (pula títulos/linhas em branco antes da tabela). Vence o separador
    cuja forma tem mais colunas e mais linhas de suporte.
    """
    lines = text.splitlines()[:HEADER_SCAN_LINES]
    best = (0, 0, ",", 0)

    for separator in CANDIDATE_SEPARATORS:
        counts = [
            _field_count(line, separator) if line.strip() else 0 for line in lines
        ]
        populated = [count for count in counts if count >= 2]

        if not populated:
            continue

        shape, support = Counter(populated).most_common(1)[0]
        score = (shape if support >= 2 or len(populated) == 1 else 0, support)

        if score > best[:2]:
            best = (*score, separator, counts.index(shape))

    return best[2], best[3]


def _read_csv(path: Path):
    text = _decode(path.read_bytes())

    if not text.strip():
        raise pd.errors.EmptyDataError("empty")

    separator, header_line = _detect_layout(text)

    dataframe = pd.read_csv(
        io.StringIO(text),
        sep=separator,
        skiprows=header_line,
        nrows=MAX_ROWS + 1,
        on_bad_lines="skip",
        skipinitialspace=True,
    )

    return _clean(dataframe)


def _clean(dataframe):
    dataframe = dataframe.dropna(how="all")
    empty_unnamed = [
        column
        for column in dataframe.columns
        if str(column).startswith("Unnamed:") and dataframe[column].isna().all()
    ]
    dataframe = dataframe.drop(columns=empty_unnamed)
    dataframe.columns = [str(column).strip() for column in dataframe.columns]

    return dataframe.reset_index(drop=True)


class FileReader:
    @staticmethod
    def validate_extension(file_path: str):
        path = Path(file_path)

        extension = path.suffix.lower()

        if extension not in SUPPORTED_EXTENSIONS:
            supported = ", ".join(SUPPORTED_EXTENSIONS)
            raise IngestionError(
                f"Formato inválido. Use apenas: {supported}.",
                code="INVALID_FILE_TYPE",
            )

        return extension

    @staticmethod
    def read(file_path: str):
        path = Path(file_path)
        extension = FileReader.validate_extension(path)

        try:
            if extension == ".csv":
                dataframe = _read_csv(path)

            else:
                dataframe = pd.read_excel(
                    path,
                    nrows=MAX_ROWS + 1,
                )

        except pd.errors.EmptyDataError as error:
            raise IngestionError(
                "Arquivo vazio ou sem colunas para leitura.",
                code="EMPTY_FILE",
            ) from error

        except Exception as error:
            raise IngestionError(
                "Não foi possível ler o arquivo. Verifique se o conteúdo corresponde ao formato enviado.",
                code="FILE_READ_ERROR",
            ) from error

        if len(dataframe.columns) == 0:
            raise IngestionError(
                "Arquivo vazio ou sem colunas para leitura.",
                code="EMPTY_FILE",
            )

        if len(dataframe) > MAX_ROWS:
            raise IngestionError(
                f"Arquivo excede o limite de {MAX_ROWS} linhas.",
                code="ROW_LIMIT_EXCEEDED",
            )

        return dataframe
