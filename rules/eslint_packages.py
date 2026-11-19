"""ESLint config discovery and the per-package targets of a workspace run.

A workspace (pnpm, npm, yarn) often has no ESLint config at its root: each
package carries its own flat config and `npm run lint` runs per package. ESLint
started at such a root aborts with "couldn't find an eslint.config.* file", so
the rule runs once per package instead — in the package's directory, with the
package's own ESLint where it has one.
"""

import os
from dataclasses import dataclass
from pathlib import Path

FLAT_CONFIG_FILES = (
    'eslint.config.js',
    'eslint.config.mjs',
    'eslint.config.cjs',
    'eslint.config.ts',
    'eslint.config.mts',
    'eslint.config.cts',
)

LEGACY_CONFIG_FILES = (
    '.eslintrc.js',
    '.eslintrc.cjs',
    '.eslintrc.yaml',
    '.eslintrc.yml',
    '.eslintrc.json',
    '.eslintrc',
)

# Build output and dependencies: a config in there belongs to a package's
# published files, not to a workspace member.
SKIP_DIRECTORIES = {'node_modules', 'dist', 'build', 'coverage', 'out'}


@dataclass(frozen=True)
class EslintTarget:
    """One ESLint run: the directory it starts in and the executable it uses."""
    root: Path
    eslint_path: str


def has_flat_config(directory: Path) -> bool:
    """Whether `directory` holds an ESLint flat config of its own."""
    return any((directory / name).is_file() for name in FLAT_CONFIG_FILES)


def find_eslint_package_roots(base_path: Path) -> list[Path]:
    """Directories below base_path with their own flat config, not nested in another."""
    roots = []

    def raise_walk_error(error: OSError) -> None:
        raise error

    for root, dirs, _ in os.walk(base_path, onerror=raise_walk_error):
        current = Path(root)
        if current != base_path and has_flat_config(current):
            roots.append(current)
            dirs.clear()
            continue
        dirs[:] = [name for name in dirs
                   if name not in SKIP_DIRECTORIES and not name.startswith('.')]

    return sorted(roots)
