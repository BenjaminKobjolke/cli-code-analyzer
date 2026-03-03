"""
Report generation and formatting
"""

import csv
import json
from collections import defaultdict
from pathlib import Path

from logger import Logger
from models import LogLevel, OutputLevel, Severity, Violation


class Reporter:
    """Handles report generation in different formats"""

    CSV_FILENAME_MAP = {
        'pmd_duplicates': 'duplicate_code.csv',
        'pmd_similar_code': 'similar_code.csv',
        'php_cs_fixer_analyze': 'php_cs_fixer.csv',
    }

    def __init__(self, violations: list[Violation], file_count: int, output_level: OutputLevel, log_level: LogLevel = LogLevel.ALL, output_folder: Path | None = None, max_errors: int | None = None, logger: Logger | None = None):
        self.all_violations = violations
        self.violations = self._filter_violations(violations, log_level)
        self.file_count = file_count
        self.output_level = output_level
        self.log_level = log_level
        self.output_folder = output_folder
        self.max_errors = max_errors
        self.logger = logger or Logger()

    def _filter_violations(self, violations: list[Violation], log_level: LogLevel) -> list[Violation]:
        """Filter violations based on log level"""
        if log_level == LogLevel.ERROR:
            return [v for v in violations if v.severity == Severity.ERROR]
        elif log_level == LogLevel.WARNING:
            return [v for v in violations if v.severity in (Severity.WARNING, Severity.ERROR)]
        else:  # LogLevel.ALL
            return violations

    def _apply_max_errors_filter(self, violations: list[Violation]) -> list[Violation]:
        """Apply max errors limit by sorting violations by priority.

        Sorts by severity (ERROR > WARNING > INFO), then by value (line_count).
        Returns top N violations.
        """
        if not self.max_errors or len(violations) <= self.max_errors:
            return violations

        def violation_sort_key(v: Violation):
            # Priority: ERROR=0, WARNING=1, INFO=2 (lower = higher priority)
            severity_priority = {
                Severity.ERROR: 0,
                Severity.WARNING: 1,
                Severity.INFO: 2
            }
            # Secondary sort: by line_count (higher = worse)
            value = v.line_count if v.line_count else 0
            # Return tuple: (severity_priority, -value)
            # Negative value so higher line counts come first
            return (severity_priority.get(v.severity, 999), -value)

        # Sort by priority and take first N
        sorted_violations = sorted(violations, key=violation_sort_key)
        return sorted_violations[:self.max_errors]

    def report(self) -> bool:
        """
        Generate and print report

        Returns:
            True if errors were found, False otherwise
        """
        # If output folder is specified, write to files instead of console
        if self.output_folder:
            return self._report_to_file()

        # Otherwise, print to console
        if self.output_level == OutputLevel.MINIMAL:
            return self._report_minimal()
        elif self.output_level == OutputLevel.VERBOSE:
            return self._report_verbose()
        else:
            return self._report_normal()

    def report_json(self) -> bool:
        """Output violations as JSON to stdout.

        Always prints to stdout (bypasses quiet mode) so that JSON output
        is available even when --file suppresses other output.

        Returns:
            True if errors were found, False otherwise
        """
        errors = [v for v in self.violations if v.severity == Severity.ERROR]
        warnings = [v for v in self.violations if v.severity == Severity.WARNING]
        infos = [v for v in self.violations if v.severity == Severity.INFO]

        violation_dicts = []
        for v in self.violations:
            d = {
                "file_path": v.file_path,
                "rule_name": v.rule_name,
                "severity": v.severity.value,
                "message": v.message,
            }
            if v.line is not None:
                d["line"] = v.line
            if v.column is not None:
                d["column"] = v.column
            if v.line_count is not None:
                d["line_count"] = v.line_count
            violation_dicts.append(d)

        output = {
            "violations": violation_dicts,
            "summary": {
                "total": len(self.violations),
                "errors": len(errors),
                "warnings": len(warnings),
                "infos": len(infos),
            },
        }

        # Always print JSON to stdout, bypassing quiet mode
        print(json.dumps(output, indent=2))

        # Also write to file if output folder is set
        if self.output_folder:
            self._report_to_file()

        return len(errors) > 0

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
                    if v.severity == Severity.ERROR:
                        rule_details.append(f"maxlines>{v.line_count}")
                    else:
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

        # Separate errors, warnings, and infos
        errors = [v for v in self.violations if v.severity == Severity.ERROR]
        warnings = [v for v in self.violations if v.severity == Severity.WARNING]
        infos = [v for v in self.violations if v.severity == Severity.INFO]

        # Print errors
        if errors:
            self.logger.info(f"ERRORS ({len(errors)}):")
            self.logger.info("=" * 80)
            for violation in errors:
                self.logger.info(f"  {violation.file_path}")
                self.logger.info(f"    {violation.message}")
                self.logger.info()

        # Print warnings
        if warnings:
            self.logger.info(f"WARNINGS ({len(warnings)}):")
            self.logger.info("=" * 80)
            for violation in warnings:
                self.logger.info(f"  {violation.file_path}")
                self.logger.info(f"    {violation.message}")
                self.logger.info()

        # Print infos
        if infos:
            self.logger.info(f"INFO ({len(infos)}):")
            self.logger.info("=" * 80)
            for violation in infos:
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

        # Separate errors, warnings, and infos
        errors = [v for v in self.violations if v.severity == Severity.ERROR]
        warnings = [v for v in self.violations if v.severity == Severity.WARNING]
        infos = [v for v in self.violations if v.severity == Severity.INFO]

        # Print errors
        if errors:
            self.logger.info(f"ERRORS ({len(errors)}):")
            self.logger.info("=" * 80)
            for violation in errors:
                self.logger.info(f"  {violation.file_path}")
                self.logger.info(f"    Rule: {violation.rule_name}")
                self.logger.info(f"    Severity: {violation.severity.value}")
                if violation.line_count:
                    threshold = self._get_threshold(violation)
                    excess = violation.line_count - threshold
                    self.logger.info(f"    Lines: {violation.line_count} / {threshold} (limit exceeded by {excess})")
                self.logger.info(f"    Message: {violation.message}")
                self.logger.info()

        # Print warnings
        if warnings:
            self.logger.info(f"WARNINGS ({len(warnings)}):")
            self.logger.info("=" * 80)
            for violation in warnings:
                self.logger.info(f"  {violation.file_path}")
                self.logger.info(f"    Rule: {violation.rule_name}")
                self.logger.info(f"    Severity: {violation.severity.value}")
                if violation.line_count:
                    threshold = self._get_threshold(violation)
                    excess = violation.line_count - threshold
                    self.logger.info(f"    Lines: {violation.line_count} / {threshold} ({excess} lines over warning threshold)")
                self.logger.info(f"    Message: {violation.message}")
                self.logger.info()

        # Print infos
        if infos:
            self.logger.info(f"INFO ({len(infos)}):")
            self.logger.info("=" * 80)
            for violation in infos:
                self.logger.info(f"  {violation.file_path}")
                self.logger.info(f"    Rule: {violation.rule_name}")
                self.logger.info(f"    Severity: {violation.severity.value}")
                self.logger.info(f"    Message: {violation.message}")
                self.logger.info()

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

    def _get_threshold(self, violation: Violation) -> int:
        """Extract threshold from violation message"""
        # Parse threshold from message like "File has 523 lines (limit: 500)"
        try:
            if "limit:" in violation.message:
                return int(float(violation.message.split("limit:")[-1].strip().rstrip(")")))
            elif "warning:" in violation.message:
                return int(float(violation.message.split("warning:")[-1].strip().rstrip(")")))
        except (ValueError, TypeError):
            pass
        return 0

    def _report_to_file(self) -> bool:
        """Write report to files in output folder.

        Returns:
            True if errors were found, False otherwise
        """
        # Separate violations by rule type
        line_violations = [v for v in self.violations if v.rule_name == 'max_lines_per_file']
        line_violations = self._apply_max_errors_filter(line_violations)

        # Write line count violations to CSV file (if any)
        if line_violations:
            output_file = self.output_folder / 'line_count_report.csv'
            with open(output_file, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)

                # Write header
                writer.writerow(['file_path', 'line_count', 'threshold', 'severity'])

                # Write each violation as a row
                for violation in line_violations:
                    threshold = self._get_threshold(violation)
                    writer.writerow([
                        violation.file_path,
                        violation.line_count,
                        threshold,
                        violation.severity.value
                    ])

            self.logger.info(f"Line count report saved to: {output_file}")
        else:
            self.logger.info("No line count violations found")

        # Write CSVs for all rules (centralized — rules no longer write their own)
        self._write_rule_csvs()

        # Determine if there are errors
        total_errors = sum(1 for v in self.violations if v.severity == Severity.ERROR)
        return total_errors > 0

    def _write_rule_csvs(self):
        """Write CSV files for each rule's violations."""
        by_rule: dict[str, list[Violation]] = defaultdict(list)
        for v in self.violations:
            if v.rule_name != 'max_lines_per_file':
                by_rule[v.rule_name].append(v)

        severity_order = {Severity.ERROR: 0, Severity.WARNING: 1, Severity.INFO: 2}

        for rule_name, violations in by_rule.items():
            filename = self.CSV_FILENAME_MAP.get(rule_name, f'{rule_name}.csv')
            output_file = self.output_folder / filename

            sorted_v = sorted(violations, key=lambda v: severity_order.get(v.severity, 3))
            if self.max_errors and len(sorted_v) > self.max_errors:
                sorted_v = sorted_v[:self.max_errors]

            with open(output_file, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['file_path', 'line', 'column', 'severity', 'message'])
                for v in sorted_v:
                    writer.writerow([v.file_path, v.line or '', v.column or '', v.severity.value, v.message])

            self.logger.info(f"Report saved to: {output_file}")
