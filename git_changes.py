"""Git integration for changed files and changed source lines."""

import re
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


class GitNotAvailableError(RuntimeError):
    """Raised when git is missing or the command fails."""


@dataclass(frozen=True)
class DiffChanges:
    """Changed lines and new files, keyed by paths relative to the supplied root."""

    lines: Mapping[Path, frozenset[int]]
    new_files: frozenset[Path]

    def touches(self, file_path: Path, start_line: int, end_line: int) -> bool:
        """Return whether the function range contains a changed line."""
        return any(start_line <= line <= end_line for line in self.lines.get(file_path, ()))

    def has_changes(self, file_path: Path) -> bool:
        """Return whether the file is new or has changed lines."""
        return file_path in self.new_files or bool(self.lines.get(file_path))


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


def get_changed_lines(root: Path, base: str) -> DiffChanges:
    """Return changed new-side lines and new files relative to ``root`` since ``base``."""
    root = root.resolve()
    _run_git(root, 'rev-parse', '--verify', '--quiet', f'{base}^{{commit}}', operation='git rev-parse')
    diff = _run_git(
        root,
        '-c',
        'core.quotePath=false',
        'diff',
        '-U0',
        '-M',
        '--no-color',
        '--no-ext-diff',
        '--no-prefix',
        '--relative',
        base,
        operation='git diff',
    )
    parsed = _parse_diff_output(diff.decode('utf-8', errors='replace'))

    untracked = _run_git(
        root,
        'ls-files',
        '--others',
        '--exclude-standard',
        '-z',
        operation='git ls-files',
    )
    untracked_paths = {
        Path(item.decode('utf-8', errors='replace').replace('\\', '/'))
        for item in untracked.split(b'\0')
        if item
    }
    return DiffChanges(
        lines=parsed.lines,
        new_files=parsed.new_files | frozenset(untracked_paths),
    )


def _run_git(root: Path, *args: str, operation: str) -> bytes:
    """Run one Git command and translate unavailable or failed commands consistently."""
    cmd = ['git', '-C', str(root), *args]
    try:
        result = subprocess.run(cmd, capture_output=True, check=False)
    except FileNotFoundError as error:
        raise GitNotAvailableError("git executable not found in PATH") from error

    if result.returncode != 0:
        stderr = result.stderr.decode('utf-8', errors='replace').strip()
        detail = f": {stderr}" if stderr else " (invalid base commit or path is not a repository)"
        raise GitNotAvailableError(f"{operation} failed{detail}")
    return result.stdout


def _parse_diff_output(diff: str) -> DiffChanges:
    """Parse no-prefix unified diff output into changed new-side lines."""
    lines: dict[Path, set[int]] = {}
    new_files: set[Path] = set()
    deleted_file = False
    current_file: Path | None = None
    in_hunk = False

    for line in diff.splitlines():
        if line.startswith('diff --git '):
            current_file = None
            deleted_file = False
            in_hunk = False
        elif not in_hunk and line.startswith('--- '):
            deleted_file = line[4:].split('\t', 1)[0] == '/dev/null'
        elif not in_hunk and line.startswith('+++ '):
            path = line[4:].split('\t', 1)[0]
            current_file = None if path == '/dev/null' else Path(path.replace('\\', '/'))
            if current_file is not None and deleted_file:
                new_files.add(current_file)
            deleted_file = False
        elif line.startswith('@@ ') and current_file is not None:
            in_hunk = True
            match = re.match(r'@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@', line)
            if match is None:
                continue
            start = int(match.group(1))
            count = int(match.group(2) or '1')
            changed = range(start, start + count) if count else (start,)
            lines.setdefault(current_file, set()).update(changed)

    # Ignored untracked files and names Git still quotes with core.quotePath=false are
    # not represented reliably by this deliberately small parser; upgrade to -z parsing
    # if a real project needs either case.
    return DiffChanges(
        lines={path: frozenset(changed) for path, changed in lines.items()},
        new_files=frozenset(new_files),
    )


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
