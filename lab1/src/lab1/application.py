from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType

from lab1.adapters.analyzers import LengthAnalyzer, TemplateAnalyzer
from lab1.adapters.repository import InMemorySubmissionRepository
from lab1.adapters.testing import AcceptanceAdapter
from lab1.config import AppConfig
from lab1.domain.errors import AnalysisFailure, ConfigurationError
from lab1.domain.models import AnalysisContext, Assignment
from lab1.services.acceptance import SubmissionService
from lab1.services.analysis import AnalysisService, AnalyzerFactory, AnalyzerRegistry


@dataclass(frozen=True, slots=True)
class Application:
    repository: InMemorySubmissionRepository
    submission_service: SubmissionService
    adapter: AcceptanceAdapter
    registry: AnalyzerRegistry
    analysis_service: AnalysisService
    assignments: Mapping[str, Assignment]
    config: AppConfig

    def context_for(self, assignment_id: str) -> AnalysisContext:
        try:
            assignment = self.assignments[assignment_id]
        except KeyError as exc:
            raise AnalysisFailure("Задание не настроено", "assignment_id") from exc
        return AnalysisContext(assignment, self.config.config_version, submissions=self.repository)


def build_application(
    config: AppConfig | None = None,
    *,
    assignments: Iterable[Assignment] = (),
    extra_factories: Mapping[str, AnalyzerFactory] | None = None,
) -> Application:
    settings = config if config is not None else AppConfig()
    factories: dict[str, AnalyzerFactory] = {"length": LengthAnalyzer, "template": TemplateAnalyzer}
    for name, factory in (extra_factories or {}).items():
        if name in factories:
            raise ConfigurationError(f"Повтор фабрики: {name}", "analyzers")
        factories[name] = factory
    registry = AnalyzerRegistry()
    for item in settings.analyzers:
        selected_factory = factories.get(item.name)
        if selected_factory is None:
            raise ConfigurationError(f"Неизвестный анализатор: {item.name}", "analyzers")
        try:
            registry.register(item.name, selected_factory)
            registry.create(item.name)
        except AnalysisFailure as exc:
            raise ConfigurationError(str(exc), "analyzers") from exc
    assignment_map: dict[str, Assignment] = {}
    for assignment in assignments:
        if assignment.assignment_id in assignment_map:
            raise ConfigurationError("Повтор assignment_id", "assignments")
        assignment_map[assignment.assignment_id] = assignment
    repository = InMemorySubmissionRepository()
    service = SubmissionService(repository)
    return Application(
        repository,
        service,
        AcceptanceAdapter(service),
        registry,
        AnalysisService(repository, registry),
        MappingProxyType(assignment_map),
        settings,
    )
