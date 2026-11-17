from pathlib import Path

import pandas as pd

from app.config.settings import (
    MAX_ROWS,
    SUPPORTED_EXTENSIONS,
)
from app.domain.errors import IngestionError


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
                dataframe = pd.read_csv(
                    path,
                    nrows=MAX_ROWS + 1,
                )

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
