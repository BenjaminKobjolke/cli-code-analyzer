"""Track threshold values that matched file exceptions keep quiet."""

from pathlib import Path
from typing import Any

from exception_baseline import BaselineKey


class ExceptionGrowthMixin:
    """Record measured values when an exception suppresses a base-threshold finding."""

    def _track_exception_growth(
        self,
        file_path: Path,
        threshold_config: dict[str, Any],
        metric: str,
        value: int | float,
        function: str | None = None,
        *,
        inverse: bool = False,
    ) -> None:
        """Observe a value only when a matching exception makes it quiet."""
        baseline = self.ctx.exception_baseline
        if baseline is None:
            return

        base = self._build_threshold_dict(None, threshold_config)
        effective = self._get_threshold_for_file(file_path, threshold_config, metric)
        compare = (
            (lambda current, limit: current <= limit)
            if inverse
            else (lambda current, limit: current >= limit)
        )
        if not _hits_threshold(value, base, compare) or _hits_threshold(
            value, effective, compare
        ):
            return

        relative_path = self._get_relative_path(file_path).replace("\\", "/")
        baseline.observe(
            BaselineKey(
                rule=self.rule_name or self.__class__.__name__,
                file=relative_path,
                metric=metric,
                function=function,
            ),
            value,
        )

    def _track_suppressed_value(
        self,
        file_path: Path,
        metric: str,
        value: int | float,
        function: str,
    ) -> None:
        """Observe a value hidden by a supported in-code suppression."""
        baseline = self.ctx.exception_baseline
        if baseline is None:
            return

        relative_path = self._get_relative_path(file_path).replace("\\", "/")
        baseline.observe(
            BaselineKey(
                rule=self.rule_name or self.__class__.__name__,
                file=relative_path,
                metric=metric,
                function=function,
            ),
            value,
        )


def _hits_threshold(value, thresholds: dict[str, float | None], compare) -> bool:
    """Whether a normal error, warning, or info threshold reports this value."""
    return any(
        limit is not None and compare(value, limit)
        for limit in (
            thresholds.get("error"),
            thresholds.get("warning"),
            thresholds.get("info"),
        )
    )
