from lab1.domain.errors import SubmissionError
from lab1.domain.hashing import submission_hash
from lab1.domain.models import Acceptance, Submission
from lab1.domain.ports import SubmissionRepository


class SubmissionService:
    def __init__(self, repository: SubmissionRepository) -> None:
        self._repository = repository

    def accept(self, submission: Submission) -> Acceptance:
        existing = self._repository.get(submission.submission_id)
        if existing is not None:
            if submission_hash(existing) == submission_hash(submission):
                return Acceptance("duplicate", existing)
            raise SubmissionError(
                "conflict", "submission_id", "Идентификатор уже принят с другим содержимым"
            )
        self._repository.add(submission)
        return Acceptance("accepted", submission)
