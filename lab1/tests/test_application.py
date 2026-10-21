import json
import subprocess
import sys
from pathlib import Path

import pytest

from lab1.adapters.analyzers import DeclarationAnalyzer
from lab1.application import build_application
from lab1.cli import main
from lab1.config import load_assignments, parse_config
from lab1.demo import run_demo
from lab1.domain.errors import ConfigurationError

PROJECT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "raw",
    [
        {"analyzers": []},
        {"analyzers": [{"name": "length"}, {"name": "length"}]},
        {"analyzers": [{"name": "length", "options": {"threshold": 0.5}}]},
        {"analyzers": [{"name": 1}]},
        {"unknown": True},
        {"config_version": " "},
    ],
)
def test_invalid_config_before_first_call(raw: object) -> None:
    with pytest.raises(ConfigurationError):
        build_application(parse_config(raw))


def test_unknown_analyzer_rejected_at_startup() -> None:
    config = parse_config({"analyzers": [{"name": "typo"}]})
    with pytest.raises(ConfigurationError, match="Неизвестный анализатор"):
        build_application(config)


def test_factory_failure_rejected_at_startup() -> None:
    def broken_factory():
        raise RuntimeError("bad factory")

    config = parse_config({"analyzers": [{"name": "broken"}]})
    with pytest.raises(ConfigurationError):
        build_application(config, extra_factories={"broken": broken_factory})


def test_third_analyzer_enabled_by_configuration(payload: dict) -> None:
    config = parse_config({"analyzers": [{"name": "declaration"}]})
    app = build_application(
        config,
        assignments=load_assignments(PROJECT / "data/assignments.json"),
        extra_factories={"declaration": DeclarationAnalyzer},
    )
    submission = app.adapter.accept_payload(payload).submission
    result = app.analysis_service.run(
        submission.submission_id, "declaration", app.context_for(submission.assignment_id)
    )
    assert result.analyzer_id == "declaration"
    assert app.registry.names == ("declaration",)


def test_applications_have_isolated_state(payload: dict) -> None:
    first, second = build_application(), build_application()
    first.adapter.accept_payload(payload)
    assert len(first.repository) == 1
    assert len(second.repository) == 0
    first.registry.register("declaration", DeclarationAnalyzer)
    assert "declaration" not in second.registry.names


def test_demo_end_to_end() -> None:
    result = run_demo()
    assert result["accepted"] == 12
    assert result["duplicate"] == 12
    assert result["stored"] == 12
    assert result["reports"] == 36
    assert result["import_errors"] == []
    assert result["conflict"]["code"] == "conflict"
    assert result["original_preserved"] is True


@pytest.mark.parametrize(
    ("filename", "accepted", "duplicates", "errors", "status"),
    [
        ("submissions.jsonl", 12, 0, 0, 0),
        ("invalid_submissions.jsonl", 1, 0, 5, 1),
        ("conflict_submissions.jsonl", 1, 1, 1, 1),
    ],
)
def test_cli_import(
    filename: str, accepted: int, duplicates: int, errors: int, status: int, capsys
) -> None:
    assert main(["import", str(PROJECT / "data" / filename)]) == status
    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert not captured.err
    assert len(output["accepted"]) == accepted
    assert len(output["duplicate"]) == duplicates
    assert len(output["errors"]) == errors


def test_cli_analysis(capsys) -> None:
    assert (
        main(
            [
                "analyze",
                str(PROJECT / "data/submissions.jsonl"),
                "--assignments",
                str(PROJECT / "data/assignments.json"),
                "--config",
                str(PROJECT / "config/app.json"),
            ]
        )
        == 0
    )
    output = json.loads(capsys.readouterr().out)
    assert len(output["reports"]) == 24
    assert not output["analysis_errors"]


def test_cli_reports_unknown_assignment(capsys, tmp_path) -> None:
    assignments = tmp_path / "empty.json"
    assignments.write_text("[]", encoding="utf-8")
    assert (
        main(
            ["analyze", str(PROJECT / "data/submissions.jsonl"), "--assignments", str(assignments)]
        )
        == 1
    )
    output = json.loads(capsys.readouterr().out)
    assert not output["reports"]
    assert len(output["analysis_errors"]) == 24


def test_cli_bad_path_is_structured(capsys, tmp_path) -> None:
    assert main(["import", str(tmp_path / "missing.jsonl")]) == 2
    output = capsys.readouterr()
    assert not output.out
    assert json.loads(output.err)["error"]["code"] == "source_error"


def test_installed_package_from_outside_project(tmp_path) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "lab1", "demo"],
        cwd=tmp_path,
        capture_output=True,
        check=True,
    )
    assert json.loads(result.stdout)["reports"] == 36


def test_cli_error_stream_is_utf8(tmp_path) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "lab1", "import", str(tmp_path / "нет-файла.jsonl")],
        capture_output=True,
        check=False,
    )
    assert result.returncode == 2
    assert not result.stdout
    error = json.loads(result.stderr)["error"]
    assert error["code"] == "source_error"
    assert "нет-файла" in error["message"]
