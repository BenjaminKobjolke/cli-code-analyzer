"""Shared CRAP (Change Risk Anti-Pattern) score helpers.

CRAP(m) = complexity^2 * (1 - coverage)^3 + complexity

Reused by Dart and Python CRAP analyzers (the math functions plus
``CrapScoreMixin``, which holds the coverage-lookup / violation-building logic
common to both rules).
"""

import re
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

from models import Severity, Violation


def crap_score(complexity: float, covered_lines: int, total_lines: int) -> float:
    """Compute CRAP score for a function.

    Args:
        complexity: Cyclomatic complexity (>=1).
        covered_lines: Number of executable lines that were covered by tests.
        total_lines: Total executable lines.

    Returns:
        CRAP score. With zero executable lines, coverage is treated as 0.0.
    """
    cov = (covered_lines / total_lines) if total_lines > 0 else 0.0
    return complexity ** 2 * (1 - cov) ** 3 + complexity


def coverage_ratio(covered_lines: int, total_lines: int) -> float:
    """Coverage ratio in [0,1]; 0.0 when there are no executable lines."""
    if total_lines <= 0:
        return 0.0
    return covered_lines / total_lines


# Matches the CRAP violation message; the "(line N)" suffix is optional so the
# same pattern works for the Dart (file-level fallback omits line) and Python rules.
_CRAP_MSG_RE = re.compile(
    r"^CRAP=([\d.]+) \(complexity=([\d.]+), coverage=(\d+)%\) in '([^']*)'(?: \(line (\d+)\))?$"
)


class CrapScoreMixin:
    """Coverage-lookup and violation-building logic shared by the CRAP rules.

    The host class is a BaseRule subclass supplying ``rule_name``, ``config``,
    ``_get_relative_path``, ``_get_threshold_for_file`` and ``_write_violations_csv``.
    Subclasses provide the language-specific complexity + coverage collection and
    pass the resulting ``functions_by_file`` / ``coverage_by_file`` maps here.
    """

    def _build_function_violations(self, functions_by_file: dict[str, list[dict]],
                                   coverage_by_file: dict[str, dict[int, int]],
                                   exclude_patterns: list[str]) -> list[Violation]:
        violations: list[Violation] = []
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
        # Suffix-match fallback (handles relative/absolute path mismatch).
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
            rule_name=self.rule_name,
            severity=severity,
            message=f"CRAP={crap:.1f} (complexity={cc_disp}, coverage={cov_pct:.0f}%) in '{name}'{loc_suffix}",
            line=line,
        )

    def _write_csv(self, output_file: Path, violations: list[Violation]) -> None:
        def row_mapper(v: Violation) -> list[Any]:
            m = _CRAP_MSG_RE.match(v.message)
            if not m:
                return [v.file_path, v.line or '', '', '', '', '', v.severity.value]
            crap, cc, cov_pct, name, line = m.groups()
            return [v.file_path, line or v.line or '', name, cc, f"{cov_pct}%", crap, v.severity.value]

        self._write_violations_csv(
            output_file, violations,
            headers=['file', 'line', 'function', 'complexity', 'coverage', 'crap', 'severity'],
            row_mapper=row_mapper,
        )
