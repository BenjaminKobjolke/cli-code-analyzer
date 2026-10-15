"""Standalone read-only dependency security audit mode."""

import json
import sys
from pathlib import Path
from typing import TextIO

from dependency_audit import dart_stack, php_stack, python_stack
from dependency_audit.models import AuditReport, Ecosystem, StackError
from logger import Logger


def print_report(report: AuditReport, stream: TextIO | None = None) -> None:
    """Write machine-readable output to stdout by default."""
    print(json.dumps(report.to_dict(), indent=2), file=stream or sys.stdout)


def run_dependency_audit(path: str, logger: Logger | None = None) -> int:
    """Audit root lock files and print the combined JSON result."""
    checkout = Path(path)
    if not checkout.is_dir():
        if logger:
            logger.error(f"Dependency audit path is not a directory: {path}")
        return 2
    report = AuditReport()
    stacks = (
        (python_stack.LOCK_FILE, python_stack.audit, "python"),
        (php_stack.LOCK_FILE, php_stack.audit, "php"),
        (dart_stack.LOCK_FILE, dart_stack.audit, "dart"),
    )
    for lock_file, audit, ecosystem in stacks:
        if not (checkout / lock_file).is_file():
            continue
        error_count = len(report.errors)
        try:
            audit(checkout, report)
        except Exception as error:  # keep independent stacks running on malformed lock data
            report.errors.append(StackError(Ecosystem(ecosystem), str(error)))
        for error in report.errors[error_count:]:
            if logger:
                logger.error(f"{ecosystem} dependency audit failed: {error.message}")
    print_report(report)
    return 0


__all__ = ["run_dependency_audit"]
