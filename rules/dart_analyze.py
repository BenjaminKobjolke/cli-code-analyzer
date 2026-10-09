"""
Dart analyze rule for Flutter/Dart code analysis
"""

import csv
from pathlib import Path

from models import LogLevel, RuleResult, Severity, Violation
from rules.base import ProjectWideRule


class DartAnalyzeRule(ProjectWideRule):
    """Rule to analyze Dart/Flutter code using dart analyze"""

    rule_name = 'dart_analyze'

    def _run(self, _file_path: Path) -> RuleResult:
        self.logger.info("\nRunning dart analyze...")

        # Get dart command using FVM-aware utility
        dart_cmd = self._get_dart_command()
        if not dart_cmd:
            return self._failed("Dart executable not found")

        # Run dart analyze
        return self._run_dart_analyze(dart_cmd)

    def _run_dart_analyze(self, dart_cmd: list[str]) -> RuleResult:
        """Execute dart analyze and parse results.

        Args:
            dart_cmd: Dart command as list (e.g., ['dart'] or ['fvm', 'dart'])

        Returns:
            RuleResult
        """
        # Build command with JSON format
        cmd = [*dart_cmd, 'analyze', '--fatal-infos', '--format=json']

        # Scope to changed files when filtering; cwd stays base_path for package context.
        try:
            commands = self._scoped_commands(cmd, ('.dart',))
            if commands is None:
                return self._ok([])
            documents = self._run_json('dart analyze', commands, self.base_path)
            diagnostics = []
            for data in documents:
                if not isinstance(data, dict) or not isinstance(data.get('diagnostics'), list):
                    raise TypeError('dart analyze returned unexpected JSON structure')
                diagnostics.extend(data['diagnostics'])
            violations = self._parse_dart_json(diagnostics)

            # Apply log level filter to violations
            violations = self._filter_violations_by_log_level(violations)

            # Print summary
            if violations:
                self.logger.info(f"Dart analyze found {len(violations)} issue(s)")
            else:
                self.logger.info("Dart analyze: No issues found")

            # Write to CSV file if output folder is specified and violations found
            if self.output_folder and violations:
                output_file = self.output_folder / 'dart_analyze.csv'
                self._write_csv_output(output_file, diagnostics)

            return self._ok(violations)

        except FileNotFoundError:
            self.logger.error(f"Error: Dart executable not found: {dart_cmd}")
            self.logger.error("Please ensure Dart/Flutter SDK is installed and configured correctly")
            return self._failed(f"Dart executable not found: {dart_cmd}")
        except Exception as e:
            self.logger.error(f"Error running dart analyze: {e}")
            return self._failed(f"error running dart analyze: {e}")

    def _parse_dart_json(self, diagnostics: list[dict]) -> list[Violation]:
        """Parse dart analyze JSON output into violations.

        Args:
            diagnostics: Parsed diagnostic entries from dart analyze

        Returns:
            List of violations
        """
        violations = []

        for diagnostic in diagnostics:
            # Extract fields from JSON
            code = diagnostic.get('code', 'unknown')
            severity_str = diagnostic.get('severity', 'WARNING')
            problem_message = diagnostic.get('problemMessage', '')
            correction_message = diagnostic.get('correctionMessage', '')

            location = diagnostic.get('location', {})
            file_path = location.get('file', 'unknown')
            range_info = location.get('range', {})
            start = range_info.get('start', {})
            line_num = start.get('line', 0)
            col_num = start.get('column', 0)

            # Map severity
            severity = self._map_severity(severity_str)

            # Create relative path
            try:
                rel_path = self._get_relative_path(Path(file_path))
            except Exception:
                rel_path = file_path

            # Build detailed message
            message_parts = [problem_message]
            if correction_message:
                message_parts.append(correction_message)
            full_message = ' '.join(message_parts)

            detailed_message = f"{full_message} ({code}) at line {line_num}, column {col_num}"

            violation = Violation(
                file_path=rel_path,
                rule_name='dart_analyze',
                severity=severity,
                message=detailed_message,
                line=line_num,
                column=col_num
            )
            violations.append(violation)

        return violations

    def _write_csv_output(self, output_file: Path, diagnostics: list[dict]):
        """Write dart analyze results to CSV file, filtered by log level.

        Args:
            output_file: Path to CSV output file
            diagnostics: Parsed diagnostic entries from dart analyze
        """
        try:
            if not diagnostics:
                return

            # Filter diagnostics based on log level
            filtered_diagnostics = []
            for diagnostic in diagnostics:
                severity_str = diagnostic.get('severity', 'WARNING')
                severity = self._map_severity(severity_str)

                # Apply log level filter
                if (self.log_level == LogLevel.ERROR and severity != Severity.ERROR) or \
                   (self.log_level == LogLevel.WARNING and severity not in (Severity.ERROR, Severity.WARNING)):
                    continue

                filtered_diagnostics.append(diagnostic)

            # Apply max_errors limit
            if self.max_errors and len(filtered_diagnostics) > self.max_errors:
                # Sort by severity (ERROR first), then alphabetically
                def diagnostic_sort_key(d):
                    severity_order = {'ERROR': 0, 'WARNING': 1, 'INFO': 2}
                    return (severity_order.get(d.get('severity', 'WARNING'), 3),)

                filtered_diagnostics.sort(key=diagnostic_sort_key)
                filtered_diagnostics = filtered_diagnostics[:self.max_errors]

            # Don't create CSV if no violations match the filter
            if not filtered_diagnostics:
                return

            # Write CSV
            with open(output_file, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)

                # Write header
                writer.writerow(['file', 'line', 'column', 'severity', 'code', 'message'])

                # Write data rows
                for diagnostic in filtered_diagnostics:
                    location = diagnostic.get('location', {})
                    file_path = location.get('file', 'unknown')

                    # Get relative path
                    try:
                        rel_path = self._get_relative_path(Path(file_path))
                    except Exception:
                        rel_path = file_path

                    range_info = location.get('range', {})
                    start = range_info.get('start', {})
                    line_num = start.get('line', 0)
                    col_num = start.get('column', 0)

                    severity = diagnostic.get('severity', 'WARNING')
                    code = diagnostic.get('code', 'unknown')

                    # Combine problem and correction messages
                    problem_msg = diagnostic.get('problemMessage', '')
                    correction_msg = diagnostic.get('correctionMessage', '')
                    message_parts = [problem_msg]
                    if correction_msg:
                        message_parts.append(correction_msg)
                    full_message = ' '.join(message_parts)

                    writer.writerow([rel_path, line_num, col_num, severity, code, full_message])

            self.logger.info(f"Dart analyze report saved to: {output_file}")

        except Exception as e:
            self.logger.error(f"Error writing dart analyze CSV file: {e}")
