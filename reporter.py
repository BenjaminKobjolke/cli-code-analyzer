"""
Report generation and formatting (console output).

CSV file writing and JSON building live in `report_files.py`.
"""

import json
from collections import defaultdict

from logger import Logger
from models import LogLevel, OutputLevel, Severity, Violation
from report_config import ReportConfig
from report_files import build_json, parse_threshold, write_csv_reports


class Reporter:
    """Handles report generation in different formats"""

    def __init__(self, config: ReportConfig):
        self.all_violations = config.violations
        self.violations = self._filter_violations(config.violations, config.log_level)
        self.file_count = config.file_count
        self.output_level = config.output_level
        self.log_level = config.log_level
        self.output_folder = config.output_folder
        self.max_errors = config.max_errors
        self.logger = config.logger or Logger()
        self.failures = config.failures or []

    def _filter_violations(self, violations: list[Violation], log_level: LogLevel) -> list[Violation]:
        """Filter violations based on log level"""
        if log_level == LogLevel.ERROR:
            return [v for v in violations if v.severity == Severity.ERROR]
        elif log_level == LogLevel.WARNING:
            return [v for v in violations if v.severity in (Severity.WARNING, Severity.ERROR)]
        else:  # LogLevel.ALL
            return violations

    def report(self) -> bool:
        """
        Generate and print report

        Returns:
            True if errors were found, False otherwise
        """
        # Surface tool failures first — an unrunnable/untrusted tool is a hard
        # error regardless of how many violations were (or weren't) collected.
        self._report_failures()

        # If output folder is specified, write to files instead of console
        if self.output_folder:
            base = write_csv_reports(self.violations, self.output_folder, self.max_errors, self.logger)
        elif self.output_level == OutputLevel.MINIMAL:
            base = self._report_minimal()
        elif self.output_level == OutputLevel.VERBOSE:
            base = self._report_verbose()
        else:
            base = self._report_normal()

        return base or bool(self.failures)

    def _report_failures(self) -> None:
        """Print a dedicated section listing rules whose tool failed to run."""
        if not self.failures:
            return
        self.logger.error(f"\nTool execution failures ({len(self.failures)}):")
        self.logger.error("=" * 80)
        for f in self.failures:
            self.logger.error(f"  {f.rule_name}: {f.message or 'tool failed to run'}")
        self.logger.error("")

    def report_json(self) -> bool:
        """Output violations as JSON to stdout.

        Always prints to stdout (bypasses quiet mode) so that JSON output
        is available even when --file suppresses other output.

        Returns:
            True if errors were found, False otherwise
        """
        output = build_json(self.violations, self.failures)

        # Always print JSON to stdout, bypassing quiet mode
        print(json.dumps(output, indent=2))

        # Also write to file if output folder is set
        if self.output_folder:
            write_csv_reports(self.violations, self.output_folder, self.max_errors, self.logger)

        return output["summary"]["errors"] > 0 or bool(self.failures)

    def _report_minimal(self) -> bool:
        """Generate minimal output format"""
        if not self.violations:
            self.logger.info("No violations found")
            return False

        # Group violations by file
        file_violations: dict[str, list[Violation]] = defaultdict(list)
        for violation in self.violations:
            file_violations[violation.file_path].append(violation)

        # Print each file with its violation counts
        for file_path, violations in sorted(file_violations.items()):
            errors = sum(1 for v in violations if v.severity == Severity.ERROR)
            warnings = sum(1 for v in violations if v.severity == Severity.WARNING)

            # Get the max lines violation details
            rule_details = []
            for v in violations:
                if v.rule_name == 'max_lines_per_file':
                    rule_details.append(f"maxlines>{v.line_count}")

            details = " ".join(rule_details) if rule_details else ""

            # Build output based on log level
            if self.log_level == LogLevel.ERROR:
                self.logger.info(f"{file_path} errors:{errors} {details}")
            elif self.log_level == LogLevel.WARNING:
                self.logger.info(f"{file_path} warnings:{warnings} {details}")
            else:  # LogLevel.ALL
                self.logger.info(f"{file_path} errors:{errors} warnings:{warnings} {details}")

        # Summary
        total_errors = sum(1 for v in self.violations if v.severity == Severity.ERROR)
        total_warnings = sum(1 for v in self.violations if v.severity == Severity.WARNING)

        if self.log_level == LogLevel.ERROR:
            self.logger.info(f"Summary: {total_errors} error(s)")
        elif self.log_level == LogLevel.WARNING:
            self.logger.info(f"Summary: {total_warnings} warning(s)")
        else:  # LogLevel.ALL
            self.logger.info(f"Summary: {total_errors} error(s), {total_warnings} warning(s)")

        return total_errors > 0

    def _report_normal(self) -> bool:
        """Generate normal output format"""
        if not self.violations:
            self.logger.info("No violations found!")
            return False

        errors = [v for v in self.violations if v.severity == Severity.ERROR]
        warnings = [v for v in self.violations if v.severity == Severity.WARNING]
        infos = [v for v in self.violations if v.severity == Severity.INFO]

        for label, group in (("ERRORS", errors), ("WARNINGS", warnings), ("INFO", infos)):
            if not group:
                continue
            self.logger.info(f"{label} ({len(group)}):")
            self.logger.info("=" * 80)
            for violation in group:
                self.logger.info(f"  {violation.file_path}")
                self.logger.info(f"    {violation.message}")
                self.logger.info()

        # Summary
        self.logger.info("=" * 80)
        if self.log_level == LogLevel.ERROR:
            self.logger.info(f"Summary: {len(errors)} error(s)")
        elif self.log_level == LogLevel.WARNING:
            self.logger.info(f"Summary: {len(errors)} error(s), {len(warnings)} warning(s)")
        else:  # LogLevel.ALL
            self.logger.info(f"Summary: {len(errors)} error(s), {len(warnings)} warning(s), {len(infos)} info(s)")

        return len(errors) > 0

    def _report_verbose(self) -> bool:
        """Generate verbose output format"""
        self.logger.info(f"Analyzing {self.file_count} file(s)...\n")

        if not self.violations:
            self.logger.info("No violations found!")
            return False

        errors = [v for v in self.violations if v.severity == Severity.ERROR]
        warnings = [v for v in self.violations if v.severity == Severity.WARNING]
        infos = [v for v in self.violations if v.severity == Severity.INFO]

        self._print_verbose_group("ERRORS", errors, "limit exceeded by {excess}")
        self._print_verbose_group("WARNINGS", warnings, "{excess} lines over warning threshold")
        self._print_verbose_group("INFO", infos, None)

        # Summary
        self.logger.info("=" * 80)
        self.logger.info(f"Files analyzed: {self.file_count}")
        files_with_violations = len({v.file_path for v in self.violations})
        self.logger.info(f"Files with violations: {files_with_violations}")

        if self.log_level == LogLevel.ERROR:
            self.logger.info(f"Summary: {len(errors)} error(s)")
        elif self.log_level == LogLevel.WARNING:
            self.logger.info(f"Summary: {len(errors)} error(s), {len(warnings)} warning(s)")
        else:  # LogLevel.ALL
            self.logger.info(f"Summary: {len(errors)} error(s), {len(warnings)} warning(s), {len(infos)} info(s)")

        return len(errors) > 0

    def _print_verbose_group(self, label: str, group: list[Violation], excess_template: str | None) -> None:
        """Print one severity group in verbose form."""
        if not group:
            return
        self.logger.info(f"{label} ({len(group)}):")
        self.logger.info("=" * 80)
        for violation in group:
            self.logger.info(f"  {violation.file_path}")
            self.logger.info(f"    Rule: {violation.rule_name}")
            self.logger.info(f"    Severity: {violation.severity.value}")
            if excess_template and violation.line_count:
                threshold = parse_threshold(violation.message)
                excess = violation.line_count - threshold
                detail = excess_template.format(excess=excess)
                self.logger.info(f"    Lines: {violation.line_count} / {threshold} ({detail})")
            self.logger.info(f"    Message: {violation.message}")
            self.logger.info()
