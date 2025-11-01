"""
Data models for the code analyzer
"""

from dataclasses import dataclass
from enum import Enum


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
