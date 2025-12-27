"""
Ruff analyze rule for Python code analysis
"""

import csv
import json
from pathlib import Path

from models import LogLevel, Severity, Violation
from rules.base import BaseRule
from settings import Settings


class RuffAnalyzeRule(BaseRule):
    """Rule to analyze Python code using Ruff linter"""

    def __init__(self, config: dict, base_path: Path | None = None, output_folder: Path | None = None, log_level: LogLevel = LogLevel.ALL, max_errors: int | None = None, rules_file_path: str | None = None):
        """Initialize Ruff analyze rule.

        Args:
            config: Rule configuration from rules.json
            base_path: Base path for analysis
            output_folder: Optional folder for file output (None = console output)
            log_level: Log level for filtering violations
            max_errors: Optional limit on number of violations to include in CSV
            rules_file_path: Path to the rules.json file
        """
        super().__init__(config=config, base_path=base_path, log_level=log_level, max_errors=max_errors, rules_file_path=rules_file_path)
        self.output_folder = output_folder
        self.log_level = log_level
        self.settings = Settings()
        self._ruff_executed = False  # Track if ruff has been executed

    def check(self, _file_path: Path) -> list[Violation]:
        """Run ruff check on the entire project (only once).

        Note: ruff analyzes entire projects, not individual files.
        This method will execute ruff once on the first file and return empty for subsequent files.

        Args:
            file_path: Path to a file (used to determine base directory)

        Returns:
            List of violations found (only on first execution)
        """
        # Only execute ruff once per analysis run
        if self._ruff_executed:
            return []

        self._ruff_executed = True

        print("\nRunning ruff check...")

        # Get ruff path using base utility
        ruff_path = self._get_tool_path('ruff', self.settings.get_ruff_path, self.settings.prompt_and_save_ruff_path)
        if not ruff_path:
            return []

        # Run ruff check
        violations = self._run_ruff_check(ruff_path)

        return violations

    def _run_ruff_check(self, ruff_path: str) -> list[Violation]:
        """Execute ruff check and parse results.

        Args:
            ruff_path: Path to ruff executable

        Returns:
            List of violations
        """
        # Build command with JSON format
        cmd = [ruff_path, 'check', '--output-format', 'json']

        # Add select rules if configured
        if self.config.get('select'):
            cmd.extend(['--select', ','.join(self.config['select'])])

        # Add ignore rules if configured
        if self.config.get('ignore'):
            cmd.extend(['--ignore', ','.join(self.config['ignore'])])

        # Add exclude patterns
        if self.config.get('exclude_patterns'):
            for pattern in self.config['exclude_patterns']:
                cmd.extend(['--exclude', pattern])

        # Add base path to analyze
        cmd.append(str(self.base_path))

        # Execute ruff using base utility
        try:
            result = self._run_subprocess(cmd, self.base_path)

            # Ruff outputs JSON to stdout
            output = result.stdout

            # Parse JSON output
            violations = self._parse_ruff_json(output)

            # Apply log level filter to violations
            violations = self._filter_violations_by_log_level(violations)

            # Apply max_errors limit to returned violations
            if self.max_errors and len(violations) > self.max_errors:
                violations = violations[:self.max_errors]

            # Print summary
            if violations:
                print(f"\nRuff found {len(violations)} issue(s)")
            else:
                print("\nRuff: No issues found")

            # Write to CSV file if output folder is specified and violations found
            if self.output_folder and violations:
                output_file = self.output_folder / 'ruff_analyze.csv'
                self._write_csv_output(output_file, output)

            return violations

        except FileNotFoundError:
            print(f"Error: Ruff executable not found: {ruff_path}")
            print("Please ensure Ruff is installed: pip install ruff")
            return []
        except Exception as e:
            print(f"Error running ruff check: {e}")
            return []

    def _map_ruff_severity(self, code: str) -> Severity:
        """Map Ruff rule code to severity.

        Args:
            code: Ruff rule code (e.g., 'E501', 'F401', 'W291')

        Returns:
            Severity enum value
        """
        prefix = code[0] if code else ''
        if prefix == 'E':  # pycodestyle errors
            return Severity.ERROR
        elif prefix in ('F', 'W'):  # Pyflakes, warnings
            return Severity.WARNING
        else:  # All others (B, C, I, N, etc.)
            return Severity.INFO

    def _parse_ruff_json(self, output: str) -> list[Violation]:
        """Parse ruff check JSON output into violations.

        Ruff JSON format:
        [
            {
                "code": "F401",
                "filename": "path/to/file.py",
                "location": {"column": 8, "row": 4},
                "message": "`shutil` imported but unused",
                "url": "https://docs.astral.sh/ruff/rules/..."
            },
            ...
        ]

        Args:
            output: JSON output from ruff check

        Returns:
            List of violations
        """
        violations = []

        if not output or not output.strip():
            return violations

        try:
            data = json.loads(output)

            # Ruff returns a list of diagnostics directly
            for diagnostic in data:
                # Extract fields from JSON
                code = diagnostic.get('code', 'unknown')
                message = diagnostic.get('message', '')
                file_path = diagnostic.get('filename', 'unknown')

                location = diagnostic.get('location', {})
                line_num = location.get('row', 0)
                col_num = location.get('column', 0)

                # Map severity based on rule code
                severity = self._map_ruff_severity(code)

                # Create relative path
                try:
                    rel_path = self._get_relative_path(Path(file_path))
                except Exception:
                    rel_path = file_path

                # Build detailed message
                detailed_message = f"{message} ({code}) at line {line_num}, column {col_num}"

                violation = Violation(
                    file_path=rel_path,
                    rule_name='ruff_analyze',
                    severity=severity,
                    message=detailed_message
                )
                violations.append(violation)

        except json.JSONDecodeError as e:
            print(f"Error parsing ruff JSON output: {e}")
            print(f"Output was: {output[:200]}...")  # Print first 200 chars for debugging
        except Exception as e:
            print(f"Error processing ruff results: {e}")

        return violations

    def _write_csv_output(self, output_file: Path, json_content: str):
        """Write ruff results to CSV file, filtered by log level.

        Args:
            output_file: Path to CSV output file
            json_content: JSON content from ruff check
        """
        try:
            data = json.loads(json_content)

            if not data:
                return

            # Filter diagnostics based on log level
            filtered_diagnostics = []
            for diagnostic in data:
                code = diagnostic.get('code', '')
                severity = self._map_ruff_severity(code)

                # Apply log level filter
                if (self.log_level == LogLevel.ERROR and severity != Severity.ERROR) or \
                   (self.log_level == LogLevel.WARNING and severity not in (Severity.ERROR, Severity.WARNING)):
                    continue

                filtered_diagnostics.append(diagnostic)

            # Apply max_errors limit
            if self.max_errors and len(filtered_diagnostics) > self.max_errors:
                # Sort by severity (ERROR first), then alphabetically
                def diagnostic_sort_key(d):
                    code = d.get('code', '')
                    severity = self._map_ruff_severity(code)
                    severity_order = {Severity.ERROR: 0, Severity.WARNING: 1, Severity.INFO: 2}
                    return (severity_order.get(severity, 3),)

                filtered_diagnostics.sort(key=diagnostic_sort_key)
                filtered_diagnostics = filtered_diagnostics[:self.max_errors]

            # Don't create CSV if no violations match the filter
            if not filtered_diagnostics:
                return

            # Write CSV
            with open(output_file, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)

                # Write header
                writer.writerow(['file', 'line', 'column', 'severity', 'code', 'message', 'url'])

                # Write data rows
                for diagnostic in filtered_diagnostics:
                    file_path = diagnostic.get('filename', 'unknown')

                    # Get relative path
                    try:
                        rel_path = self._get_relative_path(Path(file_path))
                    except Exception:
                        rel_path = file_path

                    location = diagnostic.get('location', {})
                    line_num = location.get('row', 0)
                    col_num = location.get('column', 0)

                    code = diagnostic.get('code', 'unknown')
                    severity = self._map_ruff_severity(code)
                    message = diagnostic.get('message', '')
                    url = diagnostic.get('url', '')

                    writer.writerow([rel_path, line_num, col_num, severity.value, code, message, url])

            print(f"Ruff report saved to: {output_file}")

        except json.JSONDecodeError as e:
            print(f"Error parsing JSON for CSV output: {e}")
        except Exception as e:
            print(f"Error writing ruff CSV file: {e}")
