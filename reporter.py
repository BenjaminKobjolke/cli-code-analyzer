"""
Report generation and formatting
"""

from typing import List, Dict
from collections import defaultdict
from models import Violation, Severity, OutputLevel, LogLevel


class Reporter:
    """Handles report generation in different formats"""

    def __init__(self, violations: List[Violation], file_count: int, output_level: OutputLevel, log_level: LogLevel = LogLevel.ALL):
        self.all_violations = violations
        self.violations = self._filter_violations(violations, log_level)
        self.file_count = file_count
        self.output_level = output_level
        self.log_level = log_level

    def _filter_violations(self, violations: List[Violation], log_level: LogLevel) -> List[Violation]:
        """Filter violations based on log level"""
        if log_level == LogLevel.ERROR:
            return [v for v in violations if v.severity == Severity.ERROR]
        elif log_level == LogLevel.WARNING:
            return [v for v in violations if v.severity == Severity.WARNING]
        else:  # LogLevel.ALL
            return violations

    def report(self) -> bool:
        """
        Generate and print report

        Returns:
            True if errors were found, False otherwise
        """
        if self.output_level == OutputLevel.MINIMAL:
            return self._report_minimal()
        elif self.output_level == OutputLevel.VERBOSE:
            return self._report_verbose()
        else:
            return self._report_normal()

    def _report_minimal(self) -> bool:
        """Generate minimal output format"""
        if not self.violations:
            print("No violations found")
            return False

        # Group violations by file
        file_violations: Dict[str, List[Violation]] = defaultdict(list)
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
                print(f"{file_path} errors:{errors} {details}")
            elif self.log_level == LogLevel.WARNING:
                print(f"{file_path} warnings:{warnings} {details}")
            else:  # LogLevel.ALL
                print(f"{file_path} errors:{errors} warnings:{warnings} {details}")

        # Summary
        total_errors = sum(1 for v in self.violations if v.severity == Severity.ERROR)
        total_warnings = sum(1 for v in self.violations if v.severity == Severity.WARNING)

        if self.log_level == LogLevel.ERROR:
            print(f"Summary: {total_errors} error(s)")
        elif self.log_level == LogLevel.WARNING:
            print(f"Summary: {total_warnings} warning(s)")
        else:  # LogLevel.ALL
            print(f"Summary: {total_errors} error(s), {total_warnings} warning(s)")

        return total_errors > 0

    def _report_normal(self) -> bool:
        """Generate normal output format"""
        if not self.violations:
            print("✓ No violations found!")
            return False

        # Separate errors and warnings
        errors = [v for v in self.violations if v.severity == Severity.ERROR]
        warnings = [v for v in self.violations if v.severity == Severity.WARNING]

        # Print errors
        if errors:
            print(f"ERRORS ({len(errors)}):")
            print("=" * 80)
            for violation in errors:
                print(f"  {violation.file_path}")
                print(f"    {violation.message}")
                print()

        # Print warnings
        if warnings:
            print(f"WARNINGS ({len(warnings)}):")
            print("=" * 80)
            for violation in warnings:
                print(f"  {violation.file_path}")
                print(f"    {violation.message}")
                print()

        # Summary
        print("=" * 80)
        if self.log_level == LogLevel.ERROR:
            print(f"Summary: {len(errors)} error(s)")
        elif self.log_level == LogLevel.WARNING:
            print(f"Summary: {len(warnings)} warning(s)")
        else:  # LogLevel.ALL
            print(f"Summary: {len(errors)} error(s), {len(warnings)} warning(s)")

        return len(errors) > 0

    def _report_verbose(self) -> bool:
        """Generate verbose output format"""
        print(f"Analyzing {self.file_count} file(s)...\n")

        if not self.violations:
            print("✓ No violations found!")
            return False

        # Separate errors and warnings
        errors = [v for v in self.violations if v.severity == Severity.ERROR]
        warnings = [v for v in self.violations if v.severity == Severity.WARNING]

        # Print errors
        if errors:
            print(f"ERRORS ({len(errors)}):")
            print("=" * 80)
            for violation in errors:
                print(f"  {violation.file_path}")
                print(f"    Rule: {violation.rule_name}")
                print(f"    Severity: {violation.severity.value}")
                if violation.line_count:
                    threshold = self._get_threshold(violation)
                    excess = violation.line_count - threshold
                    print(f"    Lines: {violation.line_count} / {threshold} (limit exceeded by {excess})")
                print(f"    Message: {violation.message}")
                print()

        # Print warnings
        if warnings:
            print(f"WARNINGS ({len(warnings)}):")
            print("=" * 80)
            for violation in warnings:
                print(f"  {violation.file_path}")
                print(f"    Rule: {violation.rule_name}")
                print(f"    Severity: {violation.severity.value}")
                if violation.line_count:
                    threshold = self._get_threshold(violation)
                    excess = violation.line_count - threshold
                    print(f"    Lines: {violation.line_count} / {threshold} ({excess} lines over warning threshold)")
                print(f"    Message: {violation.message}")
                print()

        # Summary
        print("=" * 80)
        print(f"Files analyzed: {self.file_count}")
        files_with_violations = len(set(v.file_path for v in self.violations))
        print(f"Files with violations: {files_with_violations}")

        if self.log_level == LogLevel.ERROR:
            print(f"Summary: {len(errors)} error(s)")
        elif self.log_level == LogLevel.WARNING:
            print(f"Summary: {len(warnings)} warning(s)")
        else:  # LogLevel.ALL
            print(f"Summary: {len(errors)} error(s), {len(warnings)} warning(s)")

        return len(errors) > 0

    def _get_threshold(self, violation: Violation) -> int:
        """Extract threshold from violation message"""
        # Parse threshold from message like "File has 523 lines (limit: 500)"
        if "limit:" in violation.message:
            return int(violation.message.split("limit:")[-1].strip().rstrip(")"))
        elif "warning:" in violation.message:
            return int(violation.message.split("warning:")[-1].strip().rstrip(")"))
        return 0
