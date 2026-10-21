from pathlib import Path

from pydantic import Field, ValidationError, field_validator

from lab1.adapters.json_codec import decode_json
from lab1.adapters.validation import AssignmentInput, StrictInput, nonblank
from lab1.domain.errors import ConfigurationError, SubmissionError
from lab1.domain.models import Assignment


class AnalyzerOptions(StrictInput):
    pass


class AnalyzerConfig(StrictInput):
    name: str
    options: AnalyzerOptions = Field(default_factory=AnalyzerOptions)

    @field_validator("name")
    @classmethod
    def check_name(cls, value: str) -> str:
        return nonblank(value)


class AppConfig(StrictInput):
    config_version: str = "1"
    analyzers: tuple[AnalyzerConfig, ...] = (
        AnalyzerConfig(name="length"),
        AnalyzerConfig(name="template"),
    )

    @field_validator("config_version")
    @classmethod
    def check_version(cls, value: str) -> str:
        return nonblank(value)

    @field_validator("analyzers", mode="before")
    @classmethod
    def freeze_json_array(cls, value: object) -> object:
        return tuple(value) if isinstance(value, list) else value

    @field_validator("analyzers")
    @classmethod
    def check_names(cls, value: tuple[AnalyzerConfig, ...]) -> tuple[AnalyzerConfig, ...]:
        if not value or len({item.name for item in value}) != len(value):
            raise ValueError("Нужен непустой список уникальных анализаторов")
        return value


def parse_config(raw: object) -> AppConfig:
    try:
        return AppConfig.model_validate(raw)
    except ValidationError as exc:
        error = exc.errors(include_url=False, include_input=False)[0]
        field = ".".join(str(part) for part in error["loc"]) or "config"
        raise ConfigurationError(error["msg"], field) from exc


def read_json_file(path: Path) -> object:
    try:
        return decode_json(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, SubmissionError) as exc:
        raise ConfigurationError(f"Невозможно прочитать {path}: {exc}") from exc


def load_config(path: Path) -> AppConfig:
    return parse_config(read_json_file(path))


def parse_assignments(raw: object) -> tuple[Assignment, ...]:
    if not isinstance(raw, list):
        raise ConfigurationError("assignments.json должен содержать массив заданий", "assignments")
    try:
        assignments = tuple(AssignmentInput.model_validate(item).to_domain() for item in raw)
    except ValidationError as exc:
        error = exc.errors(include_url=False, include_input=False)[0]
        raise ConfigurationError(error["msg"], "assignments") from exc
    if len({item.assignment_id for item in assignments}) != len(assignments):
        raise ConfigurationError("Повтор assignment_id", "assignments")
    return assignments


def load_assignments(path: Path) -> tuple[Assignment, ...]:
    return parse_assignments(read_json_file(path))
