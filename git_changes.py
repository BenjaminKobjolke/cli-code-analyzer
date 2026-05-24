"""Git integration: discover files new or modified vs HEAD."""

import subprocess
from pathlib import Path


class GitNotAvailableError(RuntimeError):
    """Raised when git is missing or the command fails."""


def find_repo_root(path: Path) -> Path | None:
    """Walk up from `path` looking for a `.git` entry. Return repo root or None."""
    current = path.resolve()
    if current.is_file():
        current = current.parent
    for candidate in [current, *current.parents]:
        if (candidate / '.git').exists():
            return candidate
    return None


def get_changed_files(repo_root: Path) -> set[Path]:
    """Return absolute paths of files new or modified vs HEAD (incl. untracked).

    Excludes deleted files. For renames, returns the new path only.
    """
    cmd = ['git', '-C', str(repo_root), 'status', '--porcelain=v1', '-z', '--untracked-files=all']
    try:
        result = subprocess.run(cmd, capture_output=True, check=False)
    except FileNotFoundError as e:
        raise GitNotAvailableError("git executable not found in PATH") from e

    if result.returncode != 0:
        stderr = result.stderr.decode('utf-8', errors='replace').strip()
        raise GitNotAvailableError(f"git status failed: {stderr}")

    return _parse_porcelain_z(result.stdout, repo_root)


def _parse_porcelain_z(raw: bytes, repo_root: Path) -> set[Path]:
    """Parse NUL-separated `git status --porcelain=v1 -z` output."""
    text = raw.decode('utf-8', errors='replace')
    if not text:
        return set()

    tokens = text.split('\0')
    if tokens and tokens[-1] == '':
        tokens.pop()

    files: set[Path] = set()
    i = 0
    while i < len(tokens):
        entry = tokens[i]
        if len(entry) < 3:
            i += 1
            continue
        xy = entry[:2]
        path = entry[3:]
        i += 1

        # Rename/copy records: porcelain v1 with -z emits `XY new\0old`.
        # We want `new` (already captured); consume the `old` token.
        if xy[0] in ('R', 'C') or xy[1] in ('R', 'C'):
            if i < len(tokens):
                i += 1
            files.add((repo_root / path).resolve())
            continue

        # Skip pure deletes (no file on disk).
        if xy == ' D' or xy == 'D ' or xy == 'DD':
            continue
        # Mixed states with D in one slot but content in the other (e.g. 'AD', 'MD'):
        # the working-tree side is gone, skip.
        if xy[1] == 'D':
            continue

        files.add((repo_root / path).resolve())

    return files
