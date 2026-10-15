"""Typed output models for the dependency audit command."""

from dataclasses import asdict, dataclass
from enum import Enum


class Ecosystem(str, Enum):
    PYTHON = "python"
    PHP = "php"
    DART = "dart"


@dataclass(frozen=True)
class Advisory:
    ecosystem: Ecosystem
    package: str
    installed: str | None
    fixed: str | None
    id: str
    summary: str
    url: str


@dataclass(frozen=True)
class OutdatedPackage:
    ecosystem: Ecosystem
    package: str
    installed: str
    latest: str


@dataclass(frozen=True)
class StackError:
    ecosystem: Ecosystem
    message: str


@dataclass
class AuditReport:
    advisories: list[Advisory]
    outdated: list[OutdatedPackage]
    errors: list[StackError]

    def __init__(self):
        self.advisories = []
        self.outdated = []
        self.errors = []

    def to_dict(self) -> dict[str, list[dict[str, object]]]:
        """Return the stable JSON shape consumed by the watcher."""
        return {
            "advisories": [_json_ready(item) for item in self.advisories],
            "outdated": [_json_ready(item) for item in self.outdated],
            "errors": [_json_ready(item) for item in self.errors],
        }


def _json_ready(value: Advisory | OutdatedPackage | StackError) -> dict[str, object]:
    data = asdict(value)
    data["ecosystem"] = value.ecosystem.value
    return data
