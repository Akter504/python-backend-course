from dataclasses import dataclass, field
from typing import Protocol

from lab1.domain.errors import SubmissionError
from lab1.domain.models import Acceptance
from lab1.domain.ports import SubmissionSource


class PayloadAcceptor(Protocol):
    def accept_payload(self, payload: object) -> Acceptance: ...


@dataclass
class ImportSummary:
    accepted: list[str] = field(default_factory=list)
    duplicate: list[str] = field(default_factory=list)
    errors: list[dict[str, object]] = field(default_factory=list)


def import_source(source: SubmissionSource, acceptor: PayloadAcceptor) -> ImportSummary:
    summary = ImportSummary()
    with source.open() as records:
        for record in records:
            try:
                if record.error is not None:
                    raise record.error
                result = acceptor.accept_payload(record.raw)
            except SubmissionError as exc:
                summary.errors.append({"line": record.line_no, **exc.to_dict()})
            else:
                target = summary.accepted if result.status == "accepted" else summary.duplicate
                target.append(result.submission.submission_id)
    return summary
