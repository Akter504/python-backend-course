import argparse
import json
import sys
from dataclasses import asdict
from io import TextIOWrapper
from pathlib import Path

from lab1.adapters.sources import JSONLSource
from lab1.application import build_application
from lab1.config import load_assignments, load_config
from lab1.demo import run_demo
from lab1.domain.errors import LabError
from lab1.services.importing import import_source


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, TextIOWrapper):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="lab1", description="Backend ЛР 1")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("demo", help="Встроенный сценарий: импорт, дубликат, конфликт, анализ")
    for command in ("import", "analyze"):
        sub = commands.add_parser(command)
        sub.add_argument("path", type=Path, help="Файл сдач JSONL")
        sub.add_argument("--config", type=Path, help="Конфигурация приложения JSON")
        if command == "analyze":
            sub.add_argument("--assignments", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "demo":
            output = run_demo()
            exit_code = 0
        else:
            config = load_config(args.config) if args.config else None
            assignments = load_assignments(args.assignments) if args.command == "analyze" else ()
            app = build_application(config, assignments=assignments)
            summary = import_source(JSONLSource(args.path), app.adapter)
            output = asdict(summary)
            exit_code = 1 if summary.errors else 0
            if args.command == "analyze":
                reports = []
                errors = []
                for submission_id in dict.fromkeys(summary.accepted + summary.duplicate):
                    submission = app.repository.get(submission_id)
                    assert submission is not None
                    for name in app.registry.names:
                        try:
                            report = app.analysis_service.run(
                                submission_id, name, app.context_for(submission.assignment_id)
                            )
                        except LabError as exc:
                            errors.append(
                                {
                                    "submission_id": submission_id,
                                    "analyzer_id": name,
                                    **exc.to_dict(),
                                }
                            )
                        else:
                            reports.append(asdict(report))
                output["reports"], output["analysis_errors"] = reports, errors
                exit_code = 1 if errors or summary.errors else 0
    except LabError as exc:
        print(json.dumps({"error": exc.to_dict()}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return exit_code
