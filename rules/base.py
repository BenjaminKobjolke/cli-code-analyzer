"""
Base rule class for all code analysis rules
"""

import csv
import platform
import shutil
import subprocess
from abc import ABC, abstractmethod
from collections.abc import Callable
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

from models import LogLevel, Severity, Violation


class BaseRule(ABC):
    """Abstract base class for all rules"""

    def __init__(self, config: dict, base_path: Path | None = None, log_level: LogLevel = LogLevel.ALL, max_errors: int | None = None, rules_file_path: str | None = None):
        self.config = config
        self.base_path = base_path
        self.log_level = log_level
        self.max_errors = max_errors
        self.rules_file_path = rules_file_path

    @abstractmethod
    def check(self, file_path: Path) -> list[Violation]:
        """
        Check the file against this rule

        Args:
            file_path: Path to the file to check

        Returns:
            List of violations found
        """

    def _get_relative_path(self, file_path: Path) -> str:
        """
        Get relative path from base path

        Args:
            file_path: Absolute path to the file

        Returns:
            Relative path as string
        """
        if self.base_path:
            try:
                return str(file_path.resolve().relative_to(self.base_path))
            except ValueError:
                # If file is not relative to base_path, return absolute path
                return str(file_path)
        return str(file_path)

    def _count_lines(self, file_path: Path) -> int:
        """
        Utility method to count lines in a file

        Args:
            file_path: Path to the file

        Returns:
            Number of lines in the file
        """
        try:
            with open(file_path, encoding='utf-8') as f:
                return sum(1 for _ in f)
        except Exception as e:
            print(f"Warning: Could not read {file_path}: {e}")
            return 0

    def _get_threshold_for_file(
        self,
        file_path: Path,
        threshold_config: dict[str, Any],
        metric_id: str | None = None,  # noqa: ARG002
    ) -> dict[str, int]:
        """Get thresholds for a file, checking for exceptions first.

        Args:
            file_path: Path to the file being checked
            threshold_config: Base threshold configuration
            metric_id: Optional metric ID (for dart_code_linter metrics)

        Returns:
            Dict with 'error' and 'warning' thresholds
        """
        # Check if there are exceptions defined
        exceptions = threshold_config.get('exceptions', [])

        if not exceptions:
            return {
                'error': threshold_config.get('error'),
                'warning': threshold_config.get('warning')
            }

        # Get various path representations for matching
        try:
            # Relative to --path (base_path)
            rel_path_to_base = self._get_relative_path(file_path)
        except Exception:
            rel_path_to_base = str(file_path)

        # Relative to rules.json location
        rel_path_to_rules = None
        if self.rules_file_path:
            try:
                rules_dir = Path(self.rules_file_path).parent
                rel_path_to_rules = str(Path(file_path).resolve().relative_to(rules_dir))
            except Exception:
                pass

        # Normalize path separators for comparison (handle Windows/Unix)
        rel_path_to_base_normalized = rel_path_to_base.replace('\\', '/')
        rel_path_to_rules_normalized = rel_path_to_rules.replace('\\', '/') if rel_path_to_rules else None

        # Get filename only
        filename_only = Path(file_path).name

        # Check each exception for a match
        for exception in exceptions:
            exception_pattern = exception.get('file', '')
            exception_pattern_normalized = exception_pattern.replace('\\', '/')

            # Try multiple matching strategies in order:
            # 1. Relative to --path (base_path)
            if self._match_file_path(rel_path_to_base_normalized, exception_pattern_normalized):
                return {
                    'error': exception.get('error', threshold_config.get('error')),
                    'warning': exception.get('warning', threshold_config.get('warning'))
                }

            # 2. Relative to rules.json location
            if rel_path_to_rules_normalized and self._match_file_path(rel_path_to_rules_normalized, exception_pattern_normalized):
                return {
                    'error': exception.get('error', threshold_config.get('error')),
                    'warning': exception.get('warning', threshold_config.get('warning'))
                }

            # 3. Filename only match
            if self._match_file_path(filename_only, exception_pattern_normalized):
                return {
                    'error': exception.get('error', threshold_config.get('error')),
                    'warning': exception.get('warning', threshold_config.get('warning'))
                }

        # No exception matched, return base thresholds
        return {
            'error': threshold_config.get('error'),
            'warning': threshold_config.get('warning')
        }

    def _match_file_path(self, file_path: str, pattern: str) -> bool:
        """Check if a file path matches a pattern.

        Supports:
        - Exact match: "services/preferences_service.dart"
        - Glob patterns: "services/*.dart", "**/test_*.dart"
        - Ends with: pattern "preferences_service.dart" matches "lib/services/preferences_service.dart"

        Args:
            file_path: Normalized file path (forward slashes)
            pattern: Pattern to match against (forward slashes)

        Returns:
            True if path matches pattern
        """
        # Try exact match first (most common case)
        if file_path == pattern:
            return True

        # Try glob pattern match
        if fnmatch(file_path, pattern):
            return True

        # Check if file ends with pattern (for relative patterns)
        # e.g., pattern "preferences_service.dart" matches "lib/services/preferences_service.dart"
        return file_path.endswith((pattern, '/' + pattern))

    def _map_severity(self, severity_str: str) -> Severity:
        """Map severity string to Severity enum.

        Args:
            severity_str: Severity string (INFO/WARNING/ERROR)

        Returns:
            Mapped Severity enum value
        """
        severity_map = {
            'INFO': Severity.INFO,
            'WARNING': Severity.WARNING,
            'ERROR': Severity.ERROR,
        }
        return severity_map.get(severity_str.upper(), Severity.WARNING)

    def _filter_violations_by_log_level(self, violations: list[Violation]) -> list[Violation]:
        """Filter violations based on log level.

        Args:
            violations: List of all violations

        Returns:
            Filtered list of violations based on log level
        """
        if self.log_level == LogLevel.ALL:
            return violations

        filtered = []
        for violation in violations:
            if (
                (self.log_level == LogLevel.ERROR and violation.severity != Severity.ERROR)
                or (self.log_level == LogLevel.WARNING and violation.severity not in (Severity.ERROR, Severity.WARNING))
            ):
                continue
            filtered.append(violation)

        return filtered

    def _run_subprocess(self, cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
        """Run subprocess with platform-appropriate settings.

        Args:
            cmd: Command and arguments
            cwd: Working directory

        Returns:
            CompletedProcess result
        """
        use_shell = platform.system() == 'Windows'
        return subprocess.run(
            cmd, cwd=cwd, capture_output=True,
            encoding='utf-8', errors='replace', check=False, shell=use_shell
        )

    def _get_tool_path(self, tool_name: str, get_method: Callable, prompt_method: Callable) -> str | None:
        """Get tool path from PATH, settings, or prompt user.

        Args:
            tool_name: Name of tool (e.g., 'dart', 'flutter', 'pmd')
            get_method: Settings method to get saved path
            prompt_method: Settings method to prompt and save path

        Returns:
            Path to tool executable or None
        """
        # Check if tool is in PATH
        tool_in_path = shutil.which(tool_name)
        if tool_in_path:
            return tool_in_path

        # Check settings
        tool_path = get_method()
        if not tool_path:
            tool_path = prompt_method()
            if not tool_path:
                return None

        # Validate path exists
        if not Path(tool_path).exists():
            print(f"Error: {tool_name} executable not found at: {tool_path}")
            return None

        return tool_path

    def _find_pubspec(self) -> Path | None:
        """Find pubspec.yaml in base_path or parent directory.

        Returns:
            Path to directory containing pubspec.yaml, or None
        """
        pubspec_path = self.base_path / 'pubspec.yaml'
        if not pubspec_path.exists():
            pubspec_path = self.base_path.parent / 'pubspec.yaml'
        if not pubspec_path.exists():
            return None
        return pubspec_path.parent

    def _write_violations_csv(self, output_file: Path, violations: list[Violation],
                               headers: list[str], row_mapper: Callable[[Violation], list]) -> None:
        """Write violations to CSV file with max_errors limit.

        Args:
            output_file: Path to output CSV file
            violations: List of violations
            headers: CSV column headers
            row_mapper: Function to convert Violation to CSV row list
        """
        if not violations:
            return

        # Sort by severity (ERROR first) and apply max_errors limit
        severity_order = {Severity.ERROR: 0, Severity.WARNING: 1, Severity.INFO: 2}
        sorted_violations = sorted(violations, key=lambda v: severity_order.get(v.severity, 3))

        if self.max_errors and len(sorted_violations) > self.max_errors:
            sorted_violations = sorted_violations[:self.max_errors]

        try:
            with open(output_file, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                for v in sorted_violations:
                    writer.writerow(row_mapper(v))
            print(f"Report saved to: {output_file}")
        except Exception as e:
            print(f"Error writing CSV: {e}")
