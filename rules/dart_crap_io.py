"""Dart-specific I/O for the CRAP analyzer: dart_code_linter metrics and LCOV.

Mixed into DartCrapScoreRule. Kept separate so dart_crap_score.py stays focused
on orchestration and violation construction. The host class supplies
``config``, ``logger``, ``project_root``, ``settings`` and the BaseRule helpers.
"""

import contextlib
import json
from pathlib import Path


class DartCrapIOMixin:
    """dart_code_linter metrics parsing and LCOV coverage reading."""

    # ----- DCL invocation & parsing -------------------------------------------------

    def _run_dcl_metrics(self, dart_cmd: list[str], report_dir: Path) -> Path | None:
        analyze_path = self.config.get('analyze_path', 'lib')
        self.logger.info(f"Running dart_code_linter for CRAP on '{analyze_path}'...")
        cmd = [
            *dart_cmd,
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
                    with contextlib.suppress(TypeError, ValueError):
                        file_complexity[file_abs] = float(metric.get('value', 0))

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
            result = self._run_subprocess([*flutter_cmd, 'test', '--coverage'], self.project_root, timeout=timeout)
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
