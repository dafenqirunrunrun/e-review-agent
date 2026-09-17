class DocumentIngestionError(RuntimeError):
    """Base error with a stable operational reason code."""

    def __init__(self, reason_code: str, detail: str = ""):
        super().__init__(detail or reason_code)
        self.reason_code = reason_code


class ParserUnavailableError(DocumentIngestionError):
    pass


class DocumentParseError(DocumentIngestionError):
    pass
