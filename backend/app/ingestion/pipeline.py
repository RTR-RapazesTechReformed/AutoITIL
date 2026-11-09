from app.ingestion.mapper import (
    SemanticMapper,
)
from app.ingestion.reader import FileReader
from app.ingestion.transformer import (
    DataTransformer,
)
from app.ingestion.validator import (
    MappingValidator,
)


class IngestionPipeline:
    def __init__(self):
        self.reader = FileReader()
        self.mapper = SemanticMapper()
        self.validator = MappingValidator()
        self.transformer = DataTransformer()

    def preview(self, file_path):
        dataframe = self.reader.read(file_path)

        suggestions = self.mapper.suggest(dataframe)

        return dataframe, suggestions

    def execute(self, file_path, mapping=None):
        dataframe = self.reader.read(file_path)

        if mapping is None:
            suggestions = self.mapper.suggest(dataframe)

            mapping = {}

            for suggestion in suggestions:
                mapping[suggestion.source_column] = suggestion.target_field

        self.validator.validate(
            mapping,
            dataframe_columns=dataframe.columns,
        )

        transformed = self.transformer.transform(
            dataframe,
            mapping,
        )

        return transformed
