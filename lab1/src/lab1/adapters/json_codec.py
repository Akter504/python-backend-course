import json
from typing import NoReturn

from lab1.domain.errors import SubmissionError


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise SubmissionError("invalid_json", key, f"Повтор ключа JSON: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> NoReturn:
    raise SubmissionError("invalid_json", "$", f"Недопустимая константа JSON: {value}")


def decode_json(text: str) -> object:
    try:
        return json.loads(text, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    except json.JSONDecodeError as exc:
        raise SubmissionError(
            "invalid_json", "$", f"Некорректный JSON, столбец {exc.colno}: {exc.msg}"
        ) from exc
