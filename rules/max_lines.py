"""
Max lines per file rule
"""

from pathlib import Path
from typing import List, Optional
from rules.base import BaseRule
from models import Violation, Severity


class MaxLinesRule(BaseRule):
    """Rule to check maximum lines per file"""

    def __init__(self, config: dict, base_path: Path = None, max_errors: Optional[int] = None, rules_file_path: str = None):
        super().__init__(config, base_path, max_errors, rules_file_path)
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

        # Get thresholds for this specific file (may use exceptions)
        thresholds = self._get_threshold_for_file(file_path, self.config)
        error_threshold = thresholds.get('error')
        warning_threshold = thresholds.get('warning')

        if error_threshold and line_count >= error_threshold:
            violations.append(Violation(
                file_path=relative_path,
                rule_name='max_lines_per_file',
                severity=Severity.ERROR,
                message=f"File has {line_count} lines (limit: {error_threshold})",
                line_count=line_count
            ))
        elif warning_threshold and line_count >= warning_threshold:
            violations.append(Violation(
                file_path=relative_path,
                rule_name='max_lines_per_file',
                severity=Severity.WARNING,
                message=f"File has {line_count} lines (warning: {warning_threshold})",
                line_count=line_count
            ))

        return violations
