from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from lab1.domain.ports import SubmissionReader


@dataclass(frozen=True, slots=True)
class AIDeclaration:
    used: bool
    tool: str | None
    purpose: str | None
    verified_by_student: bool


@dataclass(frozen=True, slots=True)
class Submission:
    schema_version: int
    submission_id: str
    student_id: str
    assignment_id: str
    submitted_at: str
    text: str
    code: str
    template_id: str | None
    ai_declaration: AIDeclaration


@dataclass(frozen=True, slots=True)
class Assignment:
    assignment_id: str
    allowed_template: str
    requirements: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AnalysisContext:
    assignment: Assignment
    config_version: str = "1"
    submissions: SubmissionReader | None = field(default=None, repr=False, compare=False)

    def config_payload(self) -> dict[str, object]:
        return {"assignment": asdict(self.assignment), "config_version": self.config_version}


@dataclass(frozen=True, slots=True)
class Evidence:
    submission_id: str
    field: Literal["text", "code"]
    start_line: int
    end_line: int


@dataclass(frozen=True, slots=True)
class Finding:
    kind: Literal["similarity", "rubric_feedback", "processing_error"]
    score: float | None
    evidence: tuple[Evidence, ...]
    explanation: str


@dataclass(frozen=True, slots=True)
class AnalysisReport:
    report_id: str
    submission_id: str
    submission_hash: str
    analyzer_id: str
    analyzer_version: str
    config_hash: str
    findings: tuple[Finding, ...]
    created_at: str
    review_required: bool


@dataclass(frozen=True, slots=True)
class Acceptance:
    status: Literal["accepted", "duplicate"]
    submission: Submission
