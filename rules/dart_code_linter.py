"""
Dart Code Linter (DCM) rule for Flutter/Dart code metrics analysis
"""

import csv
import json
import re
import shutil
from pathlib import Path
from typing import Any, ClassVar

import yaml

from models import LogLevel, Severity, Violation
from rules.base import BaseRule
from settings import Settings


class DartCodeLinterRule(BaseRule):
    """Rule to analyze Dart/Flutter code metrics using dart_code_linter"""

    def __init__(self, config: dict, base_path: Path | None = None, output_folder: Path | None = None, log_level: LogLevel = LogLevel.ALL, max_errors: int | None = None, rules_file_path: str | None = None):
        """Initialize Dart Code Linter rule with config and output settings."""
        super().__init__(config, base_path, max_errors, rules_file_path)
        self.output_folder = output_folder
        self.log_level = log_level
        self.settings = Settings()
        self._executed = False
        self.project_root = None

    def check(self, _file_path: Path) -> list[Violation]:
        """Run dart_code_linter on the entire project (executes once, returns empty for subsequent calls)."""
        if self._executed:
            return []
        self._executed = True

        print("\nChecking dart_code_linter metrics...")

        dart_path = self._get_tool_path('dart', self.settings.get_dart_path, self.settings.prompt_and_save_dart_path)
        if not dart_path:
            return []

        if not self._check_dart_code_linter_installed():
            if self.config.get('auto_install', False):
                if not self._install_dart_code_linter(dart_path):
                    return []
            else:
                print("Warning: dart_code_linter is not installed. Run: dart pub add --dev dart_code_linter")
                return []

        return self._run_dart_code_linter(dart_path)

    def _check_dart_code_linter_installed(self) -> bool:
        """Check if dart_code_linter is in dev_dependencies of pubspec.yaml."""
        self.project_root = self._find_pubspec()
        if not self.project_root:
            print(f"Warning: pubspec.yaml not found in {self.base_path} or parent directory")
            return False

        try:
            with open(self.project_root / 'pubspec.yaml', encoding='utf-8') as f:
                pubspec_data = yaml.safe_load(f)
            dev_deps = pubspec_data.get('dev_dependencies', {}) if pubspec_data else {}
            return 'dart_code_linter' in dev_deps
        except Exception as e:
            print(f"Error reading pubspec.yaml: {e}")
            return False

    def _install_dart_code_linter(self, dart_path: str) -> bool:
        """Install dart_code_linter using dart pub add."""
        print("dart_code_linter not found. Installing...")
        install_dir = self.project_root or self.base_path
        try:
            result = self._run_subprocess([dart_path, 'pub', 'add', '--dev', 'dart_code_linter'], install_dir)
            if result.returncode == 0:
                print("dart_code_linter installed successfully\n")
                return True
            print(f"Failed to install dart_code_linter: {result.stderr}")
            return False
        except Exception as e:
            print(f"Error installing dart_code_linter: {e}")
            return False

    def _run_dart_code_linter(self, dart_path: str) -> list[Violation]:
        """Execute dart_code_linter and return parsed violations."""
        analyze_path = self.config.get('analyze_path', 'lib')
        print(f"Running dart_code_linter analysis on '{analyze_path}'...")

        working_dir = self.project_root or self.base_path
        report_dir = (self.output_folder or working_dir) / 'code_analysis'
        report_dir.mkdir(exist_ok=True)
        report_json = report_dir / 'report.json'

        cmd = [dart_path, 'run', 'dart_code_linter:metrics', 'analyze',
               '--fatal-warnings', '--fatal-style', '--reporter=json',
               f'--json-path={report_dir / "report"}', analyze_path]

        try:
            result = self._run_subprocess(cmd, working_dir)

            if not report_json.exists():
                print(f"Warning: dart_code_linter did not generate report.json (rc={result.returncode})")
                if result.stdout:
                    print(f"Stdout: {result.stdout}")
                if result.stderr:
                    print(f"Stderr: {result.stderr}")
                return []

            print(f"Metrics report saved to: {report_json}")
            violations = self._filter_violations_by_log_level(self._parse_metrics_json(report_json))
            print(f"\nDart Code Linter found {len(violations)} metric violation(s)" if violations
                  else "\nDart Code Linter: No metric violations found")

            if self.output_folder and violations:
                self._write_csv_output(self.output_folder / 'dart_code_linter.csv', violations, report_json)

            if not self.config.get('keep_report', False):
                try:
                    shutil.rmtree(report_dir)
                    print(f"Cleaned up: {report_dir}")
                except Exception as e:
                    print(f"Warning: Could not delete report directory: {e}")

            return violations
        except Exception as e:
            print(f"Error running dart_code_linter: {e}")
            return []

    def _parse_metrics_json(self, report_path: Path) -> list[Violation]:
        """Parse dart_code_linter JSON report into violations."""
        violations = []
        try:
            with open(report_path, encoding='utf-8') as f:
                data = json.load(f)

            thresholds = self.config.get('metrics', {})
            for record in data.get('records', []):
                file_path = record.get('path', 'unknown')
                # Unified loop for file, class, and function metrics
                metrics_sources = [
                    (record.get('fileMetrics', []), 'file'),
                    *[(cd.get('metrics', []), f'class {cn}') for cn, cd in record.get('classes', {}).items()],
                    *[(fd.get('metrics', []), f'function {fn}') for fn, fd in record.get('functions', {}).items()],
                ]
                for metrics, context in metrics_sources:
                    for metric in metrics:
                        if v := self._check_metric_threshold(file_path, metric, thresholds, context):
                            violations.append(v)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Error reading dart_code_linter report: {e}")
        except Exception as e:
            print(f"Error processing dart_code_linter results: {e}")
        return violations

    INVERSE_METRICS: ClassVar[set[str]] = {'maintainability-index', 'weight-of-class'}

    def _check_metric_threshold(self, file_path: str, metric: dict[str, Any],
                                 thresholds: dict[str, dict[str, int]], context: str = '') -> Violation | None:
        """Check if metric exceeds thresholds, return Violation or None."""
        metric_id = metric.get('metricsId', 'unknown')
        value = metric.get('value', 0)

        if metric_id not in thresholds:
            return None

        eff = self._get_threshold_for_file(Path(file_path), thresholds[metric_id], metric_id)
        err_th, warn_th = eff.get('error'), eff.get('warning')
        if err_th == 0 and warn_th == 0:
            return None

        is_inverse = metric_id in self.INVERSE_METRICS
        compare = (lambda v, t: v <= t) if is_inverse else (lambda v, t: v >= t)

        severity, threshold_value = None, None
        if err_th is not None and compare(value, err_th):
            severity, threshold_value = Severity.ERROR, err_th
        elif warn_th is not None and compare(value, warn_th):
            severity, threshold_value = Severity.WARNING, warn_th

        if severity is None:
            return None

        try:
            rel_path = self._get_relative_path(Path(file_path))
        except Exception:
            rel_path = file_path

        op = "<=" if is_inverse else ">="
        ctx = f" in {context}" if context else ""
        return Violation(file_path=rel_path, rule_name='dart_code_linter', severity=severity,
                         message=f"{metric_id} = {value} {op} {threshold_value} (threshold){ctx}")

    def _write_csv_output(self, output_file: Path, violations: list[Violation], _report_json: Path):
        """Write dart_code_linter results to CSV, sorted by severity, limited by max_errors."""
        try:
            pattern = r'^(.+?) = ([\d.]+) [<>]= ([\d.]+) \(threshold\)(?: in (.+))?$'
            csv_rows = []
            for v in violations:
                if m := re.match(pattern, v.message):
                    csv_rows.append({'file_path': v.file_path, 'metric': m.group(1), 'value': float(m.group(2)),
                                     'threshold': float(m.group(3)), 'severity': v.severity.value, 'context': m.group(4) or ''})

            if self.max_errors and len(csv_rows) > self.max_errors:
                sev_order = {'ERROR': 0, 'WARNING': 1, 'INFO': 2}
                csv_rows.sort(key=lambda r: (sev_order.get(r['severity'], 3), -r['value']))
                csv_rows = csv_rows[:self.max_errors]

            if csv_rows:
                with open(output_file, 'w', encoding='utf-8', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(['file_path', 'metric', 'value', 'threshold', 'severity', 'context'])
                    for r in csv_rows:
                        writer.writerow([r['file_path'], r['metric'], r['value'], r['threshold'], r['severity'], r['context']])
                print(f"Dart Code Linter report saved to: {output_file}")
            else:
                print("No violations to write to CSV (after log level filtering)")
        except Exception as e:
            print(f"Error writing dart_code_linter CSV file: {e}")
