import copy
import json
from pathlib import Path

import pytest

from lab1.adapters.sources import InMemorySource, JSONLSource
from lab1.domain.errors import SourceError
from lab1.services.importing import import_source


@pytest.fixture(params=["memory", "jsonl"])
def source(request, payload: dict, tmp_path):
    items = [payload, {**payload, "submission_id": "sub-two"}]
    if request.param == "memory":
        return InMemorySource(items)
    path = tmp_path / "records.jsonl"
    path.write_text("".join(json.dumps(item) + "\n" for item in items), encoding="utf-8")
    return JSONLSource(path)


def test_common_source_contract(source, payload: dict) -> None:
    with source.open() as records:
        loaded = list(records)
    assert [record.line_no for record in loaded] == [1, 2]
    assert all(record.error is None for record in loaded)
    assert loaded[0].raw == payload
    loaded[0].raw["ai_declaration"]["used"] = True
    with source.open() as records:
        assert next(records).raw == payload


def test_import_accepts_either_source(source, app) -> None:
    first = import_source(source, app.adapter)
    second = import_source(source, app.adapter)
    assert first.accepted == ["sub-001", "sub-two"]
    assert second.duplicate == first.accepted
    assert not first.errors and not second.errors
    assert len(app.repository) == 2


def test_in_memory_takes_snapshot(payload: dict) -> None:
    before = copy.deepcopy(payload)
    source = InMemorySource([payload])
    payload["ai_declaration"]["used"] = True
    with source.open() as records:
        assert next(records).raw == before


@pytest.mark.parametrize("termination", ["normal", "break", "exception"])
def test_actual_file_handle_closed(payload: dict, tmp_path, monkeypatch, termination: str) -> None:
    path = tmp_path / "source.jsonl"
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    real_open = Path.open
    handles = []

    def observed_open(self, *args, **kwargs):
        handle = real_open(self, *args, **kwargs)
        handles.append(handle)
        return handle

    monkeypatch.setattr(Path, "open", observed_open)
    source = JSONLSource(path)
    try:
        with source.open() as records:
            assert not handles[0].closed
            for _ in records:
                if termination == "exception":
                    raise RuntimeError("consumer failure")
                if termination == "break":
                    break
    except RuntimeError:
        assert termination == "exception"
    assert handles[0].closed
    assert source.last_closed is True
    assert list(records) == []


def test_bad_json_utf8_and_schema_do_not_stop_import(payload: dict, app, tmp_path) -> None:
    path = tmp_path / "mixed.jsonl"
    path.write_bytes(
        b"{broken\n\xff\n\n"
        + json.dumps({**payload, "student_id": ""}).encode()
        + b"\n"
        + json.dumps(payload).encode()
        + b"\n"
    )
    summary = import_source(JSONLSource(path), app.adapter)
    assert summary.accepted == [payload["submission_id"]]
    assert [error["line"] for error in summary.errors] == [1, 2, 3, 4]
    assert [error["code"] for error in summary.errors] == [
        "invalid_json",
        "invalid_json",
        "invalid_json",
        "schema_error",
    ]


def test_missing_source_is_explicit(tmp_path, app) -> None:
    with pytest.raises(SourceError):
        import_source(JSONLSource(tmp_path / "missing.jsonl"), app.adapter)
