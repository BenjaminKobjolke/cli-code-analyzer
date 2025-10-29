"""
File discovery based on language
"""

from pathlib import Path
from typing import List


class FileDiscovery:
    """Discovers files to analyze based on language"""

    LANGUAGE_EXTENSIONS = {
        'flutter': ['.dart'],
        'python': ['.py'],
    }

    def __init__(self, language: str, path: str):
        self.language = language.lower()
        self.path = Path(path)

    def _get_extensions(self) -> List[str]:
        """Get file extensions for the specified language"""
        return self.LANGUAGE_EXTENSIONS.get(self.language, [])

    def discover(self) -> List[Path]:
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

        return sorted(files)
