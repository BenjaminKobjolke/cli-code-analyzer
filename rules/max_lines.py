"""
Max lines per file rule
"""

from pathlib import Path
from typing import List
from rules.base import BaseRule
from models import Violation, Severity


class MaxLinesRule(BaseRule):
    """Rule to check maximum lines per file"""

    def __init__(self, config: dict, base_path: Path = None):
        super().__init__(config, base_path)
        self.warning_threshold = config.get('warning', 300)
        self.error_threshold = config.get('error', 500)

    def check(self, file_path: Path) -> List[Violation]:
        """
        Check if file exceeds line count thresholds

        Args:
            file_path: Path to the file to check

        Returns:
            List of violations (empty if no violations)
        """
        violations = []
        line_count = self._count_lines(file_path)
        relative_path = self._get_relative_path(file_path)

        if line_count >= self.error_threshold:
            violations.append(Violation(
                file_path=relative_path,
                rule_name='max_lines_per_file',
                severity=Severity.ERROR,
                message=f"File has {line_count} lines (limit: {self.error_threshold})",
                line_count=line_count
            ))
        elif line_count >= self.warning_threshold:
            violations.append(Violation(
                file_path=relative_path,
                rule_name='max_lines_per_file',
                severity=Severity.WARNING,
                message=f"File has {line_count} lines (warning: {self.warning_threshold})",
                line_count=line_count
            ))

        return violations
