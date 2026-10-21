from dataclasses import replace

import pytest

from lab1.adapters.analyzers import DeclarationAnalyzer, template_ranges
from lab1.domain.errors import AnalysisFailure
from lab1.domain.models import AnalysisContext, Evidence, Finding
from lab1.domain.reporting import make_report, validate_report


@pytest.mark.parametrize("name", ["length", "template", "declaration"])
def test_common_analyzer_contract(name: str, app, payload: dict) -> None:
    app.registry.register("declaration", DeclarationAnalyzer)
    original = app.adapter.accept_payload(payload).submission
    context = app.context_for(original.assignment_id)
    analyzer = app.registry.create(name)
    first = analyzer.analyze(original, context)
    second = app.analysis_service.run(original.submission_id, name, context)
    assert validate_report(first, original, context) is first
    assert first.findings == second.findings
    assert first.submission_hash == second.submission_hash
    assert first.config_hash == second.config_hash
    assert first.analyzer_id == name
    assert first.analyzer_version == analyzer.analyzer_version
    assert all(finding.score is None for finding in first.findings)
    assert app.repository.get(original.submission_id) is original
    wrong = AnalysisContext(replace(context.assignment, assignment_id="other"))
    with pytest.raises(AnalysisFailure):
        analyzer.analyze(original, wrong)


def test_length_uses_original_line_numbers(app, payload: dict) -> None:
    payload.update(text="\nПервый\n \nВторой\n", code="\n\nprint(1)\n")
    submission = app.adapter.accept_payload(payload).submission
    report = app.analysis_service.run(
        submission.submission_id, "length", app.context_for(submission.assignment_id)
    )
    text, code = report.findings
    assert [e.start_line for e in text.evidence] == [2, 4]
    assert [e.start_line for e in code.evidence] == [3]
    assert "строк 2" in text.explanation
    assert "строк 1" in code.explanation


@pytest.mark.parametrize(
    ("source", "pattern", "expected"),
    [
        ("\na\nb\n\na\nb\n", "a\nb\n", ((2, 3), (5, 6))),
        ("a\n b\n", "a\nb", ()),
        ("a\nb", "a\nb\n", ((1, 2),)),
        ("a\r\nb\r\n", "a\nb", ((1, 2),)),
        ("a\na\na\n", "a\na", ((1, 2), (2, 3))),
        ("a\nb", " \n", ()),
        ("", "a", ()),
        ("a", "a\nb", ()),
    ],
)
def test_template_ranges(source: str, pattern: str, expected: tuple) -> None:
    assert template_ranges(source, pattern) == expected


def test_template_reports_allowed_match_with_original_evidence(app, payload: dict) -> None:
    payload["code"] = "\na\nb\n\na\nb\n"
    submission = app.adapter.accept_payload(payload).submission
    context = app.context_for(submission.assignment_id)
    context = replace(context, assignment=replace(context.assignment, allowed_template="a\nb\n"))
    report = app.analysis_service.run(submission.submission_id, "template", context)
    finding = report.findings[0]
    assert finding.kind == "similarity"
    assert "разрешено" in finding.explanation
    assert [(e.start_line, e.end_line) for e in finding.evidence] == [(2, 3), (5, 6)]


@pytest.fixture
def valid_report(app, payload: dict):
    submission = app.adapter.accept_payload(payload).submission
    context = app.context_for(submission.assignment_id)
    report = app.analysis_service.run(submission.submission_id, "length", context)
    return submission, context, report


@pytest.mark.parametrize("score", [True, float("nan"), float("inf"), -0.1, 1.5, "0.5"])
def test_bad_scores_rejected(valid_report, score: object) -> None:
    submission, context, report = valid_report
    bad = replace(report, findings=(replace(report.findings[0], score=score),))
    with pytest.raises(AnalysisFailure):
        validate_report(bad, submission, context)


@pytest.mark.parametrize(
    "change",
    [
        {"start_line": 0},
        {"end_line": 1000},
        {"start_line": 2, "end_line": 1},
        {"start_line": True},
        {"end_line": "1"},
        {"field": "missing"},
        {"submission_id": "other"},
    ],
)
def test_bad_evidence_rejected(valid_report, change: dict) -> None:
    submission, context, report = valid_report
    evidence = replace(Evidence(submission.submission_id, "code", 1, 1), **change)
    bad = replace(report, findings=(Finding("similarity", None, (evidence,), "reason"),))
    with pytest.raises(AnalysisFailure):
        validate_report(bad, submission, context)


