"""
Dart analyze rule for Flutter/Dart code analysis
"""

import subprocess
import json
import csv
import shutil
import platform
from pathlib import Path
from typing import List, Optional, Dict, Any
from rules.base import BaseRule
from models import Violation, Severity, LogLevel
from settings import Settings


class DartAnalyzeRule(BaseRule):
    """Rule to analyze Dart/Flutter code using dart analyze"""

    def __init__(self, config: dict, base_path: Path = None, output_folder: Optional[Path] = None, log_level: LogLevel = LogLevel.ALL):
        """Initialize Dart analyze rule.

        Args:
            config: Rule configuration from rules.json
            base_path: Base path for analysis
            output_folder: Optional folder for file output (None = console output)
            log_level: Log level for filtering violations
        """
        super().__init__(config, base_path)
        self.output_folder = output_folder
        self.log_level = log_level
        self.settings = Settings()
        self._dart_executed = False  # Track if dart analyze has been executed

    def check(self, file_path: Path) -> List[Violation]:
        """Run dart analyze on the entire project (only once).

        Note: dart analyze analyzes entire projects, not individual files.
        This method will execute dart analyze once on the first file and return empty for subsequent files.

        Args:
            file_path: Path to a file (used to determine base directory)

        Returns:
            List of violations found (only on first execution)
        """
        # Only execute dart analyze once per analysis run
        if self._dart_executed:
            return []

        self._dart_executed = True

        # Get dart path
        dart_path = self._get_or_prompt_dart_path()
        if not dart_path:
            return []

        # Run dart analyze
        violations = self._run_dart_analyze(dart_path)

        return violations

    def _get_or_prompt_dart_path(self) -> Optional[str]:
        """Get dart path from settings or PATH, or prompt user.

        Returns:
            Path to dart executable or None if failed
        """
        # First check if dart is in PATH
        dart_in_path = shutil.which('dart')
        if dart_in_path:
            # Return the full path found by shutil.which for better compatibility
            return dart_in_path

        # Check settings
        dart_path = self.settings.get_dart_path()

        if not dart_path:
            # Prompt user to provide path
            dart_path = self.settings.prompt_and_save_dart_path()
            if not dart_path:
                return None

        # Validate path exists
        if not Path(dart_path).exists():
            print(f"Error: Dart executable not found at: {dart_path}")
            print("Please update the path in settings.ini or delete settings.ini to reconfigure")
            return None

        return dart_path

    def _run_dart_analyze(self, dart_path: str) -> List[Violation]:
        """Execute dart analyze and parse results.

        Args:
            dart_path: Path to dart executable

        Returns:
            List of violations
        """
        # Build command with JSON format
        cmd = [dart_path, 'analyze', '--fatal-infos', '--format=json']

        # On Windows, use shell=True for better PATH resolution
        use_shell = platform.system() == 'Windows'

        # Execute dart analyze
        try:
            result = subprocess.run(
                cmd,
                cwd=self.base_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
                shell=use_shell
            )

            # Combine stdout and stderr (dart analyze may output to either)
            output = result.stdout if result.stdout.strip() else result.stderr

            # Parse JSON output
            violations = self._parse_dart_json(output)

            # Apply log level filter to violations
            violations = self._filter_violations_by_log_level(violations)

            # Print summary
            if violations:
                print(f"\nDart analyze found {len(violations)} issue(s)")
            else:
                print("\nDart analyze: No issues found")

            # Write to CSV file if output folder is specified and violations found
            if self.output_folder and violations:
                output_file = self.output_folder / 'dart_analyze.csv'
                self._write_csv_output(output_file, output)

            return violations

        except FileNotFoundError:
            print(f"Error: Dart executable not found: {dart_path}")
            print("Please ensure Dart/Flutter SDK is installed and configured correctly")
            return []
        except Exception as e:
            print(f"Error running dart analyze: {e}")
            return []

    def _parse_dart_json(self, output: str) -> List[Violation]:
        """Parse dart analyze JSON output into violations.

        Args:
            output: JSON output from dart analyze

        Returns:
            List of violations
        """
        violations = []

        if not output or not output.strip():
            return violations

        try:
            data = json.loads(output)

            # Get diagnostics array
            diagnostics = data.get('diagnostics', [])

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
                except:
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
                    message=detailed_message
                )
                violations.append(violation)

        except json.JSONDecodeError as e:
            print(f"Error parsing dart analyze JSON output: {e}")
            print(f"Output was: {output[:200]}...")  # Print first 200 chars for debugging
        except Exception as e:
            print(f"Error processing dart analyze results: {e}")

        return violations

    def _map_severity(self, severity_str: str) -> Severity:
        """Map dart analyze severity to our Severity enum.

        Args:
            severity_str: Severity string from dart analyze (INFO/WARNING/ERROR)

        Returns:
            Mapped Severity enum value
        """
        severity_map = {
            'INFO': Severity.INFO,
            'WARNING': Severity.WARNING,
            'ERROR': Severity.ERROR,
        }
        return severity_map.get(severity_str.upper(), Severity.WARNING)

    def _filter_violations_by_log_level(self, violations: List[Violation]) -> List[Violation]:
        """Filter violations based on log level.

        Args:
            violations: List of all violations

        Returns:
            Filtered list of violations based on log level
        """
        if self.log_level == LogLevel.ALL:
            return violations

        filtered = []
        for violation in violations:
            if self.log_level == LogLevel.ERROR and violation.severity != Severity.ERROR:
                continue
            elif self.log_level == LogLevel.WARNING and violation.severity not in (Severity.ERROR, Severity.WARNING):
                continue
            filtered.append(violation)

        return filtered

    def _write_csv_output(self, output_file: Path, json_content: str):
        """Write dart analyze results to CSV file, filtered by log level.

        Args:
            output_file: Path to CSV output file
            json_content: JSON content from dart analyze
        """
        try:
            data = json.loads(json_content)
            diagnostics = data.get('diagnostics', [])

            if not diagnostics:
                return

            # Filter diagnostics based on log level
            filtered_diagnostics = []
            for diagnostic in diagnostics:
                severity_str = diagnostic.get('severity', 'WARNING')
                severity = self._map_severity(severity_str)

                # Apply log level filter
                if self.log_level == LogLevel.ERROR and severity != Severity.ERROR:
                    continue
                elif self.log_level == LogLevel.WARNING and severity not in (Severity.ERROR, Severity.WARNING):
                    continue

                filtered_diagnostics.append(diagnostic)

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
                    except:
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

            print(f"Dart analyze report saved to: {output_file}")

        except json.JSONDecodeError as e:
            print(f"Error parsing JSON for CSV output: {e}")
        except Exception as e:
            print(f"Error writing dart analyze CSV file: {e}")
