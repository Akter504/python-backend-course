import hashlib
import json
from dataclasses import asdict

from lab1.domain.models import Submission


def stable_hash(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def submission_hash(submission: Submission) -> str:
    return stable_hash(asdict(submission))
