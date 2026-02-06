"""
Dart test coverage analyzer - runs tests and checks coverage against thresholds.
"""

import re
from pathlib import Path

from models import LogLevel, Severity, Violation
from rules.base import BaseRule
from settings import Settings


class DartTestCoverageRule(BaseRule):
    """Run Flutter tests and check coverage against configurable thresholds."""

    def __init__(self, config: dict, base_path: Path | None = None, output_folder: Path | None = None, log_level: LogLevel = LogLevel.ALL, max_errors: int | None = None, rules_file_path: str | None = None):
        super().__init__(config, base_path, log_level, max_errors, rules_file_path)
        self.output_folder = output_folder
        self.settings = Settings()
        self._executed = False

    def check(self, _file_path: Path) -> list[Violation]:
        if self._executed:
            return []
        self._executed = True

        print("\nRunning dart test coverage check...")

        project_root = self._find_pubspec()
        if not project_root:
            print("Warning: pubspec.yaml not found, skipping dart_test_coverage")
            return []

        run_tests = self.config.get('run_tests', True)
        lcov_path = self.config.get('lcov_path', 'coverage/lcov.info')
        test_timeout = self.config.get('test_timeout', 600)
        overall_cfg = self.config.get('overall_coverage', {'warning': 60, 'error': 40})
        per_file_cfg = self.config.get('per_file_coverage', {'warning': 50, 'error': 20})
        exclude_patterns = self.config.get('exclude_patterns', ['*.g.dart', '*.freezed.dart'])

        lcov_file = project_root / lcov_path

        # Run tests with coverage if configured
        if run_tests:
            success = self._run_flutter_test(project_root, test_timeout)
            if not success:
                print("Warning: Flutter test run failed, attempting to parse existing coverage data")

        if not lcov_file.exists():
            print(f"Warning: Coverage file not found at {lcov_file}")
            if run_tests:
                print("Tests may have failed to produce coverage output")
            return []

        # Parse LCOV data
        coverage_data = self._parse_lcov(lcov_file, exclude_patterns)
        if not coverage_data:
            print("No coverage data found")
            return []

        violations = []

        # Calculate overall coverage
        total_lines = sum(d['total'] for d in coverage_data.values())
        covered_lines = sum(d['covered'] for d in coverage_data.values())
        overall_pct = (covered_lines / total_lines * 100) if total_lines > 0 else 0

        # Check overall coverage thresholds
        overall_warning = overall_cfg.get('warning', 60)
        overall_error = overall_cfg.get('error', 40)

        if overall_pct < overall_error:
            violations.append(Violation(
                file_path='project',
                rule_name='dart_test_coverage',
                severity=Severity.ERROR,
                message=f"Overall test coverage is {overall_pct:.1f}% (error threshold: {overall_error}%)"
            ))
        elif overall_pct < overall_warning:
            violations.append(Violation(
                file_path='project',
                rule_name='dart_test_coverage',
                severity=Severity.WARNING,
                message=f"Overall test coverage is {overall_pct:.1f}% (warning threshold: {overall_warning}%)"
            ))

        # Check per-file coverage thresholds
        per_file_warning = per_file_cfg.get('warning', 50)
        per_file_error = per_file_cfg.get('error', 20)

        for file_path, data in sorted(coverage_data.items()):
            file_pct = (data['covered'] / data['total'] * 100) if data['total'] > 0 else 0

            if file_pct < per_file_error:
                violations.append(Violation(
                    file_path=file_path,
                    rule_name='dart_test_coverage',
                    severity=Severity.ERROR,
                    message=f"Test coverage is {file_pct:.1f}% ({data['covered']}/{data['total']} lines) - error threshold: {per_file_error}%"
                ))
            elif file_pct < per_file_warning:
                violations.append(Violation(
                    file_path=file_path,
                    rule_name='dart_test_coverage',
                    severity=Severity.WARNING,
                    message=f"Test coverage is {file_pct:.1f}% ({data['covered']}/{data['total']} lines) - warning threshold: {per_file_warning}%"
                ))

        violations = self._filter_violations_by_log_level(violations)

        if violations:
            print(f"\nDart test coverage found {len(violations)} issue(s) (overall: {overall_pct:.1f}%)")
        else:
            print(f"\nDart test coverage: All thresholds met (overall: {overall_pct:.1f}%)")

        if self.output_folder and violations:
            output_file = self.output_folder / 'dart_test_coverage.csv'
            self._write_violations_csv(
                output_file, violations,
                ['file_path', 'total_lines', 'covered_lines', 'coverage_pct', 'threshold', 'severity'],
                lambda v: self._parse_violation_data(v, coverage_data)
            )

        return violations

    def _run_flutter_test(self, project_root: Path, timeout: int) -> bool:
        """Run flutter test --coverage."""
        print("Running flutter test --coverage (this may take a while)...")

        flutter_cmd = self._get_flutter_command(self.settings.get_flutter_path, self.settings.prompt_and_save_flutter_path)
        if not flutter_cmd:
            return False

        try:
            result = self._run_subprocess(
                flutter_cmd + ['test', '--coverage'],
                project_root,
                timeout=timeout
            )
            if result.returncode != 0:
                stderr = result.stderr.strip() if result.stderr else ''
                if stderr:
                    print(f"Flutter test stderr: {stderr[:500]}")
                return False
            return True
        except Exception as e:
            print(f"Error running flutter test: {e}")
            return False

    def _parse_lcov(self, lcov_file: Path, exclude_patterns: list[str]) -> dict:
        """Parse LCOV coverage file.

        Returns:
            Dict mapping file paths to {'total': int, 'covered': int}
        """
        coverage = {}
        current_file = None
        current_total = 0
        current_covered = 0

        try:
            content = lcov_file.read_text(encoding='utf-8', errors='replace')
        except Exception as e:
            print(f"Error reading LCOV file: {e}")
            return {}

        for line in content.split('\n'):
            line = line.strip()

            if line.startswith('SF:'):
                current_file = line[3:]
                current_total = 0
                current_covered = 0
            elif line.startswith('DA:'):
                parts = line[3:].split(',')
                if len(parts) >= 2:
                    current_total += 1
                    try:
                        if int(parts[1]) > 0:
                            current_covered += 1
                    except ValueError:
                        pass
            elif line == 'end_of_record' and current_file:
                # Check exclusions
                excluded = False
                for pattern in exclude_patterns:
                    if Path(current_file).match(pattern):
                        excluded = True
                        break

                if not excluded and current_total > 0:
                    # Normalize file path
                    try:
                        rel_path = self._get_relative_path(Path(current_file))
                    except Exception:
                        rel_path = current_file

                    coverage[rel_path] = {
                        'total': current_total,
                        'covered': current_covered
                    }

                current_file = None

        return coverage

    def _parse_violation_data(self, v: Violation, coverage_data: dict) -> list:
        """Parse violation message into CSV columns."""
        msg = v.message
        total = 0
        covered = 0
        pct = 0.0
        threshold = ''

        if v.file_path in coverage_data:
            data = coverage_data[v.file_path]
            total = data['total']
            covered = data['covered']

        pct_match = re.search(r'(\d+\.\d+)%', msg)
        if pct_match:
            pct = float(pct_match.group(1))

        threshold_match = re.search(r'threshold: (\d+)%', msg)
        if threshold_match:
            threshold = threshold_match.group(1)

        return [v.file_path, total, covered, f"{pct:.1f}", threshold, v.severity.name]
