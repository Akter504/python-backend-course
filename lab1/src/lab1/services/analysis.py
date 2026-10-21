from collections.abc import Callable

from lab1.domain.errors import AnalysisFailure
from lab1.domain.models import AnalysisContext, AnalysisReport
from lab1.domain.ports import Analyzer, SubmissionRepository
from lab1.domain.reporting import validate_report

type AnalyzerFactory = Callable[[], Analyzer]


class AnalyzerRegistry:
    def __init__(self) -> None:
        self._factories: dict[str, AnalyzerFactory] = {}

    def register(self, name: str, factory: AnalyzerFactory) -> None:
        if not name.strip() or name in self._factories:
            raise AnalysisFailure("Имя анализатора должно быть непустым и уникальным")
        self._factories[name] = factory

    def create(self, name: str) -> Analyzer:
        factory = self._factories.get(name)
        if factory is None:
            raise AnalysisFailure(f"Неизвестный анализатор: {name}", "analyzer_id")
        try:
            analyzer = factory()
            if analyzer.analyzer_id != name:
                raise AnalysisFailure("Имя регистрации не совпадает с analyzer_id")
            if (
                not isinstance(analyzer.analyzer_version, str)
                or not analyzer.analyzer_version.strip()
            ):
                raise AnalysisFailure("Версия анализатора обязательна")
            if not callable(getattr(analyzer, "analyze", None)):
                raise AnalysisFailure("Анализатор должен предоставлять analyze()")
        except AnalysisFailure:
            raise
        except Exception as exc:
            raise AnalysisFailure(f"Не удалось создать анализатор {name}") from exc
        return analyzer

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(self._factories)


class AnalysisService:
    def __init__(self, repository: SubmissionRepository, registry: AnalyzerRegistry) -> None:
        self._repository = repository
        self._registry = registry

    def run(
        self, submission_id: str, analyzer_name: str, context: AnalysisContext
    ) -> AnalysisReport:
        submission = self._repository.get(submission_id)
        if submission is None:
            raise AnalysisFailure("Сдача ещё не принята", "submission_id")
        if submission.assignment_id != context.assignment.assignment_id:
            raise AnalysisFailure("Контекст относится к другому заданию", "assignment_id")
        analyzer = self._registry.create(analyzer_name)
        try:
            report = validate_report(analyzer.analyze(submission, context), submission, context)
            if (report.analyzer_id, report.analyzer_version) != (
                analyzer.analyzer_id,
                analyzer.analyzer_version,
            ):
                raise AnalysisFailure("Отчёт не соответствует вызванному анализатору")
            return report
        except AnalysisFailure:
            raise
        except Exception as exc:
            raise AnalysisFailure(f"Анализатор {analyzer_name} завершился с ошибкой") from exc
