"""Validate shared API contract JSON files and enum definitions."""

import json
from pathlib import Path
from typing import Any

from models import RuleResult, Severity, Violation
from rules.base import BaseRule

ALLOWED_DIRECTIONS = frozenset({"api_to_client", "client_to_api"})


class ContractEnumsRule(BaseRule):
    """Check JSON syntax and the shared contract's ``enums.json`` shape."""

    rule_name = "contract_enums"

    def check(self, file_path: Path) -> RuleResult:
        """Validate one discovered JSON file and return its findings."""
        if file_path.suffix.lower() != ".json":
            return self._ok([])

        relative_path = self._get_relative_path(file_path)
        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError as error:
            violation = self._violation(
                relative_path,
                f"{relative_path}: invalid UTF-8 at byte {error.start}",
            )
            return self._ok([violation])
        except OSError as error:
            return self._failed(f"could not read {relative_path}: {error}")

        try:
            document = json.loads(content)
        except json.JSONDecodeError as error:
            violation = self._violation(
                relative_path,
                f"{relative_path}: invalid JSON at line {error.lineno}, "
                f"column {error.colno}: {error.msg}",
                line=error.lineno,
                column=error.colno,
            )
            return self._ok([violation])

        if file_path.name != "enums.json":
            return self._ok([])

        violations = self._validate_enums(relative_path, document)
        return self._ok(self._filter_violations_by_log_level(violations))

    def _validate_enums(self, relative_path: str, document: Any) -> list[Violation]:
        """Validate the enum map and each named enum definition."""
        if not isinstance(document, dict):
            return [self._violation(
                relative_path,
                f"{relative_path}: enums.json top level must be an object",
            )]

        violations = []
        for enum_name, entry in document.items():
            if not isinstance(entry, dict):
                violations.append(self._enum_violation(
                    relative_path, enum_name, "entry must be an object",
                ))
                continue

            values = entry.get("values")
            if not isinstance(values, list) or not values:
                violations.append(self._enum_violation(
                    relative_path, enum_name, "values must be a non-empty array",
                ))
            elif any(not isinstance(value, str) for value in values):
                violations.append(self._enum_violation(
                    relative_path, enum_name, "values must contain only strings",
                ))
            else:
                if values != sorted(values):
                    violations.append(self._enum_violation(
                        relative_path, enum_name, "values must be sorted",
                    ))
                if len(values) != len(set(values)):
                    violations.append(self._enum_violation(
                        relative_path, enum_name, "values must not contain duplicates",
                    ))

            direction = entry.get("direction")
            if not isinstance(direction, str) or direction not in ALLOWED_DIRECTIONS:
                violations.append(self._enum_violation(
                    relative_path,
                    enum_name,
                    "direction must be api_to_client or client_to_api",
                ))

            description = entry.get("description")
            if not isinstance(description, str) or not description.strip():
                violations.append(self._enum_violation(
                    relative_path, enum_name, "description must be a non-empty string",
                ))

        return violations

    def _enum_violation(self, relative_path: str, enum_name: str, message: str) -> Violation:
        """Build an enum-specific error finding."""
        return self._violation(relative_path, f"{enum_name}: {message}")

    def _violation(
        self,
        relative_path: str,
        message: str,
        *,
        line: int | None = None,
        column: int | None = None,
    ) -> Violation:
        """Build a consistent error finding for this rule."""
        return Violation(
            file_path=relative_path,
            rule_name=self.rule_name,
            severity=Severity.ERROR,
            message=message,
            line=line,
            column=column,
        )
