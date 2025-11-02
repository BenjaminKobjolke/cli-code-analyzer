"""
Base rule class for all code analysis rules
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional, Dict, Any
from fnmatch import fnmatch
from models import Violation


class BaseRule(ABC):
    """Abstract base class for all rules"""

    def __init__(self, config: dict, base_path: Path = None, max_errors: Optional[int] = None, rules_file_path: str = None):
        self.config = config
        self.base_path = base_path
        self.max_errors = max_errors
        self.rules_file_path = rules_file_path

    @abstractmethod
    def check(self, file_path: Path) -> List[Violation]:
        """
        Check the file against this rule

        Args:
            file_path: Path to the file to check

        Returns:
            List of violations found
        """
        pass

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
            with open(file_path, 'r', encoding='utf-8') as f:
                return sum(1 for _ in f)
        except Exception as e:
            print(f"Warning: Could not read {file_path}: {e}")
            return 0

    def _get_threshold_for_file(
        self,
        file_path: Path,
        threshold_config: Dict[str, Any],
        metric_id: str = None
    ) -> Dict[str, int]:
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
        except:
            rel_path_to_base = str(file_path)

        # Relative to rules.json location
        rel_path_to_rules = None
        if self.rules_file_path:
            try:
                rules_dir = Path(self.rules_file_path).parent
                rel_path_to_rules = str(Path(file_path).resolve().relative_to(rules_dir))
            except:
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
        if file_path.endswith(pattern) or file_path.endswith('/' + pattern):
            return True

        return False
