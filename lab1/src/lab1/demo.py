from dataclasses import asdict
from importlib.resources import files

from lab1.adapters.analyzers import DeclarationAnalyzer
from lab1.adapters.json_codec import decode_json
from lab1.adapters.sources import InMemorySource
from lab1.application import build_application
from lab1.config import parse_assignments, parse_config
from lab1.domain.errors import SubmissionError
from lab1.services.importing import import_source


def run_demo() -> dict[str, object]:
    data = files("lab1").joinpath("data")
    payloads = [
        decode_json(line)
        for line in data.joinpath("submissions.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assignments = parse_assignments(
        decode_json(data.joinpath("assignments.json").read_text(encoding="utf-8"))
    )
    config = parse_config(
        {"analyzers": [{"name": "length"}, {"name": "template"}, {"name": "declaration"}]}
    )
    app = build_application(
        config, assignments=assignments, extra_factories={"declaration": DeclarationAnalyzer}
    )
    first = import_source(InMemorySource(payloads), app.adapter)
    second = import_source(InMemorySource(payloads), app.adapter)
    original = app.repository.get(first.accepted[0])
    assert original is not None
    altered = {**asdict(original), "text": original.text + " Изменено."}
    conflict: dict[str, str] = {}
    try:
        app.adapter.accept_payload(altered)
    except SubmissionError as exc:
        conflict = exc.to_dict()
    reports = []
    for submission_id in first.accepted:
        submission = app.repository.get(submission_id)
        assert submission is not None
        context = app.context_for(submission.assignment_id)
        for name in app.registry.names:
            reports.append(app.analysis_service.run(submission_id, name, context))
    return {
        "accepted": len(first.accepted),
        "duplicate": len(second.duplicate),
        "import_errors": first.errors + second.errors,
        "conflict": conflict,
        "stored": len(app.repository),
        "reports": len(reports),
        "analyzers": list(app.registry.names),
        "original_preserved": app.repository.get(original.submission_id) == original,
        "sample_reports": [asdict(report) for report in reports[:3]],
    }
