"""
Data models for the code analyzer
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal


class Severity(Enum):
    """Severity levels for violations"""
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class OutputLevel(Enum):
    """Output verbosity levels"""
    MINIMAL = "minimal"
    NORMAL = "normal"
    VERBOSE = "verbose"


class LogLevel(Enum):
    """Log levels for filtering violations"""
    ERROR = "error"
    WARNING = "warning"
    ALL = "all"


@dataclass
class Violation:
    """Represents a rule violation"""
    file_path: str
    rule_name: str
    severity: Severity
    message: str
    line_count: int = None
    line: int = None      # Source line number (1-based)
    column: int = None    # Source column number (1-based)
    function_name: str | None = None
    confidence: Literal["high", "medium", "low"] | None = None
    evidence: str | None = None
    recommendation: str | None = None


class RuleStatus(Enum):
    """Outcome of running a rule, independent of how many violations it found."""
    OK = "OK"            # ran successfully; violations may be empty (genuinely clean)
    FAILED = "FAILED"    # tool missing/crashed/unparseable — result is NOT trustworthy
    SKIPPED = "SKIPPED"  # not applicable (language unsupported, no project marker, no files)


@dataclass
class RuleResult:
    """Typed result of a rule run: status plus any violations it produced.

    Distinguishes "ran and found nothing" (OK, empty violations) from "could not
    run / could not be trusted" (FAILED) and "not applicable" (SKIPPED). A bare
    list of violations cannot express that difference, which let a broken tool
    masquerade as clean code.
    """
    rule_name: str
    status: RuleStatus
    violations: list[Violation] = field(default_factory=list)
    message: str | None = None   # failure / skip reason, surfaced to the user
