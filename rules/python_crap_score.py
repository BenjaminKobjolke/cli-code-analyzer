"""Python CRAP score analyzer.

Combines per-function cyclomatic complexity from pyscn with per-line
coverage from coverage.py JSON to compute the CRAP score per function:

    CRAP(m) = complexity^2 * (1 - coverage)^3 + complexity

Standalone analyzer: invokes pyscn directly and reads coverage.json
without sharing runtime state with pyscn_analyze or python_test_coverage.
"""

import json
from pathlib import Path

from models import RuleResult
from rules._crap import CrapScoreMixin
from rules.base import ProjectWideRule
from rules.python_coverage_io import run_tests_with_coverage


class PythonCrapScoreRule(CrapScoreMixin, ProjectWideRule):
    """Per-function CRAP score for Python projects."""

    rule_name = 'python_crap_score'

    def _run(self, _file_path: Path) -> RuleResult:
        self.logger.info("\nRunning python_crap_score check...")

        # Resolve pyscn up front so a missing tool reports FAILED rather than
        # being collapsed into the "no functions" skip path below.
        pyscn_path = self._get_tool_path('pyscn')
        if not pyscn_path:
            return self._failed("pyscn executable not found")

        functions_by_file = self._collect_functions(pyscn_path)
        if not functions_by_file:
            return self._skipped("no functions with complexity data found")

        coverage_by_file = self._load_coverage()
        if coverage_by_file is None:
            return self._failed("coverage data unavailable")

        exclude_patterns = self.config.get('exclude_patterns',
                                           ['**/__pycache__/**', '*.pyc', '**/.venv/**', '**/venv/**'])
        violations = self._build_function_violations(functions_by_file, coverage_by_file, exclude_patterns)
        violations = self._filter_violations_by_log_level(violations)

        if violations:
            self.logger.info(f"python_crap_score found {len(violations)} issue(s)")
        else:
            self.logger.info("python_crap_score: no issues found")

        if self.output_folder and violations:
            self._write_csv(self.output_folder / 'python_crap_score.csv', violations)

        return self._ok(violations)

    # ----- pyscn complexity --------------------------------------------------------

    def _collect_functions(self, pyscn_path: str) -> dict[str, list[dict]]:

        cmd = [pyscn_path, 'analyze', '--json', '--select', 'complexity', str(self.base_path)]
        try:
            result = self._run_subprocess(cmd, cwd=self.base_path)
        except Exception as e:
            self.logger.error(f"Error running pyscn: {e}")
            return {}

        if not result.stdout or not result.stdout.strip():
            if result.stderr:
                self.logger.warning(f"pyscn stderr: {result.stderr.strip()}")
            return {}

        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            self.logger.error(f"Error parsing pyscn JSON: {e}")
            return {}

        functions_by_file: dict[str, list[dict]] = {}
        complexity_section = data.get('complexity') or data.get('Complexity') or {}
        functions = complexity_section.get('Functions') or complexity_section.get('functions') or []
        for fn in functions:
            file_path = fn.get('FilePath') or fn.get('file_path') or ''
            if not file_path:
                continue
            metrics = fn.get('Metrics') or fn.get('metrics') or {}
            cc = metrics.get('Complexity') or metrics.get('complexity')
            if cc is None:
                continue
            start_line = fn.get('StartLine') or fn.get('start_line')
            end_line = fn.get('EndLine') or fn.get('end_line')
            name = fn.get('Name') or fn.get('name') or '<unknown>'
            if start_line is None or end_line is None:
                continue
            file_abs = self._resolve_path(file_path)
            functions_by_file.setdefault(file_abs, []).append({
                'name': name,
                'first_line': int(start_line),
                'last_line': int(end_line),
                'complexity': float(cc),
            })
        return functions_by_file

    def _resolve_path(self, raw: str) -> str:
        p = Path(raw)
        if not p.is_absolute():
            p = self.base_path / raw
        try:
            return str(p.resolve())
        except Exception:
            return str(p)

    # ----- coverage.json ----------------------------------------------------------

    def _load_coverage(self) -> dict[str, dict[int, int]] | None:
        json_path = self.config.get('coverage_json_path', 'coverage.json')
        coverage_json = (self.base_path / json_path).resolve()
        reuse = self.config.get('reuse_existing_coverage', True)
        run_tests = self.config.get('run_tests', True)

        if not (coverage_json.exists() and reuse):
            if not run_tests:
                if not coverage_json.exists():
                    self.logger.warning(f"Warning: coverage JSON not found at {coverage_json} and run_tests=false; skipping")
                    return None
            else:
                if not self._run_tests_with_coverage(coverage_json):
                    if not coverage_json.exists():
                        return None
                    self.logger.warning("Test run failed; using existing coverage data")

        if not coverage_json.exists():
            self.logger.warning(f"Warning: coverage JSON not produced at {coverage_json}")
            return None

        try:
            with open(coverage_json, encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            self.logger.error(f"Error reading coverage JSON: {e}")
            return None

        coverage_by_file: dict[str, dict[int, int]] = {}
        for raw_path, fdata in (data.get('files') or {}).items():
            file_abs = self._resolve_path(raw_path)
            executed = set(fdata.get('executed_lines') or [])
            missing = set(fdata.get('missing_lines') or [])
            lines: dict[int, int] = {}
            for ln in executed:
                lines[int(ln)] = 1
            for ln in missing:
                lines.setdefault(int(ln), 0)
            coverage_by_file[file_abs] = lines
        return coverage_by_file

    def _run_tests_with_coverage(self, coverage_json: Path) -> bool:
        return run_tests_with_coverage(self, coverage_json)
