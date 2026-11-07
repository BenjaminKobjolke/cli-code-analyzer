"""
File discovery based on language
"""

import fnmatch
from pathlib import Path
from typing import ClassVar

from path_utils import resolve_exclude_patterns

# Default exclude patterns per language
DEFAULT_EXCLUDE_PATTERNS = {
    'flutter': ['*.g.dart', '*.freezed.dart', '.dart_tool/**', '.fvm/**', 'build/**'],
    'python': ['venv/**', '.venv/**', '__pycache__/**', '*.pyc', 'env/**', '.git/**'],
    'php': ['vendor/**', 'node_modules/**', '.git/**', '.phpstan-cache/**'],
    'csharp': ['bin/**', 'obj/**', '.vs/**', 'packages/**', 'node_modules/**', '.git/**'],
    'javascript': ['node_modules/**', 'dist/**', 'build/**', 'coverage/**', '.git/**'],
    'svelte': ['node_modules/**', 'dist/**', 'build/**', '.svelte-kit/**', '.git/**'],
    'autohotkey': ['.git/**'],
    'cpp': ['.pio/**', 'build/**', '.git/**'],
    'kotlin': ['build/**', '.gradle/**', '.idea/**', '.git/**'],
    'contract': [
        '.git/**', '.claude/**', 'node_modules/**', 'graphify-out/**', 'tickets/**',
        'code_analysis_results/**', 'tmp/**', 'coding-rules.json',
    ],
}


def matches_exclude_pattern(rel_path: str, patterns: list[str]) -> bool:
    """Return whether a base-relative POSIX path matches an exclusion pattern."""
    path_str = rel_path.replace('\\', '/')
    file_name = path_str.rsplit('/', 1)[-1]

    for pattern in patterns:
        pattern = pattern.replace('\\', '/')

        # Directory forms match a complete segment at any depth, including root.
        if pattern.endswith(('/**', '/**/*')):
            dir_prefix = pattern.split('/**')[0]
            if dir_prefix.startswith('**/'):
                dir_prefix = dir_prefix[3:]
            if dir_prefix and (
                path_str == dir_prefix
                or path_str.startswith(dir_prefix + '/')
                or ('/' + dir_prefix + '/') in ('/' + path_str + '/')
            ):
                return True
        elif '**' in pattern:
            if fnmatch.fnmatch(path_str, pattern):
                return True
        elif fnmatch.fnmatch(path_str, pattern) or fnmatch.fnmatch(file_name, pattern):
            return True

    return False


class FileDiscovery:
    """Discovers files to analyze based on language"""

    LANGUAGE_EXTENSIONS: ClassVar[dict[str, list[str]]] = {
        'flutter': ['.dart'],
        'python': ['.py'],
        'php': ['.php'],
        'csharp': ['.cs'],
        'javascript': ['.js', '.mjs', '.cjs', '.ts', '.tsx', '.jsx'],
        'svelte': ['.svelte'],
        'autohotkey': ['.ahk', '.ah2', '.ahk2'],
        'cpp': ['.ino', '.cpp', '.h', '.hpp', '.c', '.cc'],
        'kotlin': ['.kt', '.kts'],
        'contract': ['.json'],
    }

    def __init__(self, languages: str | list[str], path: str,
                 exclude_patterns: list[str] | dict[str, list[str]] | None = None):
        if isinstance(languages, str):
            languages = [languages]
        self.languages = [lang.lower() for lang in languages]
        self.path = Path(path)
        # rules.json may give a flat list or a dict keyed by language; both
        # arrive here unnormalized. Language defaults (generated files, tool
        # caches) always apply; configured patterns add to them rather than
        # replace them, so listing a cache dir never re-enables *.g.dart.
        self.exclude_patterns = resolve_exclude_patterns(DEFAULT_EXCLUDE_PATTERNS, self.languages)
        for pattern in resolve_exclude_patterns(exclude_patterns, self.languages):
            if pattern not in self.exclude_patterns:
                self.exclude_patterns.append(pattern)

    def _get_extensions(self) -> list[str]:
        """Get file extensions for all requested languages"""
        extensions = []
        for lang in self.languages:
            for ext in self.LANGUAGE_EXTENSIONS.get(lang, []):
                if ext not in extensions:
                    extensions.append(ext)
        return extensions

    def discover(self) -> list[Path]:
        """Discover all files to analyze"""
        extensions = self._get_extensions()

        if not extensions:
            raise ValueError(f"Unsupported language(s): {', '.join(self.languages)}")

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
        # Get path relative to base for matching
        try:
            rel_path = file_path.relative_to(self.path)
        except ValueError:
            # File is not relative to base path, use absolute
            rel_path = file_path

        return matches_exclude_pattern(str(rel_path), self.exclude_patterns)
