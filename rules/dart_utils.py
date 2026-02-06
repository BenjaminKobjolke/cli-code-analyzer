"""
Shared Dart/Flutter utilities for import parsing and file collection.
"""

import re
from pathlib import Path

import yaml


def get_package_name(project_root: Path) -> str | None:
    """Read the package name from pubspec.yaml.

    Args:
        project_root: Path to the project root containing pubspec.yaml

    Returns:
        Package name string or None if not found
    """
    pubspec_path = project_root / 'pubspec.yaml'
    if not pubspec_path.exists():
        return None
    try:
        with open(pubspec_path, encoding='utf-8') as f:
            data = yaml.safe_load(f)
        return data.get('name') if data else None
    except Exception:
        return None


def parse_imports(file_path: Path) -> list[dict]:
    """Parse import/export/part statements from a Dart file.

    Args:
        file_path: Path to the .dart file

    Returns:
        List of dicts with keys: type ('import'|'export'|'part'), uri, line
    """
    results = []
    pattern = re.compile(
        r"^\s*(import|export|part)\s+'([^']+)'\s*;", re.MULTILINE
    )
    try:
        content = file_path.read_text(encoding='utf-8', errors='replace')
    except Exception:
        return results

    for match in pattern.finditer(content):
        stmt_type = match.group(1)
        uri = match.group(2)
        line = content[:match.start()].count('\n') + 1
        results.append({'type': stmt_type, 'uri': uri, 'line': line})

    return results


def resolve_package_import(uri: str, package_name: str, project_root: Path) -> Path | None:
    """Resolve a package: import URI to a local file path.

    Only resolves imports for the project's own package.

    Args:
        uri: The import URI (e.g., 'package:myapp/widgets/foo.dart')
        package_name: The project's package name from pubspec.yaml
        project_root: Path to the project root

    Returns:
        Resolved Path or None if not a local package import
    """
    prefix = f'package:{package_name}/'
    if not uri.startswith(prefix):
        return None
    relative = uri[len(prefix):]
    resolved = project_root / 'lib' / relative
    return resolved if resolved.exists() else None


def resolve_relative_import(uri: str, importing_file: Path) -> Path | None:
    """Resolve a relative import URI to an absolute file path.

    Args:
        uri: The relative import URI (e.g., '../models/user.dart')
        importing_file: Path to the file containing the import

    Returns:
        Resolved Path or None if the file doesn't exist
    """
    if uri.startswith('dart:') or uri.startswith('package:'):
        return None
    resolved = (importing_file.parent / uri).resolve()
    return resolved if resolved.exists() else None


def collect_dart_files(directory: Path, exclude_patterns: list[str] | None = None) -> list[Path]:
    """Collect all .dart files in a directory, applying exclusion patterns.

    Args:
        directory: Directory to search
        exclude_patterns: List of glob patterns to exclude (e.g., ['*.g.dart', '*.freezed.dart'])

    Returns:
        List of Path objects for matching .dart files
    """
    if not directory.exists():
        return []

    exclude_patterns = exclude_patterns or []
    files = []

    for dart_file in directory.rglob('*.dart'):
        excluded = False
        for pattern in exclude_patterns:
            if dart_file.match(pattern):
                excluded = True
                break
        if not excluded:
            files.append(dart_file)

    return sorted(files)
