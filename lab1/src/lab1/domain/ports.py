from collections.abc import Iterator
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Protocol

from lab1.domain.errors import SubmissionError
from lab1.domain.models import AnalysisContext, AnalysisReport, Submission


class SubmissionReader(Protocol):
    def get(self, submission_id: str) -> Submission | None: ...


class SubmissionRepository(SubmissionReader, Protocol):
    def add(self, submission: Submission) -> None: ...


class Analyzer(Protocol):
    @property
    def analyzer_id(self) -> str: ...

    @property
    def analyzer_version(self) -> str: ...

    def analyze(self, submission: Submission, context: AnalysisContext) -> AnalysisReport: ...


@dataclass(frozen=True, slots=True)
class SourceRecord:
    line_no: int
    raw: object = None
    error: SubmissionError | None = None


class SubmissionSource(Protocol):
    def open(self) -> AbstractContextManager[Iterator[SourceRecord]]: ...
