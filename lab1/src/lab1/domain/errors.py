class LabError(Exception):
    def __init__(self, code: str, field: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.field = field
        self.message = message

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "field": self.field, "message": self.message}


class SubmissionError(LabError):
    pass


class AnalysisFailure(LabError):
    def __init__(self, message: str, field: str = "analysis") -> None:
        super().__init__("analysis_error", field, message)


class ConfigurationError(LabError):
    def __init__(self, message: str, field: str = "config") -> None:
        super().__init__("configuration_error", field, message)


class SourceError(LabError):
    def __init__(self, message: str) -> None:
        super().__init__("source_error", "source", message)
