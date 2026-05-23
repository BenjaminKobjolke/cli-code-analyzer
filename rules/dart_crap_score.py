"""Dart CRAP score analyzer.

Combines per-function cyclomatic complexity from dart_code_linter with
per-line coverage from `flutter test --coverage` (LCOV) to compute the
CRAP score per function:

    CRAP(m) = complexity^2 * (1 - coverage)^3 + complexity

Standalone analyzer: invokes dart_code_linter and flutter directly so its
operation does not depend on the dart_code_linter / dart_test_coverage
rules being enabled.
"""

import json
import shutil
from pathlib import Path
from typing import Any

import yaml

from models import LogLevel, Severity, Violation
from rules._crap import coverage_ratio, crap_score
from rules.base import BaseRule
from settings import Settings


class DartCrapScoreRule(BaseRule):
    """Per-function CRAP score for Dart/Flutter projects."""

    def __init__(self, config: dict, base_path: Path | None = None,
                 output_folder: Path | None = None,
                 log_level: LogLevel = LogLevel.ALL,
                 max_errors: int | None = None,
                 rules_file_path: str | None = None,
                 logger=None):
        super().__init__(config, base_path, log_level, max_errors, rules_file_path, logger=logger)
        self.output_folder = output_folder
        self.settings = Settings()
        self._executed = False
        self.project_root: Path | None = None

    def check(self, _file_path: Path) -> list[Violation]:
        if self._executed:
            return []
        self._executed = True

        self.logger.info("\nRunning dart_crap_score check...")

        self.project_root = self._find_pubspec()
        if not self.project_root:
            self.logger.warning("Warning: pubspec.yaml not found, skipping dart_crap_score")
            return []

        dart_cmd = self._get_dart_command(self.settings.get_dart_path, self.settings.prompt_and_save_dart_path)
        if not dart_cmd:
            return []

        if not self._dart_code_linter_in_pubspec():
            self.logger.warning("Warning: dart_code_linter not in dev_dependencies. Run: dart pub add --dev dart_code_linter")
            return []

        # 1. Get per-function complexity + line ranges from DCL JSON
        report_dir = (self.output_folder or self.project_root) / 'crap_report'
        report_dir.mkdir(exist_ok=True, parents=True)
        report_json = self._run_dcl_metrics(dart_cmd, report_dir)
        if not report_json:
            self._cleanup_report_dir(report_dir)
            return []

        functions_by_file, file_metrics, ranges_supported = self._parse_dcl_functions(report_json)
        if not ranges_supported:
            self.logger.info("dart_crap_score: DCL JSON has no function line ranges, falling back to file-level CRAP")

        # 2. Ensure LCOV exists, optionally running flutter test --coverage
        lcov_file = self._ensure_lcov()
        if not lcov_file:
            self._cleanup_report_dir(report_dir)
            return []

        lcov_by_file = self._parse_lcov_per_line(lcov_file)

        # 3. Compute CRAP per function (or per file in fallback) and emit violations
        if ranges_supported:
            violations = self._build_function_violations(functions_by_file, lcov_by_file)
        else:
            violations = self._build_file_violations(file_metrics, lcov_by_file)

        violations = self._filter_violations_by_log_level(violations)

        if violations:
            self.logger.info(f"dart_crap_score found {len(violations)} issue(s)")
        else:
            self.logger.info("dart_crap_score: no issues found")

        if self.output_folder and violations:
            self._write_csv(self.output_folder / 'dart_crap_score.csv', violations)

        self._cleanup_report_dir(report_dir)
        return violations

    # ----- DCL invocation & parsing -------------------------------------------------

    def _dart_code_linter_in_pubspec(self) -> bool:
        try:
            with open(self.project_root / 'pubspec.yaml', encoding='utf-8') as f:
                pubspec = yaml.safe_load(f) or {}
            return 'dart_code_linter' in (pubspec.get('dev_dependencies') or {})
        except Exception as e:
            self.logger.error(f"Error reading pubspec.yaml: {e}")
            return False

    def _run_dcl_metrics(self, dart_cmd: list[str], report_dir: Path) -> Path | None:
        analyze_path = self.config.get('analyze_path', 'lib')
        self.logger.info(f"Running dart_code_linter for CRAP on '{analyze_path}'...")
        cmd = dart_cmd + [
            'pub', 'run', 'dart_code_linter:metrics', 'analyze',
            '--reporter=json',
            f'--json-path={report_dir / "report"}',
            analyze_path,
        ]
        try:
            result = self._run_subprocess(cmd, self.project_root, timeout=self.config.get('test_timeout', 600))
        except Exception as e:
            self.logger.error(f"Error running dart_code_linter: {e}")
            return None

        report_json = report_dir / 'report.json'
        if not report_json.exists():
            self.logger.warning(f"Warning: dart_code_linter did not produce report.json (rc={result.returncode})")
            if result.stderr:
                self.logger.info(f"Stderr: {result.stderr.strip()[:500]}")
            return None
        return report_json

    def _parse_dcl_functions(self, report_json: Path) -> tuple[dict[str, list[dict]], dict[str, float], bool]:
        """Parse DCL JSON.

        Returns:
            (functions_by_file, file_complexity_by_file, ranges_supported)
            functions_by_file: file_abs -> list of {name, first_line, last_line, complexity}
            file_complexity_by_file: file_abs -> file cyclomatic-complexity sum (for fallback)
            ranges_supported: True if at least one function had line range data
        """
        functions_by_file: dict[str, list[dict]] = {}
        file_complexity: dict[str, float] = {}
        ranges_supported = False

        try:
            with open(report_json, encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            self.logger.error(f"Error reading DCL report: {e}")
            return functions_by_file, file_complexity, False

        for record in data.get('records', []):
            raw_path = record.get('path', '')
            if not raw_path:
                continue
            file_abs = self._resolve_record_path(raw_path)

            # File-level complexity for fallback
            for metric in record.get('fileMetrics', []) or []:
                if metric.get('metricsId') == 'cyclomatic-complexity':
                    try:
                        file_complexity[file_abs] = float(metric.get('value', 0))
                    except (TypeError, ValueError):
                        pass

            funcs = record.get('functions', {}) or {}
            for name, fdata in funcs.items():
                cc = self._extract_metric_value(fdata, 'cyclomatic-complexity')
                if cc is None:
                    continue
                first_line, last_line = self._extract_line_range(fdata)
                if first_line is not None and last_line is not None:
                    ranges_supported = True
                    functions_by_file.setdefault(file_abs, []).append({
                        'name': name,
                        'first_line': first_line,
                        'last_line': last_line,
                        'complexity': cc,
                    })
        return functions_by_file, file_complexity, ranges_supported

    @staticmethod
    def _extract_metric_value(entry: dict, metric_id: str) -> float | None:
        for metric in entry.get('metrics', []) or []:
            if metric.get('metricsId') == metric_id:
                try:
                    return float(metric.get('value', 0))
                except (TypeError, ValueError):
                    return None
        return None

    @staticmethod
    def _extract_line_range(entry: dict) -> tuple[int | None, int | None]:
        first = entry.get('firstLine')
        last = entry.get('lastLine')
        if first is not None and last is not None:
            return int(first), int(last)
        loc = entry.get('location') or {}
        start = (loc.get('start') or {}).get('line')
        end = (loc.get('end') or {}).get('line')
        if start is not None and end is not None:
            return int(start), int(end)
        return None, None

    def _resolve_record_path(self, raw_path: str) -> str:
        path = Path(raw_path)
        if not path.is_absolute() and self.project_root:
            path = self.project_root / raw_path
        try:
            return str(path.resolve())
        except Exception:
            return str(path)

    # ----- LCOV ---------------------------------------------------------------------

    def _ensure_lcov(self) -> Path | None:
        lcov_rel = self.config.get('lcov_path', 'coverage/lcov.info')
        lcov_file = (self.project_root / lcov_rel).resolve()
        reuse = self.config.get('reuse_existing_coverage', True)
        run_tests = self.config.get('run_tests', True)

        if lcov_file.exists() and reuse:
            self.logger.info(f"Using existing coverage: {lcov_file}")
            return lcov_file

        if not run_tests:
            if lcov_file.exists():
                return lcov_file
            self.logger.warning(f"Warning: LCOV not found at {lcov_file} and run_tests=false; skipping")
            return None

        if not self._run_flutter_coverage():
            if not lcov_file.exists():
                return None
            self.logger.warning("flutter test failed; parsing existing coverage data")
        if not lcov_file.exists():
            self.logger.warning(f"Warning: coverage file not produced at {lcov_file}")
            return None
        return lcov_file

    def _run_flutter_coverage(self) -> bool:
        flutter_cmd = self._get_flutter_command(self.settings.get_flutter_path, self.settings.prompt_and_save_flutter_path)
        if not flutter_cmd:
            return False
        timeout = self.config.get('test_timeout', 600)
        self.logger.info("Running flutter test --coverage (this may take a while)...")
        try:
            result = self._run_subprocess(flutter_cmd + ['test', '--coverage'], self.project_root, timeout=timeout)
            if result.returncode != 0 and result.stderr:
                self.logger.info(f"Flutter test stderr: {result.stderr.strip()[:500]}")
            return result.returncode == 0
        except Exception as e:
            self.logger.error(f"Error running flutter test: {e}")
            return False

    def _parse_lcov_per_line(self, lcov_file: Path) -> dict[str, dict[int, int]]:
        """Return {resolved_file_path: {line_no: hits}}."""
        coverage: dict[str, dict[int, int]] = {}
        current_file: str | None = None
        current_lines: dict[int, int] = {}
        try:
            content = lcov_file.read_text(encoding='utf-8', errors='replace')
        except Exception as e:
            self.logger.error(f"Error reading LCOV: {e}")
            return coverage

        for line in content.split('\n'):
            line = line.strip()
            if line.startswith('SF:'):
                current_file = line[3:]
                current_lines = {}
            elif line.startswith('DA:') and current_file is not None:
                parts = line[3:].split(',')
                if len(parts) >= 2:
                    try:
                        ln = int(parts[0])
                        hits = int(parts[1])
                        current_lines[ln] = hits
                    except ValueError:
                        pass
            elif line == 'end_of_record' and current_file is not None:
                try:
                    key = str(Path(current_file).resolve())
                except Exception:
                    key = current_file
                coverage[key] = current_lines
                current_file = None
                current_lines = {}
        return coverage

    def _lookup_lcov(self, file_abs: str, lcov_by_file: dict[str, dict[int, int]]) -> dict[int, int]:
        if file_abs in lcov_by_file:
            return lcov_by_file[file_abs]
        # Suffix-match fallback (handles relative/absolute path mismatch)
        rel = self._get_relative_path(Path(file_abs)).replace('\\', '/')
        for key, lines in lcov_by_file.items():
            keyn = key.replace('\\', '/')
            if keyn.endswith('/' + rel) or rel.endswith('/' + keyn):
                return lines
        return {}

    # ----- Violation construction --------------------------------------------------

    def _build_function_violations(self, functions_by_file: dict[str, list[dict]],
                                   lcov_by_file: dict[str, dict[int, int]]) -> list[Violation]:
        violations: list[Violation] = []
        exclude_patterns = self.config.get('exclude_patterns', ['*.g.dart', '*.freezed.dart'])

        for file_abs, funcs in functions_by_file.items():
            rel_path = self._get_relative_path(Path(file_abs))
            if self._is_excluded(rel_path, exclude_patterns):
                continue
            line_hits = self._lookup_lcov(file_abs, lcov_by_file)
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

    def _build_file_violations(self, file_complexity: dict[str, float],
                               lcov_by_file: dict[str, dict[int, int]]) -> list[Violation]:
        violations: list[Violation] = []
        exclude_patterns = self.config.get('exclude_patterns', ['*.g.dart', '*.freezed.dart'])

        for file_abs, cc in file_complexity.items():
            rel_path = self._get_relative_path(Path(file_abs))
            if self._is_excluded(rel_path, exclude_patterns):
                continue
            line_hits = self._lookup_lcov(file_abs, lcov_by_file)
            if not line_hits:
                continue
            total = len(line_hits)
            covered = sum(1 for h in line_hits.values() if h > 0)
            if total == 0:
                continue
            crap = crap_score(cc, covered, total)
            v = self._maybe_emit(rel_path, Path(file_abs), '<file>', None, cc, covered, total, crap)
            if v is not None:
                violations.append(v)
        return violations

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

    def _is_excluded(self, rel_path: str, patterns: list[str]) -> bool:
        from fnmatch import fnmatch
        rel_norm = rel_path.replace('\\', '/')
        for pat in patterns:
            if fnmatch(rel_norm, pat) or fnmatch(Path(rel_norm).name, pat):
                return True
        return False

    def _maybe_emit(self, rel_path: str, file_abs: Path, name: str, line: int | None,
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
        loc_suffix = f" (line {line})" if line else ""
        return Violation(
            file_path=rel_path,
            rule_name='dart_crap_score',
            severity=severity,
            message=f"CRAP={crap:.1f} (complexity={cc_disp}, coverage={cov_pct:.0f}%) in '{name}'{loc_suffix}",
            line=line,
        )

    # ----- Output / cleanup --------------------------------------------------------

    def _write_csv(self, output_file: Path, violations: list[Violation]) -> None:
        import re
        pattern = re.compile(r"^CRAP=([\d.]+) \(complexity=([\d.]+), coverage=(\d+)%\) in '([^']*)'(?: \(line (\d+)\))?$")

        def row_mapper(v: Violation) -> list[Any]:
            m = pattern.match(v.message)
            if not m:
                return [v.file_path, v.line or '', '', '', '', '', v.severity.value]
            crap, cc, cov_pct, name, line = m.groups()
            return [v.file_path, line or v.line or '', name, cc, f"{cov_pct}%", crap, v.severity.value]

        self._write_violations_csv(
            output_file, violations,
            headers=['file', 'line', 'function', 'complexity', 'coverage', 'crap', 'severity'],
            row_mapper=row_mapper,
        )

    def _cleanup_report_dir(self, report_dir: Path) -> None:
        if self.config.get('keep_report', False):
            return
        try:
            shutil.rmtree(report_dir)
        except Exception as e:
            self.logger.warning(f"Warning: could not delete {report_dir}: {e}")
