"""Bundled inputs for `Reporter` (replaces a long parameter list)."""
from dataclasses import dataclass
from pathlib import Path

from logger import Logger
from models import LogLevel, OutputLevel, RuleResult, Violation


@dataclass
class ReportConfig:
    violations: list[Violation]
    file_count: int
    output_level: OutputLevel
    log_level: LogLevel = LogLevel.ALL
    output_folder: Path | None = None
    max_errors: int | None = None
    logger: Logger | None = None
    failures: list[RuleResult] | None = None
