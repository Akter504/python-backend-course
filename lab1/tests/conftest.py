import json
from pathlib import Path

import pytest

from lab1.application import Application, build_application
from lab1.config import load_assignments

PROJECT = Path(__file__).resolve().parents[1]


@pytest.fixture
def payload() -> dict:
    line = (PROJECT / "data/submissions.jsonl").read_text(encoding="utf-8").splitlines()[0]
    return json.loads(line)


@pytest.fixture
def app() -> Application:
    return build_application(assignments=load_assignments(PROJECT / "data/assignments.json"))
