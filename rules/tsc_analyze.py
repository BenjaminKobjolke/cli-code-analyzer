"""
TypeScript type checking rule using tsc --noEmit
"""

import csv
import re
from itertools import chain
from pathlib import Path

from models import LogLevel, Severity, Violation
from rules.base import BaseRule
from settings import Settings


class TscAnalyzeRule(BaseRule):
    """Rule to analyze TypeScript code using tsc --noEmit"""

    def __init__(self, config: dict, base_path: Path | None = None, output_folder: Path | None = None, log_level: LogLevel = LogLevel.ALL, max_errors: int | None = None, rules_file_path: str | None = None):
        super().__init__(config=config, base_path=base_path, log_level=log_level, max_errors=max_errors, rules_file_path=rules_file_path)
        self.output_folder = output_folder
        self.log_level = log_level
        self.settings = Settings()
        self._tsc_executed = False

    def check(self, _file_path: Path) -> list[Violation]:
        """Run tsc --noEmit on the project (only once).

        Args:
            _file_path: Path to a file (unused, tsc runs project-wide)

        Returns:
            List of violations found (only on first execution)
        """
        if self._tsc_executed:
            return []

        self._tsc_executed = True

        # Skip if no TypeScript files exist in the project
        if self.base_path and not any(chain(self.base_path.rglob('*.ts'), self.base_path.rglob('*.tsx'))):
            print("\nSkipping tsc: no .ts/.tsx files found")
            return []

        print("\nRunning tsc type checking...")

        tsc_path = self._get_tool_path('tsc', self.settings.get_tsc_path, self.settings.prompt_and_save_tsc_path)
        if not tsc_path:
            return []

        violations = self._run_tsc(tsc_path)

        return violations

    def _run_tsc(self, tsc_path: str) -> list[Violation]:
        """Execute tsc --noEmit and parse results.

        Args:
            tsc_path: Path to tsc executable

        Returns:
            List of violations
        """
        cmd = [tsc_path, '--noEmit', '--pretty', 'false']

        tsconfig = self.config.get('tsconfig')
        if tsconfig:
            cmd.extend(['--project', tsconfig])

        try:
            result = self._run_subprocess(cmd, self.base_path)

            output = result.stdout if result.stdout.strip() else result.stderr

            violations = self._parse_tsc_output(output)

            violations = self._filter_violations_by_log_level(violations)

            if self.max_errors and len(violations) > self.max_errors:
                violations = violations[:self.max_errors]

            if violations:
                print(f"tsc found {len(violations)} issue(s)")
            else:
                print("tsc: No issues found")

            if self.output_folder and violations:
                output_file = self.output_folder / 'tsc_analyze.csv'
                self._write_csv_output(output_file, violations)

            return violations

        except FileNotFoundError:
            print(f"Error: tsc executable not found: {tsc_path}")
            print("Please ensure TypeScript is installed: npm install --save-dev typescript")
            return []
        except Exception as e:
            print(f"Error running tsc: {e}")
            return []

    def _parse_tsc_output(self, output: str) -> list[Violation]:
        """Parse tsc output into violations.

        tsc output format (with --pretty false):
        file(line,col): error TS1234: message

        Args:
            output: Output from tsc --noEmit --pretty false

        Returns:
            List of violations
        """
        violations = []

        if not output or not output.strip():
            return violations

        pattern = re.compile(r'^(.+)\((\d+),(\d+)\): (error|warning) (TS\d+): (.+)$')

        for line in output.splitlines():
            line = line.strip()
            if not line:
                continue

            match = pattern.match(line)
            if not match:
                continue

            file_path = match.group(1)
            line_num = int(match.group(2))
            col_num = int(match.group(3))
            severity_str = match.group(4)
            code = match.group(5)
            message = match.group(6)

            severity = Severity.ERROR if severity_str == 'error' else Severity.WARNING

            try:
                rel_path = self._get_relative_path(Path(file_path))
            except Exception:
                rel_path = file_path

            detailed_message = f"{code}: {message} at line {line_num}, column {col_num}"

            violation = Violation(
                file_path=rel_path,
                rule_name='tsc_analyze',
                severity=severity,
                message=detailed_message,
                line=line_num,
                column=col_num
            )
            violations.append(violation)

        return violations

    def _write_csv_output(self, output_file: Path, violations: list[Violation]):
        """Write tsc results to CSV file.

        Args:
            output_file: Path to CSV output file
            violations: List of violations to write
        """
        try:
            with open(output_file, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['file', 'line', 'column', 'severity', 'code', 'message'])

                for v in violations:
                    line_num = v.line if v.line is not None else 0
                    col_num = v.column if v.column is not None else 0
                    # Extract TSxxxx code from message prefix
                    code_match = re.match(r'^(TS\d+): (.+)', v.message)
                    if code_match:
                        code = code_match.group(1)
                        msg = re.sub(r' at line \d+, column \d+$', '', code_match.group(2))
                    else:
                        code = ''
                        msg = re.sub(r' at line \d+, column \d+$', '', v.message)

                    writer.writerow([v.file_path, line_num, col_num, v.severity.value, code, msg])

            print(f"tsc report saved to: {output_file}")

        except Exception as e:
            print(f"Error writing tsc CSV file: {e}")
