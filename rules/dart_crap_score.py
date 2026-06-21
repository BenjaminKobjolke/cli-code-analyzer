"""Dart CRAP score analyzer.

Combines per-function cyclomatic complexity from dart_code_linter with
per-line coverage from `flutter test --coverage` (LCOV) to compute the
CRAP score per function:

    CRAP(m) = complexity^2 * (1 - coverage)^3 + complexity

Standalone analyzer: invokes dart_code_linter and flutter directly so its
operation does not depend on the dart_code_linter / dart_test_coverage
rules being enabled. The DCL/LCOV I/O lives in DartCrapIOMixin and the shared
coverage/violation logic in CrapScoreMixin.
"""

import shutil
from pathlib import Path

import yaml

from models import RuleResult, Violation
from rules._crap import CrapScoreMixin, crap_score
from rules.base import ProjectWideRule
from rules.context import RuleContext
from rules.dart_crap_io import DartCrapIOMixin

DEFAULT_EXCLUDE = ['*.g.dart', '*.freezed.dart']


class DartCrapScoreRule(CrapScoreMixin, DartCrapIOMixin, ProjectWideRule):
    """Per-function CRAP score for Dart/Flutter projects."""

    rule_name = 'dart_crap_score'

    def __init__(self, ctx: RuleContext):
        super().__init__(ctx)
        self.project_root: Path | None = None

    def _run(self, _file_path: Path) -> RuleResult:
        self.logger.info("\nRunning dart_crap_score check...")

        self.project_root = self._find_pubspec()
        if not self.project_root:
            self.logger.warning("Warning: pubspec.yaml not found, skipping dart_crap_score")
            return self._skipped("pubspec.yaml not found")

        dart_cmd = self._get_dart_command()
        if not dart_cmd:
            return self._failed("dart executable not found")

        if not self._dart_code_linter_in_pubspec():
            self.logger.warning("Warning: dart_code_linter not in dev_dependencies. Run: dart pub add --dev dart_code_linter")
            return self._failed("dart_code_linter not in dev_dependencies")

        # 1. Get per-function complexity + line ranges from DCL JSON
        report_dir = (self.output_folder or self.project_root) / 'crap_report'
        report_dir.mkdir(exist_ok=True, parents=True)
        report_json = self._run_dcl_metrics(dart_cmd, report_dir)
        if not report_json:
            self._cleanup_report_dir(report_dir)
            return self._failed("dart_code_linter did not produce a report")

        functions_by_file, file_metrics, ranges_supported = self._parse_dcl_functions(report_json)
        if not ranges_supported:
            self.logger.info("dart_crap_score: DCL JSON has no function line ranges, falling back to file-level CRAP")

        # 2. Ensure LCOV exists, optionally running flutter test --coverage
        lcov_file = self._ensure_lcov()
        if not lcov_file:
            self._cleanup_report_dir(report_dir)
            return self._skipped("no coverage data available")

        lcov_by_file = self._parse_lcov_per_line(lcov_file)

        # 3. Compute CRAP per function (or per file in fallback) and emit violations
        exclude_patterns = self.config.get('exclude_patterns', DEFAULT_EXCLUDE)
        if ranges_supported:
            violations = self._build_function_violations(functions_by_file, lcov_by_file, exclude_patterns)
        else:
            violations = self._build_file_violations(file_metrics, lcov_by_file, exclude_patterns)

        violations = self._filter_violations_by_log_level(violations)

        if violations:
            self.logger.info(f"dart_crap_score found {len(violations)} issue(s)")
        else:
            self.logger.info("dart_crap_score: no issues found")

        if self.output_folder and violations:
            self._write_csv(self.output_folder / 'dart_crap_score.csv', violations)

        self._cleanup_report_dir(report_dir)
        return self._ok(violations)

    def _dart_code_linter_in_pubspec(self) -> bool:
        try:
            with open(self.project_root / 'pubspec.yaml', encoding='utf-8') as f:
                pubspec = yaml.safe_load(f) or {}
            return 'dart_code_linter' in (pubspec.get('dev_dependencies') or {})
        except Exception as e:
            self.logger.error(f"Error reading pubspec.yaml: {e}")
            return False

    def _build_file_violations(self, file_complexity: dict[str, float],
                               lcov_by_file: dict[str, dict[int, int]],
                               exclude_patterns: list[str]) -> list[Violation]:
        """File-level CRAP fallback when DCL provides no per-function line ranges."""
        violations: list[Violation] = []
        for file_abs, cc in file_complexity.items():
            rel_path = self._get_relative_path(Path(file_abs))
            if self._is_excluded(rel_path, exclude_patterns):
                continue
            line_hits = self._lookup_coverage(file_abs, lcov_by_file)
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

    def _cleanup_report_dir(self, report_dir: Path) -> None:
        if self.config.get('keep_report', False):
            return
        try:
            shutil.rmtree(report_dir)
        except Exception as e:
            self.logger.warning(f"Warning: could not delete {report_dir}: {e}")
