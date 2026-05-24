"""Python test coverage analyzer.

Runs pytest + coverage (or just `coverage`) and parses coverage.json to
check overall and per-file coverage against configurable thresholds.

coverage.json structure (https://coverage.readthedocs.io/):
    {
      "files": {
        "<path>": {
          "executed_lines": [int, ...],
          "missing_lines": [int, ...],
          "summary": {"percent_covered": float, ...}
        },
        ...
      },
      "totals": {"percent_covered": float, ...}
    }
"""

import json
import shutil
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

from models import LogLevel, Severity, Violation
from rules.base import ProjectWideRule
from rules.context import RuleContext


class PythonTestCoverageRule(ProjectWideRule):
    """Run pytest + coverage.py and check coverage thresholds."""

    def _run(self, _file_path: Path) -> list[Violation]:
        self.logger.info("\nRunning python_test_coverage check...")

        json_path = self.config.get('coverage_json_path', 'coverage.json')
        coverage_json = (self.base_path / json_path).resolve()
        reuse = self.config.get('reuse_existing_coverage', True)
        run_tests = self.config.get('run_tests', True)

        if not (coverage_json.exists() and reuse):
            if not run_tests:
                if not coverage_json.exists():
                    self.logger.warning(f"Warning: coverage JSON not found at {coverage_json} and run_tests=false; skipping")
                    return []
            else:
                if not self._run_tests_with_coverage(coverage_json):
                    if not coverage_json.exists():
                        return []
                    self.logger.warning("Test run failed; parsing existing coverage data")

        if not coverage_json.exists():
            self.logger.warning(f"Warning: coverage JSON not produced at {coverage_json}")
            return []

        coverage_data = self._parse_coverage_json(coverage_json)
        if not coverage_data:
            return []

        violations = self._build_violations(coverage_data)
        violations = self._filter_violations_by_log_level(violations)

        if violations:
            overall = coverage_data['overall_pct']
            self.logger.info(f"python_test_coverage found {len(violations)} issue(s) (overall: {overall:.1f}%)")
        else:
            self.logger.info(f"python_test_coverage: thresholds met (overall: {coverage_data['overall_pct']:.1f}%)")

        if self.output_folder and violations:
            self._write_csv(self.output_folder / 'python_test_coverage.csv', violations)

        return violations

    def _run_tests_with_coverage(self, coverage_json: Path) -> bool:
        timeout = self.config.get('test_timeout', 600)
        run_cmd = self.config.get('run_command') or ['python', '-m', 'coverage', 'run', '-m', 'pytest']
        json_cmd = self.config.get('json_command') or ['python', '-m', 'coverage', 'json', '-o', str(coverage_json)]

        if not shutil.which(run_cmd[0]):
            self.logger.warning(f"Warning: '{run_cmd[0]}' not in PATH; install with: pip install coverage pytest")
            return False

        self.logger.info(f"Running: {' '.join(run_cmd)} (this may take a while)...")
        try:
            run_result = self._run_subprocess(run_cmd, self.base_path, timeout=timeout)
            if run_result.returncode != 0 and run_result.stderr:
                self.logger.info(f"Coverage run stderr: {run_result.stderr.strip()[:500]}")
        except Exception as e:
            self.logger.error(f"Error running coverage: {e}")
            return False

        self.logger.info(f"Exporting coverage to {coverage_json}...")
        try:
            json_result = self._run_subprocess(json_cmd, self.base_path, timeout=timeout)
            if json_result.returncode != 0:
                if json_result.stderr:
                    self.logger.warning(f"coverage json stderr: {json_result.stderr.strip()[:500]}")
                return False
            return True
        except Exception as e:
            self.logger.error(f"Error exporting coverage JSON: {e}")
            return False

    def _parse_coverage_json(self, coverage_json: Path) -> dict | None:
        try:
            with open(coverage_json, encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            self.logger.error(f"Error reading coverage JSON: {e}")
            return None

        overall_pct = (data.get('totals') or {}).get('percent_covered', 0.0)
        files = data.get('files') or {}
        return {'overall_pct': overall_pct, 'files': files}

    def _build_violations(self, coverage_data: dict) -> list[Violation]:
        violations: list[Violation] = []
        overall_cfg = self.config.get('overall_coverage', {'warning': 60, 'error': 40})
        per_file_cfg = self.config.get('per_file_coverage', {'warning': 50, 'error': 20})
        exclude_patterns = self.config.get('exclude_patterns', ['**/__pycache__/**', '*.pyc', '**/.venv/**', '**/venv/**'])

        overall_pct = coverage_data['overall_pct']
        overall_warn = overall_cfg.get('warning', 60)
        overall_err = overall_cfg.get('error', 40)
        if overall_err is not None and overall_pct < overall_err:
            violations.append(Violation(
                file_path='project',
                rule_name='python_test_coverage',
                severity=Severity.ERROR,
                message=f"Overall test coverage is {overall_pct:.1f}% (error threshold: {overall_err}%)",
            ))
        elif overall_warn is not None and overall_pct < overall_warn:
            violations.append(Violation(
                file_path='project',
                rule_name='python_test_coverage',
                severity=Severity.WARNING,
                message=f"Overall test coverage is {overall_pct:.1f}% (warning threshold: {overall_warn}%)",
            ))

        for file_path, fdata in sorted(coverage_data['files'].items()):
            rel = self._normalize_path(file_path)
            if self._is_excluded(rel, exclude_patterns):
                continue
            summary = fdata.get('summary') or {}
            pct = summary.get('percent_covered', 0.0)
            executed = summary.get('covered_lines') or len(fdata.get('executed_lines') or [])
            total = summary.get('num_statements') or (executed + len(fdata.get('missing_lines') or []))

            warn_t = per_file_cfg.get('warning', 50)
            err_t = per_file_cfg.get('error', 20)
            if err_t is not None and pct < err_t:
                violations.append(Violation(
                    file_path=rel,
                    rule_name='python_test_coverage',
                    severity=Severity.ERROR,
                    message=f"Test coverage is {pct:.1f}% ({executed}/{total} lines) - error threshold: {err_t}%",
                ))
            elif warn_t is not None and pct < warn_t:
                violations.append(Violation(
                    file_path=rel,
                    rule_name='python_test_coverage',
                    severity=Severity.WARNING,
                    message=f"Test coverage is {pct:.1f}% ({executed}/{total} lines) - warning threshold: {warn_t}%",
                ))
        return violations

    def _normalize_path(self, raw: str) -> str:
        try:
            return self._get_relative_path(Path(raw))
        except Exception:
            return raw

    @staticmethod
    def _is_excluded(rel_path: str, patterns: list[str]) -> bool:
        rel_norm = rel_path.replace('\\', '/')
        for pat in patterns:
            if fnmatch(rel_norm, pat) or fnmatch(Path(rel_norm).name, pat):
                return True
        return False

    def _write_csv(self, output_file: Path, violations: list[Violation]) -> None:
        import re
        pct_re = re.compile(r'(\d+\.\d+)%')
        lines_re = re.compile(r'\((\d+)/(\d+) lines\)')
        threshold_re = re.compile(r'threshold: (\d+)%')

        def row_mapper(v: Violation) -> list[Any]:
            pct = float(m.group(1)) if (m := pct_re.search(v.message)) else 0.0
            executed = total = ''
            if lm := lines_re.search(v.message):
                executed, total = lm.group(1), lm.group(2)
            threshold = tm.group(1) if (tm := threshold_re.search(v.message)) else ''
            return [v.file_path, executed, total, f"{pct:.1f}", threshold, v.severity.value]

        self._write_violations_csv(
            output_file, violations,
            headers=['file', 'covered', 'total', 'coverage_pct', 'threshold', 'severity'],
            row_mapper=row_mapper,
        )
