"""Tests for changed-file selection relative to a Git commit."""

import shutil
import subprocess
from pathlib import Path

import pytest

from git_changes import (
    CHANGED_SINCE_ENV,
    GitNotAvailableError,
    changed_since_from_env,
    get_changed_files,
)

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git is required")


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.stdout.strip()


def _make_history(repo: Path) -> str:
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "analyzer-test@example.com")
    _git(repo, "config", "user.name", "Analyzer Test")
    content = "".join(f"line {number}: stable source content\n" for number in range(10))
    for name in ("keep.py", "edit.py", "gone.py", "old_name.py"):
        (repo / name).write_text(content, encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")
    base = _git(repo, "rev-parse", "HEAD")

    (repo / "edit.py").write_text(content.replace("line 5:", "changed 5:"), encoding="utf-8")
    (repo / "added.py").write_text(content, encoding="utf-8")
    (repo / "gone.py").unlink()
    (repo / "old_name.py").replace(repo / "new_name.py")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "change files")

    (repo / "keep.py").write_text(content.replace("line 0:", "worktree 0:"), encoding="utf-8")
    (repo / "fresh.py").write_text("untracked\n", encoding="utf-8")
    (repo / "added.py").unlink()
    return base


def test_get_changed_files_since_unions_commits_and_worktree_and_skips_deletions(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    base = _make_history(repo)

    changed = get_changed_files(repo, since=base)

    assert changed == {
        (repo / name).resolve()
        for name in ("edit.py", "new_name.py", "keep.py", "fresh.py")
    }
    assert (repo / "gone.py").resolve() not in changed
    assert (repo / "old_name.py").resolve() not in changed
    assert (repo / "added.py").resolve() not in changed


def test_get_changed_files_without_since_keeps_head_only_behavior(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _make_history(repo)

    assert get_changed_files(repo) == {
        (repo / "keep.py").resolve(),
        (repo / "fresh.py").resolve(),
    }


def test_invalid_since_commit_names_environment_variable(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _make_history(repo)

    with pytest.raises(GitNotAvailableError, match=CHANGED_SINCE_ENV):
        get_changed_files(repo, since="not-a-commit")


def test_changed_since_from_env_strips_value_and_treats_blank_as_unset(monkeypatch) -> None:
    monkeypatch.delenv(CHANGED_SINCE_ENV, raising=False)
    assert changed_since_from_env() is None

    monkeypatch.setenv(CHANGED_SINCE_ENV, "   ")
    assert changed_since_from_env() is None

    monkeypatch.setenv(CHANGED_SINCE_ENV, "  abc123  ")
    assert changed_since_from_env() == "abc123"
