from app.domain.constants import TARGET_FIELDS
from app.domain.errors import IngestionError


class MappingValidator:
    @staticmethod
    def validate(mapping, dataframe_columns=None):
        valid_fields = set(TARGET_FIELDS)

        for target_field in mapping.values():
            if target_field not in valid_fields:
                supported = ", ".join(TARGET_FIELDS.keys())
                raise IngestionError(
                    f"Campo interno inválido: {target_field}. Use apenas: {supported}.",
                    code="INVALID_MAPPING_FIELD",
                )

        duplicated_fields = [
            field
            for field in set(mapping.values())
            if list(mapping.values()).count(field) > 1
        ]

        if duplicated_fields:
            raise IngestionError(
                f"Campo interno duplicado no mapeamento: {duplicated_fields[0]}.",
                code="DUPLICATE_MAPPING_FIELD",
            )

        if dataframe_columns is not None:
            available_columns = set(dataframe_columns)

            for source_column in mapping:
                if source_column not in available_columns:
                    raise IngestionError(
                        f"Coluna mapeada não existe no arquivo: {source_column}.",
                        code="COLUMN_NOT_FOUND",
                    )

        required_fields = [
            field for field, meta in TARGET_FIELDS.items() if meta["required"]
        ]

        mapped = mapping.values()

        for field in required_fields:
            if field not in mapped:
                raise IngestionError(
                    f"Campo obrigatório ausente: {field}.",
                    code="MISSING_REQUIRED_FIELD",
                )
