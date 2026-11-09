class IngestionError(ValueError):
    def __init__(self, message, code="INGESTION_ERROR"):
        super().__init__(message)
        self.code = code
