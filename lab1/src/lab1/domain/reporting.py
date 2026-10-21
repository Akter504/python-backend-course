import math
from datetime import UTC, datetime
from uuid import uuid4

from lab1.domain.errors import AnalysisFailure
from lab1.domain.hashing import stable_hash, submission_hash
from lab1.domain.models import AnalysisContext, AnalysisReport, Evidence, Finding, Submission


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AnalysisFailure(message, "report")


def validate_report(
    report: object, submission: Submission, context: AnalysisContext
) -> AnalysisReport:
    if not isinstance(report, AnalysisReport):
        raise AnalysisFailure("Ожидается AnalysisReport", "report")
    for value in (report.report_id, report.analyzer_id, report.analyzer_version):
        _require(isinstance(value, str) and bool(value.strip()), "Пустой идентификатор отчёта")
    _require(report.submission_id == submission.submission_id, "Отчёт относится к другой сдаче")
    _require(report.submission_hash == submission_hash(submission), "Неверный хеш сдачи")
    _require(
        report.config_hash == stable_hash(context.config_payload()), "Неверный хеш конфигурации"
    )
    _require(type(report.review_required) is bool, "review_required должен быть bool")
    try:
        timestamp = datetime.fromisoformat(report.created_at)
    except (ValueError, TypeError) as exc:
        raise AnalysisFailure("Неверное время отчёта", "created_at") from exc
    _require(
        timestamp.tzinfo is not None and timestamp.utcoffset() is not None,
        "Время отчёта должно содержать часовой пояс",
    )
    _require(
        isinstance(report.findings, tuple) and bool(report.findings), "Ожидается tuple findings"
    )
    for finding in report.findings:
        _require(isinstance(finding, Finding), "Ожидается Finding")
        _require(
            finding.kind in ("similarity", "rubric_feedback", "processing_error"),
            "Неизвестный kind",
        )
        score = finding.score
        if score is not None:
            _require(
                type(score) in (int, float) and math.isfinite(score) and 0 <= score <= 1,
                "score должен быть конечным числом 0–1 либо None",
            )
        _require(
            isinstance(finding.explanation, str) and bool(finding.explanation.strip()),
            "Объяснение обязательно",
        )
        _require(isinstance(finding.evidence, tuple), "Ожидается tuple evidence")
        for evidence in finding.evidence:
            _require(isinstance(evidence, Evidence), "Ожидается Evidence")
            _require(
                evidence.submission_id == submission.submission_id,
                "Evidence относится к другой сдаче",
            )
            _require(evidence.field in ("text", "code"), "Неизвестное поле evidence")
            _require(
                type(evidence.start_line) is int and type(evidence.end_line) is int,
                "Номер строки должен быть int",
            )
            _require(
                1
                <= evidence.start_line
                <= evidence.end_line
                <= len(getattr(submission, evidence.field).splitlines()),
                "Evidence выходит за границы оригинала",
            )
    return report


def make_report(
    submission: Submission,
    context: AnalysisContext,
    analyzer_id: str,
    analyzer_version: str,
    findings: tuple[Finding, ...],
    *,
    review_required: bool = False,
) -> AnalysisReport:
    if submission.assignment_id != context.assignment.assignment_id:
        raise AnalysisFailure("Контекст относится к другому заданию", "assignment_id")
    report = AnalysisReport(
        report_id=str(uuid4()),
        submission_id=submission.submission_id,
        submission_hash=submission_hash(submission),
        analyzer_id=analyzer_id,
        analyzer_version=analyzer_version,
        config_hash=stable_hash(context.config_payload()),
        findings=findings,
        created_at=datetime.now(UTC).isoformat(),
        review_required=review_required,
    )
    return validate_report(report, submission, context)
