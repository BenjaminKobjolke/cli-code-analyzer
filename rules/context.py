"""Shared DTO passed to every rule constructor."""
from dataclasses import dataclass
from pathlib import Path

from logger import Logger
from models import LogLevel


@dataclass(frozen=True)
class RuleContext:
    config: dict
    base_path: Path | None = None
    output_folder: Path | None = None
    log_level: LogLevel = LogLevel.ALL
    max_errors: int | None = None
    rules_file_path: str | None = None
    logger: Logger | None = None
    language: str | None = None
