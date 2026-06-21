"""
TypeScript type checking rule using tsc --noEmit
"""

import csv
import re
from pathlib import Path

from models import RuleResult, Severity, Violation
from rules.base import ProjectWideRule


class TscAnalyzeRule(ProjectWideRule):
    """Rule to analyze TypeScript code using tsc --noEmit"""

    rule_name = 'tsc_analyze'

    def _run(self, _file_path: Path) -> RuleResult:
        self.logger.info("Running tsc type checking...")

        tsc_path = self._get_tool_path('tsc', self.settings.get_tsc_path, self.settings.prompt_and_save_tsc_path)
        if not tsc_path:
            return self._failed("tsc executable not found")

        return self._run_tsc(tsc_path)

    def _run_tsc(self, tsc_path: str) -> RuleResult:
        """Execute tsc --noEmit and parse results.

        Args:
            tsc_path: Path to tsc executable

        Returns:
            RuleResult
        """
        cmd = [tsc_path, '--noEmit', '--pretty', 'false']

        tsconfig = self.config.get('tsconfig')
        if tsconfig:
            cmd.extend(['--project', tsconfig])

        try:
            result = self._run_subprocess(cmd, self.base_path)

            output = result.stdout if result.stdout.strip() else result.stderr

            violations = self._parse_tsc_output(output)

            # Filter Svelte resolve false positives (TS2614 referencing *.svelte)
            if self.config.get('skip_svelte_resolve_errors', False):
                violations = [v for v in violations if not (
                    'TS2614' in v.message and '*.svelte' in v.message
                )]

            # Filter by ignore_codes config
            ignore_codes = self.config.get('ignore_codes', [])
            if ignore_codes:
                violations = [v for v in violations if not any(code in v.message for code in ignore_codes)]

            violations = self._filter_violations_by_log_level(violations)

            if self.max_errors and len(violations) > self.max_errors:
                violations = violations[:self.max_errors]

            if violations:
                self.logger.info(f"tsc found {len(violations)} issue(s)")
            else:
                self.logger.info("tsc: No issues found")

            if self.output_folder and violations:
                output_file = self.output_folder / 'tsc_analyze.csv'
                self._write_csv_output(output_file, violations)

            return self._ok(violations)

        except FileNotFoundError:
            self.logger.error(f"Error: tsc executable not found: {tsc_path}")
            self.logger.error("Please ensure TypeScript is installed: npm install --save-dev typescript")
            return self._failed(f"tsc executable not found: {tsc_path}")
        except Exception as e:
            self.logger.error(f"Error running tsc: {e}")
            return self._failed(f"error running tsc: {e}")

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

            self.logger.info(f"tsc report saved to: {output_file}")

        except Exception as e:
            self.logger.error(f"Error writing tsc CSV file: {e}")
