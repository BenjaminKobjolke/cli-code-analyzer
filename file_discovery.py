"""
File discovery based on language
"""

import fnmatch
from pathlib import Path
from typing import ClassVar

# Default exclude patterns per language
DEFAULT_EXCLUDE_PATTERNS = {
    'flutter': ['*.g.dart', '*.freezed.dart'],
    'python': ['venv/**', '.venv/**', '__pycache__/**', '*.pyc', 'env/**', '.git/**'],
}


class FileDiscovery:
    """Discovers files to analyze based on language"""

    LANGUAGE_EXTENSIONS: ClassVar[dict[str, list[str]]] = {
        'flutter': ['.dart'],
        'python': ['.py'],
    }

    def __init__(self, language: str, path: str, exclude_patterns: list[str] | None = None):
        self.language = language.lower()
        self.path = Path(path)
        # Use provided patterns or fall back to defaults for the language
        if exclude_patterns is not None:
            self.exclude_patterns = exclude_patterns
        else:
            self.exclude_patterns = DEFAULT_EXCLUDE_PATTERNS.get(self.language, [])

    def _get_extensions(self) -> list[str]:
        """Get file extensions for the specified language"""
        return self.LANGUAGE_EXTENSIONS.get(self.language, [])

    def discover(self) -> list[Path]:
        """Discover all files to analyze"""
        extensions = self._get_extensions()

        if not extensions:
            raise ValueError(f"Unsupported language: {self.language}")

        files = []

        if self.path.is_file():
            # Single file
            if any(str(self.path).endswith(ext) for ext in extensions):
                files.append(self.path)
        else:
            # Directory - find all matching files recursively
            for ext in extensions:
                files.extend(self.path.rglob(f'*{ext}'))

        # Filter out excluded files
        files = [f for f in files if not self._is_excluded(f)]

        return sorted(files)

    def _is_excluded(self, file_path: Path) -> bool:
        """Check if a file matches any exclusion pattern.

        Args:
            file_path: Path to check

        Returns:
            True if file should be excluded, False otherwise
        """
        if not self.exclude_patterns:
            return False

        # Get path relative to base for matching
        try:
            rel_path = file_path.relative_to(self.path)
        except ValueError:
            # File is not relative to base path, use absolute
            rel_path = file_path

        # Convert to string with forward slashes for consistent matching
        path_str = str(rel_path).replace('\\', '/')

        for pattern in self.exclude_patterns:
            # Normalize pattern
            pattern = pattern.replace('\\', '/')

            # Handle directory patterns like venv/** or venv/**/*
            if pattern.endswith(('/**', '/**/*')):
                # Extract the directory prefix
                dir_prefix = pattern.split('/**')[0]
                # Check if path starts with this directory
                if path_str.startswith(dir_prefix + '/') or path_str == dir_prefix:
                    return True
            elif '**' in pattern:
                # General glob pattern with **
                if fnmatch.fnmatch(path_str, pattern):
                    return True
            else:
                # Simple pattern (e.g., *.pyc)
                if fnmatch.fnmatch(path_str, pattern) or fnmatch.fnmatch(file_path.name, pattern):
                    return True

        return False
