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
        """Initialize Flutter analyze rule with config and output settings."""
        super().__init__(config, base_path, log_level, max_errors, rules_file_path)
        self.output_folder = output_folder
        self.log_level = log_level
        self.settings = Settings()
        self._flutter_executed = False
        self.project_root = None

    def check(self, _file_path: Path) -> list[Violation]:
        """Run flutter analyze on the entire project (executes once, returns empty for subsequent calls)."""
        if self._flutter_executed:
            return []
        self._flutter_executed = True

        print("\nRunning flutter analyze...")

        if not self._is_flutter_project():
            print("Not a Flutter project (no flutter dependency in pubspec.yaml)")
            return []

        flutter_cmd = self._get_flutter_command(self.settings.get_flutter_path, self.settings.prompt_and_save_flutter_path)
        if not flutter_cmd:
            return []

        return self._run_flutter_analyze(flutter_cmd)

    def _is_flutter_project(self) -> bool:
        """Check if project has flutter dependency in pubspec.yaml."""
        self.project_root = self._find_pubspec()
        if not self.project_root:
            print(f"Warning: pubspec.yaml not found in {self.base_path} or parent")
            return False

        try:
            with open(self.project_root / 'pubspec.yaml', encoding='utf-8') as f:
                pubspec_data = yaml.safe_load(f)
            if not pubspec_data:
                return False
            deps = pubspec_data.get('dependencies', {})
            dev_deps = pubspec_data.get('dev_dependencies', {})
            return 'flutter' in deps or 'flutter' in dev_deps
        except Exception as e:
            print(f"Warning: Could not parse pubspec.yaml: {e}")
            return False

    def _run_flutter_analyze(self, flutter_cmd: list[str]) -> list[Violation]:
        """Execute flutter analyze and return parsed violations."""
        try:
            result = self._run_subprocess(flutter_cmd + ['analyze'], self.project_root or self.base_path)
            output = result.stdout if result.stdout.strip() else result.stderr
            violations = self._filter_violations_by_log_level(self._parse_flutter_text_output(output))

            print(f"\nFlutter analyze found {len(violations)} issue(s)" if violations else "\nFlutter analyze: No issues found")

            if self.output_folder and violations:
                self._write_csv_output(self.output_folder / 'flutter_analyze.csv', violations)

            return violations
        except Exception as e:
            err_msg = "Flutter executable not found" if isinstance(e, FileNotFoundError) else str(e)
            print(f"Error running flutter analyze: {err_msg}")
            return []

    def _parse_flutter_text_output(self, output: str) -> list[Violation]:
        """Parse flutter analyze text output (severity - message - path:line:col - code) into violations."""
        violations = []
        if not output or not output.strip():
            return violations

        main_pattern = re.compile(
            r'^\s*(warning|info|error)\s+-\s+(.+?)\s+-\s+(.+?):(\d+):(\d+)\s+-\s+(\S+)\s*$', re.IGNORECASE)
        continuation_pattern = re.compile(
            r'^\s+(info|warning|error)\s+-\s+(.+?)\s+-\s*$', re.IGNORECASE)

        current_violation = None
        current_message_parts = []

        for line in output.split('\n'):
            main_match = main_pattern.match(line)
            if main_match:
                if current_violation:
                    current_violation['message'] = ' '.join(current_message_parts)
                    violations.append(self._create_violation(current_violation))
                severity_str, message, file_path, line_num, col_num, code = main_match.groups()
                current_violation = {
                    'severity': severity_str, 'message': message, 'file_path': file_path,
                    'line': int(line_num), 'column': int(col_num), 'code': code
                }
                current_message_parts = [message.strip()]
                continue

            continuation_match = continuation_pattern.match(line)
            if continuation_match and current_violation:
                current_message_parts.append(continuation_match.group(2).strip())

        if current_violation:
            current_violation['message'] = ' '.join(current_message_parts)
            violations.append(self._create_violation(current_violation))

        return violations

    def _create_violation(self, data: dict[str, Any]) -> Violation:
        """Create a Violation object from parsed data dict."""
        try:
            file_path = Path(data['file_path'])
            rel_path = str(file_path.resolve().relative_to(self.project_root)) if self.project_root else self._get_relative_path(file_path)
        except (ValueError, Exception):
            rel_path = data['file_path']

        return Violation(
            file_path=rel_path, rule_name='flutter_analyze',
            severity=self._map_severity(data['severity']),
            message=f"{data['message']} ({data['code']}) at line {data['line']}, column {data['column']}"
        )

    def _write_csv_output(self, output_file: Path, violations: list[Violation]):
        """Write flutter analyze results to CSV, sorted by severity, limited by max_errors."""
        try:
            if not violations:
                return

            violation_data = []
            for v in violations:
                line_m = re.search(r'at line (\d+)', v.message)
                col_m = re.search(r'column (\d+)', v.message)
                code_m = re.search(r'\(([^)]+)\) at line', v.message)
                code = code_m.group(1) if code_m else 'unknown'
                base_msg = v.message.split(f'({code})')[0].strip() if code_m else v.message
                sev_order = {Severity.ERROR: 0, Severity.WARNING: 1}.get(v.severity, 2)
                violation_data.append({
                    'file': v.file_path, 'line': int(line_m.group(1)) if line_m else 0,
                    'column': int(col_m.group(1)) if col_m else 0, 'severity': v.severity.name,
                    'code': code, 'message': base_msg, 'severity_order': sev_order
                })

            if self.max_errors and len(violation_data) > self.max_errors:
                violation_data.sort(key=lambda x: (x['severity_order'], x['file'], x['line']))
                violation_data = violation_data[:self.max_errors]

            with open(output_file, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['file', 'line', 'column', 'severity', 'code', 'message'])
                for d in violation_data:
                    writer.writerow([d['file'], d['line'], d['column'], d['severity'], d['code'], d['message']])

            print(f"Flutter analyze report saved to: {output_file}")

        except Exception as e:
            print(f"Error writing flutter analyze CSV file: {e}")
