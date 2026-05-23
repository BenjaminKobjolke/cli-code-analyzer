"""Shared CRAP (Change Risk Anti-Pattern) score helper.

CRAP(m) = complexity^2 * (1 - coverage)^3 + complexity

Reused by Dart and Python CRAP analyzers.
"""


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
