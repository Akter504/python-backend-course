from collections.abc import Generator, Iterable, Iterator
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path

from lab1.adapters.json_codec import decode_json
from lab1.domain.errors import SourceError, SubmissionError
from lab1.domain.ports import SourceRecord


class InMemorySource:
    def __init__(self, values: Iterable[object]) -> None:
        self._values = deepcopy(tuple(values))

    @contextmanager
    def open(self) -> Iterator[Iterator[SourceRecord]]:
        records = (
            SourceRecord(number, deepcopy(value)) for number, value in enumerate(self._values, 1)
        )
        try:
            yield records
        finally:
            records.close()


class JSONLSource:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.last_closed: bool | None = None

    @contextmanager
    def open(self) -> Iterator[Iterator[SourceRecord]]:
        try:
            handle = self.path.open("rb")
        except OSError as exc:
            raise SourceError(f"Невозможно открыть {self.path}: {exc.strerror}") from exc
        self.last_closed = False

        def records() -> Generator[SourceRecord, None, None]:
            number = 0
            while True:
                try:
                    line = handle.readline()
                except OSError as exc:
                    raise SourceError(f"Ошибка чтения {self.path}: {exc.strerror}") from exc
                if not line:
                    break
                number += 1
                try:
                    raw = decode_json(line.decode("utf-8"))
                except UnicodeDecodeError:
                    yield SourceRecord(
                        number, error=SubmissionError("invalid_json", "$", "Ожидается UTF-8")
                    )
                except SubmissionError as exc:
                    yield SourceRecord(number, error=exc)
                else:
                    yield SourceRecord(number, raw=raw)

        iterator = records()
        try:
            yield iterator
        finally:
            iterator.close()
            handle.close()
            self.last_closed = handle.closed
