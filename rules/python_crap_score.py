"""Python CRAP score analyzer.

Combines per-function cyclomatic complexity from pyscn with per-line
coverage from coverage.py JSON to compute the CRAP score per function:

    CRAP(m) = complexity^2 * (1 - coverage)^3 + complexity

Standalone analyzer: invokes pyscn directly and reads coverage.json
without sharing runtime state with pyscn_analyze or python_test_coverage.
"""

import json
import shutil
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

from models import LogLevel, RuleResult, Severity, Violation
from rules._crap import coverage_ratio, crap_score
from rules.base import ProjectWideRule
from rules.context import RuleContext


class PythonCrapScoreRule(ProjectWideRule):
    """Per-function CRAP score for Python projects."""

    rule_name = 'python_crap_score'

    def _run(self, _file_path: Path) -> RuleResult:
        self.logger.info("\nRunning python_crap_score check...")

        # Resolve pyscn up front so a missing tool reports FAILED rather than
        # being collapsed into the "no functions" skip path below.
        pyscn_path = self._get_tool_path(
            'pyscn',
            self.settings.get_pyscn_path,
            self.settings.prompt_and_save_pyscn_path,
        )
        if not pyscn_path:
            return self._failed("pyscn executable not found")

        functions_by_file = self._collect_functions(pyscn_path)
        if not functions_by_file:
            return self._skipped("no functions with complexity data found")

        coverage_by_file = self._load_coverage()
        if coverage_by_file is None:
            return self._failed("coverage data unavailable")

        violations = self._build_violations(functions_by_file, coverage_by_file)
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

    # ----- Violations -------------------------------------------------------------

    def _build_violations(self, functions_by_file: dict[str, list[dict]],
                          coverage_by_file: dict[str, dict[int, int]]) -> list[Violation]:
        violations: list[Violation] = []
        exclude_patterns = self.config.get('exclude_patterns',
                                           ['**/__pycache__/**', '*.pyc', '**/.venv/**', '**/venv/**'])

        for file_abs, funcs in functions_by_file.items():
            rel_path = self._get_relative_path(Path(file_abs))
            if self._is_excluded(rel_path, exclude_patterns):
                continue
            line_hits = self._lookup_coverage(file_abs, coverage_by_file)
            if not line_hits:
                continue
            for fn in funcs:
                total, covered = self._count_function_coverage(fn['first_line'], fn['last_line'], line_hits)
                if total == 0:
                    continue
                crap = crap_score(fn['complexity'], covered, total)
                v = self._maybe_emit(rel_path, Path(file_abs), fn['name'], fn['first_line'],
                                     fn['complexity'], covered, total, crap)
                if v is not None:
                    violations.append(v)
        return violations

    def _lookup_coverage(self, file_abs: str,
                         coverage_by_file: dict[str, dict[int, int]]) -> dict[int, int]:
        if file_abs in coverage_by_file:
            return coverage_by_file[file_abs]
        rel = self._get_relative_path(Path(file_abs)).replace('\\', '/')
        for key, lines in coverage_by_file.items():
            keyn = key.replace('\\', '/')
            if keyn.endswith('/' + rel) or rel.endswith('/' + keyn):
                return lines
        return {}

    @staticmethod
    def _count_function_coverage(first_line: int, last_line: int,
                                 line_hits: dict[int, int]) -> tuple[int, int]:
        total = 0
        covered = 0
        for ln in range(first_line, last_line + 1):
            if ln in line_hits:
                total += 1
                if line_hits[ln] > 0:
                    covered += 1
        return total, covered

    @staticmethod
    def _is_excluded(rel_path: str, patterns: list[str]) -> bool:
        rel_norm = rel_path.replace('\\', '/')
        for pat in patterns:
            if fnmatch(rel_norm, pat) or fnmatch(Path(rel_norm).name, pat):
                return True
        return False

    def _maybe_emit(self, rel_path: str, file_abs: Path, name: str, line: int,
                    complexity: float, covered: int, total: int, crap: float) -> Violation | None:
        thresholds = self._get_threshold_for_file(file_abs, self.config)
        warn_t = thresholds.get('warning')
        err_t = thresholds.get('error')

        severity: Severity | None = None
        if err_t is not None and crap >= err_t:
            severity = Severity.ERROR
        elif warn_t is not None and crap >= warn_t:
            severity = Severity.WARNING
        if severity is None:
            return None

        cov_pct = coverage_ratio(covered, total) * 100
        cc_disp = int(complexity) if float(complexity).is_integer() else complexity
        return Violation(
            file_path=rel_path,
            rule_name='python_crap_score',
            severity=severity,
            message=f"CRAP={crap:.1f} (complexity={cc_disp}, coverage={cov_pct:.0f}%) in '{name}' (line {line})",
            line=line,
        )

    def _write_csv(self, output_file: Path, violations: list[Violation]) -> None:
        import re
        pattern = re.compile(r"^CRAP=([\d.]+) \(complexity=([\d.]+), coverage=(\d+)%\) in '([^']*)' \(line (\d+)\)$")

        def row_mapper(v: Violation) -> list[Any]:
            m = pattern.match(v.message)
            if not m:
                return [v.file_path, v.line or '', '', '', '', '', v.severity.value]
            crap, cc, cov_pct, name, line = m.groups()
            return [v.file_path, line, name, cc, f"{cov_pct}%", crap, v.severity.value]

        self._write_violations_csv(
            output_file, violations,
            headers=['file', 'line', 'function', 'complexity', 'coverage', 'crap', 'severity'],
            row_mapper=row_mapper,
        )
