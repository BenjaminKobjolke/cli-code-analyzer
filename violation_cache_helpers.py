"""Data and reporting helpers shared by the SQLite violation cache."""

from contextlib import suppress
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING

from models import Severity, Violation

if TYPE_CHECKING:
    from report_config import ReportConfig
    from violation_cache import ViolationCache


def newest_mtime(base_path: str, file_paths: list[str] | None) -> float:
    """Return the newest source-file mtime, or zero when no paths are supplied."""
    newest = 0.0
    for file_path in file_paths or []:
        path = Path(file_path)
        if not path.is_absolute():
            path = Path(base_path) / path
        with suppress(OSError):
            newest = max(newest, path.stat().st_mtime)
    return newest


def row_to_violation(
    row: tuple[str, str, str, str, int | None, int | None, int | None],
) -> Violation:
    """Convert a SQLite violation row into the domain model."""
    severity_map = {"ERROR": Severity.ERROR, "WARNING": Severity.WARNING, "INFO": Severity.INFO}
    return Violation(
        file_path=row[0],
        rule_name=row[1],
        severity=severity_map.get(row[2], Severity.WARNING),
        message=row[3],
        line=row[4],
        column=row[5],
        line_count=row[6],
    )


def report_cached_results(
    cache: "ViolationCache",
    file_paths: set[str],
    report_config: "ReportConfig",
    output_format: str,
) -> bool:
    """Report cached violations for a filtered file request."""
    from reporter import Reporter

    cached_config = replace(
        report_config,
        violations=cache.load_for_files(file_paths),
        file_count=0,
    )
    reporter = Reporter(cached_config)
    return (
        reporter.report_json()
        if output_format == "json"
        else reporter.report()
    )
