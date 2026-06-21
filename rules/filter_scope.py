"""Filter-file scoping helpers, mixed into BaseRule.

Provides the logic that maps an active ``--only-changed`` / ``--file`` filter to
the file-path arguments a project-wide tool should scan. Kept separate from
base.py so the core base class stays focused. The host class supplies
``filter_files`` and ``base_path`` (BaseRule sets both in __init__).
"""

from pathlib import Path


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
