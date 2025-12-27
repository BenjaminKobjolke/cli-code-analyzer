"""
Flutter analyze rule for Flutter code analysis
"""

import csv
import re
from pathlib import Path
from typing import Any

import yaml

from models import LogLevel, Severity, Violation
from rules.base import BaseRule
from settings import Settings


class FlutterAnalyzeRule(BaseRule):
    """Rule to analyze Flutter code using flutter analyze"""

    def __init__(self, config: dict, base_path: Path | None = None, output_folder: Path | None = None, log_level: LogLevel = LogLevel.ALL, max_errors: int | None = None, rules_file_path: str | None = None):
        """Initialize Flutter analyze rule.

        Args:
            config: Rule configuration from rules.json
            base_path: Base path for analysis
            output_folder: Optional folder for file output (None = console output)
            log_level: Log level for filtering violations
            max_errors: Optional limit on number of violations to include in CSV
            rules_file_path: Path to the rules.json file
        """
        super().__init__(config, base_path, max_errors, rules_file_path)
        self.output_folder = output_folder
        self.log_level = log_level
        self.settings = Settings()
        self._flutter_executed = False  # Track if flutter analyze has been executed
        self.project_root = None

    def check(self, _file_path: Path) -> list[Violation]:
        """Run flutter analyze on the entire project (only once).

        Note: flutter analyze analyzes entire projects, not individual files.
        This method will execute flutter analyze once on the first file and return empty for subsequent files.

        Args:
            file_path: Path to a file (used to determine base directory)

        Returns:
            List of violations found (only on first execution)
        """
        # Only execute flutter analyze once per analysis run
        if self._flutter_executed:
            return []

        self._flutter_executed = True

        print("\nRunning flutter analyze...")

        # Check if this is a Flutter project
        if not self._is_flutter_project():
            print("Not a Flutter project (no flutter dependency in pubspec.yaml)")
            return []

        # Get flutter path using base utility
        flutter_path = self._get_tool_path('flutter', self.settings.get_flutter_path, self.settings.prompt_and_save_flutter_path)
        if not flutter_path:
            return []

        # Run flutter analyze
        violations = self._run_flutter_analyze(flutter_path)

        return violations

    def _is_flutter_project(self) -> bool:
        """Check if the project is a Flutter project by inspecting pubspec.yaml.

        Returns:
            True if Flutter project, False otherwise
        """
        # Use base utility to find pubspec
        self.project_root = self._find_pubspec()
        if not self.project_root:
            print(f"Warning: pubspec.yaml not found in {self.base_path} or parent")
            return False

        pubspec_path = self.project_root / 'pubspec.yaml'

        # Parse pubspec.yaml and check for flutter dependency
        try:
            with open(pubspec_path, encoding='utf-8') as f:
                pubspec_data = yaml.safe_load(f)

            if not pubspec_data:
                return False

            # Check dependencies section for flutter
            dependencies = pubspec_data.get('dependencies', {})
            if 'flutter' in dependencies:
                return True

            # Also check dev_dependencies
            dev_dependencies = pubspec_data.get('dev_dependencies', {})
            return 'flutter' in dev_dependencies

        except Exception as e:
            print(f"Warning: Could not parse pubspec.yaml: {e}")
            return False

    def _run_flutter_analyze(self, flutter_path: str) -> list[Violation]:
        """Execute flutter analyze and parse results.

        Args:
            flutter_path: Path to flutter executable

        Returns:
            List of violations
        """
        # Build command for text format output
        cmd = [flutter_path, 'analyze']

        # Execute flutter analyze using base utility
        try:
            result = self._run_subprocess(cmd, self.project_root or self.base_path)

            # Combine stdout and stderr
            output = result.stdout if result.stdout.strip() else result.stderr

            # Parse text output
            violations = self._parse_flutter_text_output(output)

            # Apply log level filter to violations
            violations = self._filter_violations_by_log_level(violations)

            # Print summary
            if violations:
                print(f"\nFlutter analyze found {len(violations)} issue(s)")
            else:
                print("\nFlutter analyze: No issues found")

            # Write to CSV file if output folder is specified and violations found
            if self.output_folder and violations:
                output_file = self.output_folder / 'flutter_analyze.csv'
                self._write_csv_output(output_file, violations)

            return violations

        except FileNotFoundError:
            print(f"Error: Flutter executable not found: {flutter_path}")
            print("Please ensure Flutter SDK is installed and configured correctly")
            return []
        except Exception as e:
            print(f"Error running flutter analyze: {e}")
            return []

    def _parse_flutter_text_output(self, output: str) -> list[Violation]:
        """Parse flutter analyze text output into violations.

        The output format is:
        warning - Message - file_path:line:column - code
        info - Message - file_path:line:column - code
        error - Message - file_path:line:column - code

        Some messages can be multi-line with continuation lines indented.

        Args:
            output: Text output from flutter analyze

        Returns:
            List of violations
        """
        violations = []

        if not output or not output.strip():
            return violations

        # Pattern for main violation line: severity - message - path:line:column - code
        # Example: warning - Unused import: 'package:path/path.dart' - lib\screens\file.dart:3:8 - unused_import
        main_pattern = re.compile(
            r'^\s*(warning|info|error)\s+-\s+(.+?)\s+-\s+(.+?):(\d+):(\d+)\s+-\s+(\S+)\s*$',
            re.IGNORECASE
        )

        # Pattern for continuation line (indented message without severity)
        # Example:    info - Additional message part -
        continuation_pattern = re.compile(
            r'^\s+(info|warning|error)\s+-\s+(.+?)\s+-\s*$',
            re.IGNORECASE
        )

        lines = output.split('\n')
        current_violation = None
        current_message_parts = []

        for line in lines:
            # Try to match main violation line
            main_match = main_pattern.match(line)
            if main_match:
                # Save previous violation if exists
                if current_violation:
                    # Join all message parts
                    full_message = ' '.join(current_message_parts)
                    current_violation['message'] = full_message
                    violations.append(self._create_violation(current_violation))

                # Start new violation
                severity_str, message, file_path, line_num, col_num, code = main_match.groups()
                current_violation = {
                    'severity': severity_str,
                    'message': message,
                    'file_path': file_path,
                    'line': int(line_num),
                    'column': int(col_num),
                    'code': code
                }
                current_message_parts = [message.strip()]
                continue

            # Try to match continuation line
            continuation_match = continuation_pattern.match(line)
            if continuation_match and current_violation:
                # Append to current message
                _, message_part = continuation_match.groups()
                current_message_parts.append(message_part.strip())
                continue

            # If we reach here and have a current violation, we might be at the end
            # or encountering a non-matching line

        # Don't forget to save the last violation
        if current_violation:
            full_message = ' '.join(current_message_parts)
            current_violation['message'] = full_message
            violations.append(self._create_violation(current_violation))

        return violations

    def _create_violation(self, data: dict[str, Any]) -> Violation:
        """Create a Violation object from parsed data.

        Args:
            data: Dictionary with parsed violation data

        Returns:
            Violation object
        """
        # Map severity
        severity = self._map_severity(data['severity'])

        # Create relative path
        try:
            file_path = Path(data['file_path'])
            # Try to make it relative to project root or base path
            if self.project_root:
                try:
                    rel_path = str(file_path.resolve().relative_to(self.project_root))
                except ValueError:
                    rel_path = self._get_relative_path(file_path)
            else:
                rel_path = self._get_relative_path(file_path)
        except Exception:
            rel_path = data['file_path']

        # Build detailed message
        detailed_message = f"{data['message']} ({data['code']}) at line {data['line']}, column {data['column']}"

        violation = Violation(
            file_path=rel_path,
            rule_name='flutter_analyze',
            severity=severity,
            message=detailed_message
        )
        return violation

    def _write_csv_output(self, output_file: Path, violations: list[Violation]):
        """Write flutter analyze results to CSV file, filtered by log level.

        Args:
            output_file: Path to CSV output file
            violations: List of violations (already filtered by log level)
        """
        try:
            if not violations:
                return

            # Convert violations to data for sorting and limiting
            violation_data = []
            for violation in violations:
                # Extract line and column from message if possible
                # Message format: "message (code) at line X, column Y"
                line_match = re.search(r'at line (\d+)', violation.message)
                col_match = re.search(r'column (\d+)', violation.message)
                code_match = re.search(r'\(([^)]+)\) at line', violation.message)

                line_num = int(line_match.group(1)) if line_match else 0
                col_num = int(col_match.group(1)) if col_match else 0
                code = code_match.group(1) if code_match else 'unknown'

                # Extract base message (before code)
                base_message = violation.message
                if code_match:
                    base_message = violation.message.split(f'({code})')[0].strip()

                violation_data.append({
                    'file': violation.file_path,
                    'line': line_num,
                    'column': col_num,
                    'severity': violation.severity.name,
                    'code': code,
                    'message': base_message,
                    'severity_order': 0 if violation.severity == Severity.ERROR else (1 if violation.severity == Severity.WARNING else 2)
                })

            # Apply max_errors limit
            if self.max_errors and len(violation_data) > self.max_errors:
                # Sort by severity (ERROR first), then alphabetically
                violation_data.sort(key=lambda x: (x['severity_order'], x['file'], x['line']))
                violation_data = violation_data[:self.max_errors]

            # Write CSV
            with open(output_file, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)

                # Write header
                writer.writerow(['file', 'line', 'column', 'severity', 'code', 'message'])

                # Write data rows
                for data in violation_data:
                    writer.writerow([
                        data['file'],
                        data['line'],
                        data['column'],
                        data['severity'],
                        data['code'],
                        data['message']
                    ])

            print(f"Flutter analyze report saved to: {output_file}")

        except Exception as e:
            print(f"Error writing flutter analyze CSV file: {e}")
