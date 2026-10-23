"""Standalone most-complex-function analysis mode."""

import json
import sys
from pathlib import Path
from typing import TextIO

from function_complexity.models import (
    ComplexityReport,
    FunctionComplexity,
    LanguageError,
)
from function_complexity.sources import (
    SourceFile,
    analyzer_filename,
    prepare_source,
    read_paths,
)
from git_changes import GitNotAvailableError, get_changed_lines
from logger import Logger


def print_report(report: ComplexityReport, stream: TextIO | None = None) -> None:
    """Write machine-readable output to stdout by default."""
    print(json.dumps(report.to_dict(), indent=2), file=stream or sys.stdout)


def _language_errors(paths: list[SourceFile], message: str) -> list[LanguageError]:
    """Make one dependency error for each represented language, in input order."""
    languages = dict.fromkeys(source_file.language for source_file in paths)
    return [LanguageError(language, message) for language in languages]


def _analyze_file(lizard: object, source_file: SourceFile) -> list[object]:
    """Analyze one in-memory file with a fresh lizard FileAnalyzer."""
    analyzer = lizard.FileAnalyzer(  # type: ignore[attr-defined]
        lizard.analyze_file.processors  # type: ignore[attr-defined]
    )
    text = source_file.path.read_text(encoding="utf-8-sig", errors="replace")
    return analyzer.analyze_source_code(
        analyzer_filename(source_file), prepare_source(text, source_file.language)
    ).function_list


def run_most_complex_function(
    path: str,
    files_from: str,
    logger: Logger | None = None,
    diff_base: str | None = None,
) -> int:
    """Print the highest cyclomatic-complexity function from the listed files."""
    logger = logger or Logger(stream=sys.stderr)
    root = Path(path)
    if not root.is_dir():
        logger.error(f"Most complex function path is not a directory: {path}")
        return 2

    file_list = Path(files_from)
    try:
        if not file_list.is_file():
            raise OSError("file does not exist")
        source_files = read_paths(root, file_list)
    except (OSError, UnicodeError) as error:
        logger.error(f"Cannot read files-from list {files_from}: {error}")
        return 2

    changes = None
    if diff_base is not None:
        try:
            changes = get_changed_lines(root, diff_base)
        except GitNotAvailableError as error:
            logger.error(str(error))
            return 2
        source_files = [
            source_file
            for source_file in source_files
            if changes.has_changes(Path(source_file.file_path))
        ]

    try:
        import lizard
    except ImportError:
        report = ComplexityReport(
            None,
            _language_errors(
                source_files,
                "lizard not installed (pip install -r requirements.txt)",
            ),
        )
        print_report(report)
        return 0

    errors: list[LanguageError] = []
    best: FunctionComplexity | None = None
    for source_file in source_files:
        try:
            functions = _analyze_file(lizard, source_file)
        except Exception as error:  # malformed or unreadable files should not stop other inputs
            errors.append(LanguageError(source_file.language, f"{source_file.file_path}: {error}"))
            continue
        for function in sorted(functions, key=lambda item: item.start_line):
            file_path = Path(source_file.file_path)
            if (
                changes is not None
                and file_path not in changes.new_files
                and not changes.touches(file_path, function.start_line, function.end_line)
            ):
                continue
            candidate = FunctionComplexity(
                file_path=source_file.file_path,
                function_name=function.name,
                language=source_file.language,
                start_line=function.start_line,
                end_line=function.end_line,
                complexity=function.cyclomatic_complexity,
            )
            if best is None or candidate.complexity > best.complexity:
                best = candidate

    print_report(ComplexityReport(best, errors))
    return 0


__all__ = ["run_most_complex_function"]
