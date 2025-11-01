"""
Base rule class for all code analysis rules
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional
from models import Violation


class BaseRule(ABC):
    """Abstract base class for all rules"""

    def __init__(self, config: dict, base_path: Path = None, max_errors: Optional[int] = None):
        self.config = config
        self.base_path = base_path
        self.max_errors = max_errors

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
