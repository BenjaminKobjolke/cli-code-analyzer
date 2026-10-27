"""CSV reporting shared by analyzer rules."""

import csv
from collections.abc import Callable
from pathlib import Path

from models import Severity, Violation


class ViolationReportMixin:
    """Write ordered rule violations to CSV."""

    max_errors: int | None

    def _write_violations_csv(
        self, output_file: Path, violations: list[Violation], headers: list[str], row_mapper: Callable
    ) -> None:
        """Write violations to CSV, sorted by severity, limited by max_errors."""
        if not violations:
            return

        severity_order = {Severity.ERROR: 0, Severity.WARNING: 1, Severity.INFO: 2}
        sorted_violations = sorted(violations, key=lambda v: severity_order.get(v.severity, 3))
        if self.max_errors and len(sorted_violations) > self.max_errors:
            sorted_violations = sorted_violations[:self.max_errors]

        try:
            with open(output_file, 'w', encoding='utf-8', newline='') as file:
                writer = csv.writer(file)
                writer.writerow(headers)
                for violation in sorted_violations:
                    writer.writerow(row_mapper(violation))
            self.logger.info(f"Report saved to: {output_file}")
        except Exception as error:
            self.logger.error(f"Error writing CSV: {error}")
