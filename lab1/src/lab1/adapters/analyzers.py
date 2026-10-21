from lab1.domain.models import AnalysisContext, AnalysisReport, Evidence, Finding, Submission
from lab1.domain.reporting import make_report


class LengthAnalyzer:
    analyzer_id = "length"
    analyzer_version = "1.0"

    def analyze(self, submission: Submission, context: AnalysisContext) -> AnalysisReport:
        findings: list[Finding] = []
        for field in ("text", "code"):
            numbers = tuple(
                number
                for number, line in enumerate(getattr(submission, field).splitlines(), 1)
                if line.strip()
            )
            evidence = tuple(
                Evidence(submission.submission_id, field, number, number) for number in numbers
            )
            findings.append(
                Finding(
                    "rubric_feedback",
                    None,
                    evidence,
                    f"{field}: непустых строк {len(numbers)}. "
                    "Количество строк не оценивает качество.",
                )
            )
        return make_report(
            submission, context, self.analyzer_id, self.analyzer_version, tuple(findings)
        )


def template_ranges(source: str, template: str) -> tuple[tuple[int, int], ...]:
    if not template.strip():
        return ()
    lines, pattern = source.splitlines(), template.splitlines()
    width = len(pattern)
    return tuple(
        (index + 1, index + width)
        for index in range(len(lines) - width + 1)
        if lines[index : index + width] == pattern
    )


class TemplateAnalyzer:
    analyzer_id = "template"
    analyzer_version = "1.0"

    def analyze(self, submission: Submission, context: AnalysisContext) -> AnalysisReport:
        ranges = template_ranges(submission.code, context.assignment.allowed_template)
        evidence = tuple(
            Evidence(submission.submission_id, "code", start, end) for start, end in ranges
        )
        explanation = (
            f"Найдено блоков разрешённого шаблона: {len(ranges)}. "
            "Совпадение разрешено и не является доказательством плагиата."
            if ranges
            else "Точный блок разрешённого шаблона не найден. Нечёткое сходство не проверялось."
        )
        return make_report(
            submission,
            context,
            self.analyzer_id,
            self.analyzer_version,
            (Finding("similarity", None, evidence, explanation),),
        )


class DeclarationAnalyzer:
    analyzer_id = "declaration"
    analyzer_version = "1.0"

    def analyze(self, submission: Submission, context: AnalysisContext) -> AnalysisReport:
        declaration = submission.ai_declaration
        complete = bool(
            declaration.tool
            and declaration.tool.strip()
            and declaration.purpose
            and declaration.purpose.strip()
        )
        if declaration.used:
            explanation = (
                "Использование ИИ заявлено; инструмент и цель заполнены."
                if complete
                else "При used=true отсутствует инструмент или цель использования ИИ."
            )
        else:
            explanation = "Использование ИИ не заявлено. Авторство автоматически не определялось."
        return make_report(
            submission,
            context,
            self.analyzer_id,
            self.analyzer_version,
            (Finding("rubric_feedback", None, (), explanation),),
            review_required=declaration.used
            and (not complete or not declaration.verified_by_student),
        )