@pytest.mark.parametrize(
    "change",
    [
        {"submission_id": "other"},
        {"submission_hash": "wrong"},
        {"config_hash": "wrong"},
        {"created_at": "2026-10-14"},
        {"review_required": 1},
        {"analyzer_id": " "},
        {"findings": ()},
        {"findings": (None,)},
        {"findings": (Finding("rubric_feedback", None, (), " "),)},
    ],
)
def test_invalid_report_rejected(valid_report, change: dict) -> None:
    submission, context, report = valid_report
    with pytest.raises(AnalysisFailure):
        validate_report(replace(report, **change), submission, context)


def test_config_hash_tracks_version_and_assignment(valid_report, app) -> None:
    submission, context, original = valid_report
    for changed in [
        replace(context, config_version="2"),
        replace(context, assignment=replace(context.assignment, allowed_template="new")),
        replace(context, assignment=replace(context.assignment, requirements=("new",))),
    ]:
        result = app.analysis_service.run(submission.submission_id, "length", changed)
        assert result.config_hash != original.config_hash
        with pytest.raises(AnalysisFailure):
            validate_report(original, submission, changed)


@pytest.mark.parametrize("behavior", ["raise", "bad_type", "wrong_identity"])
def test_plugin_failure_preserves_submission(app, payload: dict, behavior: str) -> None:
    original = app.adapter.accept_payload(payload).submission
    context = app.context_for(original.assignment_id)

    class BrokenAnalyzer:
        analyzer_id = "broken"
        analyzer_version = "1.0"

        def analyze(self, submission, context):
            if behavior == "raise":
                raise RuntimeError("plugin error")
            if behavior == "bad_type":
                return {"score": 1}
            return app.registry.create("length").analyze(submission, context)

    app.registry.register("broken", BrokenAnalyzer)
    with pytest.raises(AnalysisFailure) as caught:
        app.analysis_service.run(original.submission_id, "broken", context)
    assert caught.value.code == "analysis_error"
    assert app.repository.get(original.submission_id) is original
    assert len(app.repository) == 1
    assert app.analysis_service.run(original.submission_id, "length", context).findings


def test_declaration_plugin_flags_unverified_use(app, payload: dict) -> None:
    payload["ai_declaration"].update(
        used=True, tool="Assistant", purpose="Подсказка", verified_by_student=False
    )
    submission = app.adapter.accept_payload(payload).submission
    app.registry.register("declaration", DeclarationAnalyzer)
    report = app.analysis_service.run(
        submission.submission_id, "declaration", app.context_for(submission.assignment_id)
    )
    assert report.review_required is True


def test_unknown_submission_and_analyzer(app, payload: dict) -> None:
    context = app.context_for(payload["assignment_id"])
    with pytest.raises(AnalysisFailure):
        app.analysis_service.run("unknown", "length", context)
    app.adapter.accept_payload(payload)
    with pytest.raises(AnalysisFailure):
        app.analysis_service.run(payload["submission_id"], "unknown", context)


def test_context_reader_is_injected_and_replaceable(app, payload: dict) -> None:
    original = app.adapter.accept_payload(payload).submission
    context = app.context_for(original.assignment_id)
    assert context.submissions.get(original.submission_id) is original

    class FakeReader:
        def get(self, submission_id):
            assert submission_id == original.submission_id
            return replace(original, text="Данные из подменённого интерфейса")

    class LookupAnalyzer:
        analyzer_id = "lookup"
        analyzer_version = "1.0"

        def analyze(self, submission, context):
            reference = context.submissions.get(submission.submission_id)
            return make_report(
                submission,
                context,
                self.analyzer_id,
                self.analyzer_version,
                (Finding("rubric_feedback", None, (), reference.text),),
            )

    app.registry.register("lookup", LookupAnalyzer)
    replaced_context = replace(context, submissions=FakeReader())
    report = app.analysis_service.run(original.submission_id, "lookup", replaced_context)
    assert report.findings[0].explanation == "Данные из подменённого интерфейса"
    assert app.repository.get(original.submission_id) is original
    assert replaced_context.config_payload() == context.config_payload()
