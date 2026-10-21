from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator, model_validator
from pydantic_core import PydanticCustomError

from lab1.domain.errors import SubmissionError
from lab1.domain.models import AIDeclaration, Assignment, Submission


class StrictInput(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)


def nonblank(value: str) -> str:
    if not value.strip():
        raise ValueError("Значение не должно быть пустым")
    return value


class AIDeclarationInput(StrictInput):
    used: bool
    tool: str | None
    purpose: str | None
    verified_by_student: bool

    @field_validator("tool", "purpose")
    @classmethod
    def check_optional(cls, value: str | None) -> str | None:
        return nonblank(value) if value is not None else None

    @model_validator(mode="after")
    def check_used(self) -> Self:
        if self.used and (self.tool is None or self.purpose is None):
            raise ValueError("При used=true обязательны непустые tool и purpose")
        return self

    def to_domain(self) -> AIDeclaration:
        return AIDeclaration(self.used, self.tool, self.purpose, self.verified_by_student)


class SubmissionInput(StrictInput):
    schema_version: int
    submission_id: str
    student_id: str
    assignment_id: str
    submitted_at: str
    text: str
    code: str
    template_id: str | None
    ai_declaration: AIDeclarationInput

    @field_validator("schema_version")
    @classmethod
    def check_version(cls, value: int) -> int:
        if value != 1:
            raise PydanticCustomError("unsupported_version", "Поддерживается версия схемы 1")
        return value

    @field_validator("submission_id", "student_id", "assignment_id")
    @classmethod
    def check_identifier(cls, value: str) -> str:
        return nonblank(value)

    @field_validator("template_id")
    @classmethod
    def check_template(cls, value: str | None) -> str | None:
        return nonblank(value) if value is not None else None

    @field_validator("submitted_at")
    @classmethod
    def check_timestamp(cls, value: str) -> str:
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("Ожидается дата ISO 8601 с часовым поясом") from exc
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("Часовой пояс обязателен")
        return value

    @model_validator(mode="after")
    def check_content(self) -> Self:
        if not self.text.strip() and not self.code.strip():
            raise PydanticCustomError("empty_content", "Текст или код должны быть непустыми")
        return self

    def to_domain(self) -> Submission:
        return Submission(
            schema_version=self.schema_version,
            submission_id=self.submission_id,
            student_id=self.student_id,
            assignment_id=self.assignment_id,
            submitted_at=self.submitted_at,
            text=self.text,
            code=self.code,
            template_id=self.template_id,
            ai_declaration=self.ai_declaration.to_domain(),
        )


def parse_submission(raw: object) -> Submission:
    try:
        return SubmissionInput.model_validate(raw).to_domain()
    except ValidationError as exc:
        error = exc.errors(include_url=False, include_input=False)[0]
        field = ".".join(str(part) for part in error["loc"]) or "$"
        if error["type"] == "empty_content":
            field = "text/code"
        code = "unsupported_version" if error["type"] == "unsupported_version" else "schema_error"
        raise SubmissionError(code, field, error["msg"]) from exc


class AssignmentInput(StrictInput):
    assignment_id: str
    allowed_template: str
    requirements: list[str]

    @field_validator("assignment_id")
    @classmethod
    def check_identifier(cls, value: str) -> str:
        return nonblank(value)

    @field_validator("requirements")
    @classmethod
    def check_requirements(cls, values: list[str]) -> list[str]:
        return [nonblank(value) for value in values]

    def to_domain(self) -> Assignment:
        return Assignment(self.assignment_id, self.allowed_template, tuple(self.requirements))
