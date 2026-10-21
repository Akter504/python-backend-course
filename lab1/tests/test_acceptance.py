import copy
from dataclasses import FrozenInstanceError, asdict

import pytest
from pydantic import ValidationError

from lab1.adapters.json_codec import decode_json
from lab1.adapters.validation import SubmissionInput, parse_submission
from lab1.domain.errors import SubmissionError
from lab1.domain.hashing import submission_hash


def test_dto_conversion_and_input_immutability(payload: dict, app) -> None:
    before = copy.deepcopy(payload)
    dto = SubmissionInput.model_validate(payload)
    domain = dto.to_domain()
    result = app.adapter.accept_payload(payload)
    assert asdict(domain) == before == payload
    assert result.submission == domain
    payload["ai_declaration"]["used"] = True
    assert result.submission.ai_declaration.used is False
    with pytest.raises(FrozenInstanceError):
        result.submission.text = "changed"
    with pytest.raises(FrozenInstanceError):
        result.submission.ai_declaration.tool = "changed"
    with pytest.raises(ValidationError):
        dto.student_id = "changed"


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("student_id", " \t", "schema_error"),
        ("student_id", 123, "schema_error"),
        ("assignment_id", None, "schema_error"),
        ("submitted_at", "yesterday", "schema_error"),
        ("submitted_at", "2026-10-14T12:00:00", "schema_error"),
        ("submitted_at", "2026-99-99T12:00:00Z", "schema_error"),
        ("submitted_at", 12345, "schema_error"),
        ("schema_version", True, "schema_error"),
        ("schema_version", "1", "schema_error"),
        ("schema_version", 1.0, "schema_error"),
        ("schema_version", 2, "unsupported_version"),
        ("text", [], "schema_error"),
        ("code", None, "schema_error"),
        ("template_id", "  ", "schema_error"),
        ("studnet_id", "typo", "schema_error"),
    ],
)
def test_invalid_field(payload: dict, app, field: str, value: object, code: str) -> None:
    payload[field] = value
    before = copy.deepcopy(payload)
    with pytest.raises(SubmissionError) as caught:
        app.adapter.accept_payload(payload)
    assert caught.value.code == code
    assert caught.value.field == field
    assert caught.value.message
    assert payload == before
    assert len(app.repository) == 0


@pytest.mark.parametrize(
    "field",
    [
        "schema_version",
        "submission_id",
        "student_id",
        "assignment_id",
        "submitted_at",
        "text",
        "code",
        "template_id",
        "ai_declaration",
    ],
)
def test_required_fields(payload: dict, field: str) -> None:
    del payload[field]
    with pytest.raises(SubmissionError) as caught:
        parse_submission(payload)
    assert caught.value.field == field


@pytest.mark.parametrize("raw", [None, [], 1, "value", True])
def test_root_must_be_object(raw: object) -> None:
    with pytest.raises(SubmissionError, match="dictionary|instance"):
        parse_submission(raw)


@pytest.mark.parametrize(
    "change",
    [
        {"used": "false"},
        {"used": 1},
        {"verified_by_student": "true"},
        {"used": True},
        {"used": True, "tool": "Assistant"},
        {"used": True, "tool": "Assistant", "purpose": "  "},
        {"tool": ""},
        {"extra": "unknown"},
    ],
)
def test_ai_declaration_validation(payload: dict, change: dict) -> None:
    payload["ai_declaration"].update(change)
    with pytest.raises(SubmissionError) as caught:
        parse_submission(payload)
    assert caught.value.field.startswith("ai_declaration")


def test_valid_declaration_preserves_unverified_flag(payload: dict) -> None:
    payload["ai_declaration"] = {
        "used": True,
        "tool": "Assistant",
        "purpose": "Объяснение",
        "verified_by_student": False,
    }
    assert parse_submission(payload).ai_declaration.verified_by_student is False


def test_empty_text_and_code(payload: dict) -> None:
    payload.update(text=" \n", code="\t")
    with pytest.raises(SubmissionError) as caught:
        parse_submission(payload)
    assert caught.value.field == "text/code"


def test_duplicate_conflict_and_new_version(payload: dict, app) -> None:
    original = app.adapter.accept_payload(payload).submission
    duplicate = app.adapter.accept_payload(dict(reversed(list(payload.items()))))
    assert duplicate.status == "duplicate"
    assert duplicate.submission is original
    assert len(app.repository) == 1
    with pytest.raises(SubmissionError) as caught:
        app.adapter.accept_payload({**payload, "code": payload["code"] + "\n"})
    assert caught.value.code == "conflict"
    assert app.repository.get(original.submission_id) is original
    assert len(app.repository) == 1
    result = app.adapter.accept_payload({**payload, "submission_id": "new-version"})
    assert result.status == "accepted"
    assert len(app.repository) == 2


def test_hash_is_stable_and_preserves_original_strings(payload: dict) -> None:
    first = parse_submission(payload)
    assert submission_hash(first) == submission_hash(
        parse_submission(dict(reversed(list(payload.items()))))
    )
    for key, value in [
        ("text", payload["text"] + " "),
        ("code", payload["code"] + "\n"),
        ("student_id", "another"),
        ("submitted_at", "2026-09-01T07:01:00Z"),
    ]:
        assert submission_hash(parse_submission({**payload, key: value})) != submission_hash(first)


@pytest.mark.parametrize(
    "text",
    [
        "{",
        "",
        "NaN",
        "Infinity",
        '{"x": 1, "x": 2}',
        '{"a":{"b":1,"b":2}}',
    ],
)
def test_json_format_errors(text: str) -> None:
    with pytest.raises(SubmissionError) as caught:
        decode_json(text)
    assert caught.value.code == "invalid_json"


def test_submitted_code_is_only_data(payload: dict, app, tmp_path) -> None:
    target = tmp_path / "must-not-exist"
    payload["code"] = f"from pathlib import Path\nPath({str(target)!r}).touch()"
    result = app.adapter.accept_payload(payload)
    for name in app.registry.names:
        app.analysis_service.run(
            result.submission.submission_id, name, app.context_for(result.submission.assignment_id)
        )
    assert not target.exists()
