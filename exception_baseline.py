"""Persist the smallest accepted size for each tracked exception."""

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from models import RuleResult, RuleStatus, Severity, Violation

if TYPE_CHECKING:
    from rules.context import RuleContext

_BASELINE_VERSION = 1
_GROWTH_RULE = "exception_growth"


@dataclass(frozen=True)
class BaselineKey:
    """Identify one exception metric for a file or function."""

    rule: str
    file: str
    metric: str
    function: str | None = None


class ExceptionBaseline:
    """Track accepted values and report increases against their saved values."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._values = self._load()
        self._observed: dict[BaselineKey, int | float] = {}

    def observe(self, key: BaselineKey, value: int | float) -> None:
        """Record this run's value, retaining its maximum if seen more than once."""
        if (isinstance(value, bool) or not isinstance(value, (int, float))
                or (isinstance(value, float) and not math.isfinite(value)) or value < 0):
            raise ValueError("Baseline values must be finite non-negative numbers")
        self._observed[key] = max(value, self._observed.get(key, value))

    def growth_violations(self) -> list[Violation]:
        """Return warnings for observed values above their saved baseline."""
        violations = []
        for key, current in sorted(self._observed.items(), key=lambda item: _key_order(item[0])):
            previous = self._values.get(key)
            if previous is None or current <= previous:
                continue

            target = f" function {key.function!r}" if key.function else ""
            violations.append(
                Violation(
                    file_path=key.file,
                    rule_name=_GROWTH_RULE,
                    severity=Severity.WARNING,
                    message=(
                        f"{key.rule} exception{target} grew from {previous} to {current} "
                        f"for {key.metric}; review the growth and update the baseline if accepted."
                    ),
                    line_count=current,
                    function_name=key.function,
                )
            )
        return violations

    def save(
        self,
        prune_unseen: bool = False,
        *,
        prune_rules: set[str] | None = None,
    ) -> None:
        """Persist new or smaller observations and optionally prune unseen keys."""
        updated = dict(self._values)
        for key, value in self._observed.items():
            previous = updated.get(key)
            if previous is None or value < previous:
                updated[key] = value

        if prune_unseen:
            updated = {key: value for key, value in updated.items() if key in self._observed}
        elif prune_rules:
            updated = {
                key: value
                for key, value in updated.items()
                if key.rule not in prune_rules or key in self._observed
            }

        if updated == self._values:
            return

        document = {
            "version": _BASELINE_VERSION,
            "entries": [
                {
                    "rule": key.rule,
                    "file": key.file,
                    "metric": key.metric,
                    "function": key.function,
                    "value": value,
                }
                for key, value in sorted(updated.items(), key=lambda item: _key_order(item[0]))
            ],
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(document, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        self._values = updated

    def _load(self) -> dict[BaselineKey, int | float]:
        try:
            if not self.path.exists():
                return {}
            document = json.loads(self.path.read_text(encoding="utf-8"))
            return _parse_document(document)
        except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
            raise ValueError(f"Invalid exception baseline at {self.path}: {exc}") from exc


class ExceptionBaselineLifecycle:
    """Own the baseline setup, reporting, and safe pruning for one analysis."""

    def __init__(self, rules_file: str | Path, enabled: bool) -> None:
        self.baseline = ExceptionBaseline(baseline_path_for(rules_file)) if enabled else None

    def growth_violations(self) -> list[Violation]:
        """Return warnings accumulated by rules, or none when tracking is disabled."""
        return self.baseline.growth_violations() if self.baseline is not None else []

    def make_context(self, **context_values) -> "RuleContext":
        """Attach the shared baseline to a rule's run context."""
        from rules.context import RuleContext
        return RuleContext(exception_baseline=self.baseline, **context_values)

    def finish(
        self,
        results: list[RuleResult],
        filter_files: set[str] | None,
        violations: list[Violation],
    ) -> None:
        """Apply file filtering, add growth warnings, and save completed observations."""
        violations.extend(self.growth_violations())
        if filter_files is not None:
            violations[:] = self._filter_violations_by_files(violations, filter_files)
        self.save(results, filter_files is not None)

    @staticmethod
    def _filter_violations_by_files(violations: list[Violation], filter_files: set[str]) -> list[Violation]:
        if not filter_files:
            return []

        filtered = []
        for violation in violations:
            path = violation.file_path.replace('\\', '/')
            for filter_path in filter_files:
                if any((
                    path == filter_path,
                    path.endswith('/' + filter_path),
                    filter_path.endswith('/' + path),
                )):
                    filtered.append(violation)
                    break
        return filtered

    def save(self, results: list[RuleResult], filtered: bool) -> None:
        """Save observations and prune only successfully completed full-run rules."""
        if self.baseline is None:
            return

        prune_rules: set[str] = set()
        if not filtered:
            successful = {r.rule_name for r in results if r.status == RuleStatus.OK}
            unsuccessful = {r.rule_name for r in results if r.status != RuleStatus.OK}
            prune_rules = successful - unsuccessful
        self.baseline.save(prune_rules=prune_rules)


def baseline_path_for(rules_file: str | Path) -> Path:
    """Return the baseline path adjacent to the rules file."""
    return Path(rules_file).with_suffix(".exception_baseline.json")


def _parse_document(document: object) -> dict[BaselineKey, int | float]:
    if not isinstance(document, dict):
        raise ValueError("baseline document must be an object")
    if document.get("version") != _BASELINE_VERSION:
        raise ValueError(f"unsupported baseline version: {document.get('version')!r}")
    entries = document.get("entries")
    if not isinstance(entries, list):
        raise ValueError("baseline entries must be a list")

    values: dict[BaselineKey, int | float] = {}
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ValueError(f"baseline entry {index} must be an object")
        rule = entry.get("rule")
        file = entry.get("file")
        metric = entry.get("metric")
        function = entry.get("function")
        value = entry.get("value")
        if not all(isinstance(part, str) and part for part in (rule, file, metric)):
            raise ValueError(f"baseline entry {index} has an invalid rule, file, or metric")
        if function is not None and not isinstance(function, str):
            raise ValueError(f"baseline entry {index} has an invalid function")
        if (isinstance(value, bool) or not isinstance(value, (int, float))
                or (isinstance(value, float) and not math.isfinite(value)) or value < 0):
            raise ValueError(f"baseline entry {index} has an invalid value")

        key = BaselineKey(rule=rule, file=file, metric=metric, function=function)
        if key in values:
            raise ValueError(f"baseline entry {index} duplicates an earlier key")
        values[key] = value
    return values


def _key_order(key: BaselineKey) -> tuple[str, str, str, str]:
    return key.rule, key.file, key.metric, key.function or ""
