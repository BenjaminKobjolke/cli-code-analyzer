"""Intelephense analyze rule for PHP code analysis using LSP."""

import csv
from pathlib import Path

from models import LogLevel, Severity, Violation
from rules.base import BaseRule


class IntelephenseAnalyzeRule(BaseRule):
    """Rule to analyze PHP code using Intelephense LSP."""

    def __init__(
        self,
        config: dict,
        base_path: Path | None = None,
        output_folder: Path | None = None,
        log_level: LogLevel = LogLevel.ALL,
        max_errors: int | None = None,
        rules_file_path: str | None = None,
    ):
        super().__init__(
            config=config,
            base_path=base_path,
            log_level=log_level,
            max_errors=max_errors,
            rules_file_path=rules_file_path,
        )
        self.output_folder = output_folder
        self._executed = False

    def _map_severity(self, intelephense_severity: str) -> Severity:
        """Map Intelephense severity to cli-code-analyzer Severity.

        Args:
            intelephense_severity: Severity from Intelephense ("error", "warning", "info", "hint")

        Returns:
            Mapped Severity enum value.
        """
        severity_map = {
            "error": Severity.ERROR,
            "warning": Severity.WARNING,
            "info": Severity.INFO,
            "hint": Severity.INFO,  # Map hint to INFO
        }
        return severity_map.get(intelephense_severity.lower(), Severity.WARNING)

    def check(self, _file_path: Path) -> list[Violation]:
        """Run Intelephense check on the entire project (only once)."""
        if self._executed:
            return []

        self._executed = True
        print("\nRunning Intelephense check...")

        try:
            from intelephense_watcher.api import get_diagnostics
        except ImportError as e:
            print(f"Error: Could not import intelephense_watcher: {e}")
            print("Please run: pip install -r requirements.txt")
            return []

        violations = self._run_intelephense_check(get_diagnostics)
        return violations

    def _run_intelephense_check(self, get_diagnostics_func) -> list[Violation]:
        """Execute Intelephense check and parse results.

        Args:
            get_diagnostics_func: The get_diagnostics function from intelephense_watcher.api

        Returns:
            List of Violation objects.
        """
        # Get configuration
        min_severity = self.config.get("min_severity", "warning")
        timeout = self.config.get("timeout", 5.0)
        ignore_unused_underscore = self.config.get("ignore_unused_underscore", True)
        exclude_patterns = self.config.get("exclude_patterns", ["vendor/**", "node_modules/**"])

        try:
            diagnostics = get_diagnostics_func(
                project_path=str(self.base_path),
                min_severity=min_severity,
                ignore_unused_underscore=ignore_unused_underscore,
                ignore_patterns=exclude_patterns,
                timeout=timeout,
            )

            violations = []
            for diag in diagnostics:
                severity = self._map_severity(diag.severity)
                message = f"{diag.message} at line {diag.line}:{diag.column}"

                violation = Violation(
                    file_path=diag.file_path,
                    rule_name="intelephense_analyze",
                    severity=severity,
                    message=message,
                )
                violations.append(violation)

            violations = self._filter_violations_by_log_level(violations)

            if self.max_errors and len(violations) > self.max_errors:
                violations = violations[: self.max_errors]

            if violations:
                print(f"Intelephense found {len(violations)} issue(s)")
            else:
                print("Intelephense: No issues found")

            if self.output_folder and violations:
                output_file = self.output_folder / "intelephense_analyze.csv"
                self._write_csv_output(output_file, diagnostics)

            return violations

        except RuntimeError as e:
            print(f"Error: {e}")
            return []
        except Exception as e:
            print(f"Error running Intelephense check: {e}")
            return []

    def _write_csv_output(self, output_file: Path, diagnostics: list) -> bool:
        """Write Intelephense results to CSV file.

        Args:
            output_file: Path to output CSV file.
            diagnostics: List of Diagnostic objects from intelephense_watcher.

        Returns:
            True if CSV was written successfully, False otherwise.
        """
        if not diagnostics:
            return False

        try:
            # Apply max_errors limit
            limited_diagnostics = diagnostics
            if self.max_errors and len(limited_diagnostics) > self.max_errors:
                limited_diagnostics = limited_diagnostics[: self.max_errors]

            with open(output_file, "w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["file", "line", "column", "severity", "message"])

                for diag in limited_diagnostics:
                    writer.writerow(
                        [diag.file_path, diag.line, diag.column, diag.severity, diag.message]
                    )

            print(f"Intelephense report saved to: {output_file}")
            return True

        except Exception as e:
            print(f"Error writing Intelephense CSV file: {e}")
            return False
