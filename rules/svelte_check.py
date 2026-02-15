"""
Svelte check rule for TypeScript/Svelte type checking
"""

import csv
import re
from pathlib import Path

from models import LogLevel, Severity, Violation
from rules.base import BaseRule
from settings import Settings


class SvelteCheckRule(BaseRule):
    """Rule to analyze Svelte/TypeScript code using svelte-check"""

    def __init__(self, config: dict, base_path: Path | None = None, output_folder: Path | None = None, log_level: LogLevel = LogLevel.ALL, max_errors: int | None = None, rules_file_path: str | None = None):
        super().__init__(config=config, base_path=base_path, log_level=log_level, max_errors=max_errors, rules_file_path=rules_file_path)
        self.output_folder = output_folder
        self.log_level = log_level
        self.settings = Settings()
        self._svelte_check_executed = False

    def check(self, _file_path: Path) -> list[Violation]:
        """Run svelte-check on the entire project (only once).

        Args:
            _file_path: Path to a file (unused, svelte-check runs project-wide)

        Returns:
            List of violations found (only on first execution)
        """
        if self._svelte_check_executed:
            return []

        self._svelte_check_executed = True

        print("Running svelte-check...")

        svelte_check_path = self._get_tool_path('svelte-check', self.settings.get_svelte_check_path, self.settings.prompt_and_save_svelte_check_path)
        if not svelte_check_path:
            return []

        violations = self._run_svelte_check(svelte_check_path)

        return violations

    def _run_svelte_check(self, svelte_check_path: str) -> list[Violation]:
        """Execute svelte-check and parse results.

        Args:
            svelte_check_path: Path to svelte-check executable

        Returns:
            List of violations
        """
        tsconfig = self.config.get('tsconfig', './tsconfig.json')

        cmd = [svelte_check_path, '--output', 'machine', '--tsconfig', tsconfig]

        try:
            result = self._run_subprocess(cmd, self.base_path)

            output = result.stdout if result.stdout.strip() else result.stderr

            violations = self._parse_machine_output(output)

            violations = self._filter_violations_by_log_level(violations)

            if self.max_errors and len(violations) > self.max_errors:
                violations = violations[:self.max_errors]

            if violations:
                print(f"svelte-check found {len(violations)} issue(s)")
            else:
                print("svelte-check: No issues found")

            if self.output_folder and violations:
                output_file = self.output_folder / 'svelte_check.csv'
                self._write_csv_output(output_file, violations)

            return violations

        except FileNotFoundError:
            print(f"Error: svelte-check executable not found: {svelte_check_path}")
            print("Please ensure svelte-check is installed: npm install --save-dev svelte-check")
            return []
        except Exception as e:
            print(f"Error running svelte-check: {e}")
            return []

    def _map_severity(self, severity_str: str) -> Severity:
        """Map svelte-check severity string to internal Severity.

        Args:
            severity_str: Severity from svelte-check (Error, Warning, Hint)

        Returns:
            Severity enum value
        """
        severity_lower = severity_str.lower()
        if severity_lower == 'error':
            return Severity.ERROR
        elif severity_lower == 'warning':
            return Severity.WARNING
        else:
            return Severity.INFO

    def _parse_machine_output(self, output: str) -> list[Violation]:
        """Parse svelte-check machine output into violations.

        Machine output format:
        TIMESTAMP SEVERITY "FILE" LINE:COL "MESSAGE"

        Example:
        1234567890 ERROR "src/routes/+page.svelte" 10:5 "Type 'string' is not assignable to type 'number'"

        Args:
            output: Machine-format output from svelte-check

        Returns:
            List of violations
        """
        violations = []

        if not output or not output.strip():
            return violations

        # Pattern: TIMESTAMP SEVERITY "FILE" LINE:COL "MESSAGE"
        # Note: This pattern assumes single-line diagnostic messages, which matches
        # svelte-check's --output machine format in practice. Multi-line messages
        # (containing embedded newlines in quoted strings) would not be captured.
        pattern = re.compile(r'^\d+\s+(ERROR|WARNING|HINT)\s+"([^"]+)"\s+(\d+):(\d+)\s+"(.+)"$')

        for line in output.splitlines():
            line = line.strip()
            if not line:
                continue

            match = pattern.match(line)
            if not match:
                continue

            severity_str = match.group(1)
            file_path = match.group(2)
            line_num = int(match.group(3))
            col_num = int(match.group(4))
            message = match.group(5)

            severity = self._map_severity(severity_str)

            try:
                rel_path = self._get_relative_path(Path(file_path))
            except Exception:
                rel_path = file_path

            detailed_message = f"{message} at line {line_num}, column {col_num}"

            violation = Violation(
                file_path=rel_path,
                rule_name='svelte_check',
                severity=severity,
                message=detailed_message,
                line=line_num,
                column=col_num
            )
            violations.append(violation)

        return violations

    def _write_csv_output(self, output_file: Path, violations: list[Violation]):
        """Write svelte-check results to CSV file.

        Args:
            output_file: Path to CSV output file
            violations: List of violations to write
        """
        try:
            with open(output_file, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['file', 'line', 'column', 'severity', 'message'])

                for v in violations:
                    line_num = v.line if v.line is not None else 0
                    col_num = v.column if v.column is not None else 0
                    # Strip the "at line X, column Y" suffix from the message for CSV
                    msg = re.sub(r' at line \d+, column \d+$', '', v.message)

                    writer.writerow([v.file_path, line_num, col_num, v.severity.value, msg])

            print(f"svelte-check report saved to: {output_file}")

        except Exception as e:
            print(f"Error writing svelte-check CSV file: {e}")
