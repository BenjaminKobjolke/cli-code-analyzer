"""Filter-file scoping helpers, mixed into BaseRule.

Provides the logic that maps an active ``--only-changed`` / ``--file`` filter to
the file-path arguments and bounded commands a project-wide tool should scan. Kept separate from
base.py so the core base class stays focused. The host class supplies
``filter_files`` and ``base_path`` (BaseRule sets both in __init__).
"""

import json
import subprocess
from pathlib import Path
from typing import Any

# ponytail: one tool start per roughly 70 files; revisit for thousands of changed files.
MAX_COMMAND_CHARS = 6000


class ToolOutputError(Exception):
    """A tool could not run or did not produce trustworthy output."""


class FilterScopeMixin:
    """Resolve the active file filter to tool arguments."""

    def _filtered_paths(self, extensions: tuple[str, ...] | None = None) -> list[Path] | None:
        """Absolute paths of the filter set under base_path, matching extensions.

        Returns None when no filter is active (caller runs whole-project mode).
        Returns [] when a filter is set but no file matches this language; the
        caller MUST short-circuit, since passing zero paths makes most CLIs fall
        back to scanning the CWD. Deleted files drop out (only existing paths).
        """
        if self.filter_files is None or self.base_path is None:
            return None
        paths: list[Path] = []
        for rel in self.filter_files:
            if extensions and not rel.lower().endswith(extensions):
                continue
            p = self.base_path / rel
            if p.exists():
                paths.append(p)
        return paths

    def _scope_args(self, extensions: tuple[str, ...] | None = None,
                    whole_project: list[str] | None = None) -> list[str] | None:
        """CLI path args for a project-wide tool. Single source for the scope branch.

        Returns None  => filter set but no matching files; caller does `return self._ok([])`.
        Returns a list => filtered file paths, or the `whole_project` fallback when no filter.
        `whole_project` is [] for cwd-based tools (dart/flutter) and
        [str(self.base_path)] for path-arg tools (ruff/eslint/phpstan).
        """
        targets = self._filtered_paths(extensions)
        if targets is None:
            return whole_project or []
        if not targets:
            return None
        return [str(p) for p in targets]

    def _scoped_commands(self, cmd: list[str], extensions: tuple[str, ...] | None = None,
                         whole_project: list[str] | None = None) -> list[list[str]] | None:
        """Build complete commands, splitting only a filtered file list."""
        scope = self._scope_args(extensions, whole_project)
        if scope is None:
            return None
        if self.filter_files is None:
            command = [*cmd, *scope]
            if len(subprocess.list2cmdline(command)) > MAX_COMMAND_CHARS:
                raise ToolOutputError(f"command exceeds {MAX_COMMAND_CHARS} characters")
            return [command]

        commands: list[list[str]] = []
        current = cmd.copy()
        for path in scope:
            if len(subprocess.list2cmdline([*cmd, path])) > MAX_COMMAND_CHARS:
                raise ToolOutputError(f"command exceeds {MAX_COMMAND_CHARS} characters for {path}")
            if len(subprocess.list2cmdline([*current, path])) > MAX_COMMAND_CHARS:
                commands.append(current)
                current = cmd.copy()
            current.append(path)
        commands.append(current)
        return commands

    def _run_json(self, tool: str, commands: list[list[str]], cwd: Path | None,
                  accepted_returncodes: set[int] | None = None) -> list[Any]:
        """Run every command and return parsed JSON documents or fail."""
        documents = []
        for command in commands:
            result = self._run_subprocess(command, cwd)
            output = result.stdout or ''
            if accepted_returncodes is not None and result.returncode not in accepted_returncodes:
                raise ToolOutputError(
                    f"{tool} failed (exit {result.returncode}): {(result.stderr or '').strip()[:300]}")
            if not output.strip():
                raise ToolOutputError(
                    f"{tool} failed without producing output (exit {result.returncode}): "
                    f"{(result.stderr or '').strip()[:300]}")
            try:
                documents.append(json.loads(output))
            except json.JSONDecodeError as e:
                raise ToolOutputError(
                    f"could not parse {tool} JSON output: {e}; output was: {output[:200]}") from e
        return documents
