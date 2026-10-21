from lab1.adapters.json_codec import decode_json
from lab1.adapters.validation import parse_submission
from lab1.domain.models import Acceptance
from lab1.services.acceptance import SubmissionService


class AcceptanceAdapter:
    def __init__(self, service: SubmissionService) -> None:
        self._service = service

    def accept_payload(self, payload: object) -> Acceptance:
        return self._service.accept(parse_submission(payload))

    def accept_json(self, text: str) -> Acceptance:
        return self.accept_payload(decode_json(text))
