"""Check Kotlin function metrics with lizard's in-process Kotlin reader."""

from pathlib import Path

import lizard

from file_discovery import FileDiscovery
from models import RuleResult, Severity, Violation
from rules.base import BaseRule
from rules.context import RuleContext

METRICS = (
    ("cyclomatic_complexity", "cyclomatic_complexity", "cyclomatic complexity"),
    ("function_length", "nloc", "lines of code"),
    ("parameter_count", "parameter_count", "parameters"),
)


class KotlinComplexityRule(BaseRule):
    """Report configured complexity, length, and parameter thresholds per Kotlin function."""

    rule_name = "kotlin_complexity"

    def check(self, file_path: Path) -> RuleResult:
        """Analyze a Kotlin source file and return its configured function findings."""
        if file_path.suffix.lower() not in FileDiscovery.LANGUAGE_EXTENSIONS["kotlin"]:
            return self._ok([])

        relative_path = self._get_relative_path(file_path)
        try:
            text = file_path.read_text(encoding="utf-8", errors="replace")
            analyzer = lizard.FileAnalyzer(lizard.analyze_file.processors)
            functions = analyzer.analyze_source_code(str(file_path), text).function_list
        except Exception as error:
            return self._failed(f"could not analyze {relative_path}: {error}")

        violations = []
        for function in functions:
            for config_key, attribute, label in METRICS:
                thresholds = self.config.get(config_key)
                if thresholds is None:
                    continue

                limits = self._get_threshold_for_file(file_path, thresholds)
                value = getattr(function, attribute)
                error_limit = limits.get("error")
                warning_limit = limits.get("warning")
                if error_limit is not None and value >= error_limit:
                    severity, limit = Severity.ERROR, error_limit
                elif warning_limit is not None and value >= warning_limit:
                    severity, limit = Severity.WARNING, warning_limit
                else:
                    continue

                violations.append(Violation(
                    file_path=relative_path,
                    rule_name=self.rule_name,
                    severity=severity,
                    message=f"{function.name}: {label} {value} (limit: {limit:g})",
                    line=function.start_line,
                ))

        return self._ok(self._filter_violations_by_log_level(violations))
