"""Tests for limiting complexity reports to functions touched since a Git commit."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from function_complexity import run_most_complex_function
from git_changes import GitNotAvailableError, _parse_diff_output, get_changed_lines
from logger import Logger

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed")


def _git(path: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(path), *args], capture_output=True, check=False, text=True
    )
    if result.returncode:
        raise AssertionError(result.stderr)
    return result.stdout.strip()


def _repo(path: Path) -> str:
    _git(path, "init", "-q")
    _git(path, "config", "user.email", "test@example.invalid")
    _git(path, "config", "user.name", "Test")
    return _git(path, "rev-parse", "--show-toplevel")


def _commit(path: Path, message: str) -> str:
    _git(path, "add", "--all")
    _git(path, "commit", "-m", message, "-q")
    return _git(path, "rev-parse", "HEAD")


def _write_files_list(root: Path, *paths: str) -> Path:
    files_from = root / "files.txt"
    files_from.write_text("\n".join(paths), encoding="utf-8")
    return files_from


def _source() -> str:
    return (
        "def old_complex(x):\n"
        "    if x:\n"
        "        if x > 1:\n"
        "            if x > 2:\n"
        "                return 3\n"
        "    return 0\n"
        "\n"
        "def simple(x):\n"
        "    return x\n"
    )


def _run(root: Path, files_from: Path, base: str, capsys: pytest.CaptureFixture[str]) -> dict:
    result = run_most_complex_function(
        str(root), str(files_from), Logger(quiet=True), diff_base=base
    )
    assert result == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    return json.loads(captured.out)


def test_uncommitted_change_selects_only_the_touched_function(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _repo(tmp_path)
    source = tmp_path / "sample.py"
    source.write_text(_source(), encoding="utf-8")
    base = _commit(tmp_path, "baseline")
    source.write_text(_source().replace("    return x", "    if x: return 1\n    return 0"), encoding="utf-8")
    files_from = _write_files_list(tmp_path, "sample.py")

    report = _run(tmp_path, files_from, base, capsys)

    assert report["function"]["function_name"] == "simple"
    assert report["function"]["start_line"] == 8
    assert report["function"]["end_line"] == 10


def test_committed_change_since_base_selects_the_touched_function(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _repo(tmp_path)
    source = tmp_path / "sample.py"
    source.write_text(_source(), encoding="utf-8")
    base = _commit(tmp_path, "baseline")
    source.write_text(_source().replace("    return x", "    if x: return 1\n    return 0"), encoding="utf-8")
    _commit(tmp_path, "change simple")
    files_from = _write_files_list(tmp_path, "sample.py")

    report = _run(tmp_path, files_from, base, capsys)

    assert report["function"]["function_name"] == "simple"


def test_deletion_only_hunk_touches_function(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _repo(tmp_path)
    source = tmp_path / "sample.py"
    initial = "def simple(x):\n    if x:\n        return 1\n    return 0\n"
    source.write_text(initial, encoding="utf-8")
    base = _commit(tmp_path, "baseline")
    source.write_text(initial.replace("        return 1\n", ""), encoding="utf-8")
    files_from = _write_files_list(tmp_path, "sample.py")

    report = _run(tmp_path, files_from, base, capsys)

    assert report["function"]["function_name"] == "simple"


def test_untracked_file_counts_all_its_functions(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _repo(tmp_path)
    tracked = tmp_path / "tracked.py"
    tracked.write_text(_source(), encoding="utf-8")
    base = _commit(tmp_path, "baseline")
    new_file = tmp_path / "new.py"
    new_file.write_text(_source(), encoding="utf-8")
    files_from = _write_files_list(tmp_path, "new.py")

    report = _run(tmp_path, files_from, base, capsys)

    assert report["function"]["function_name"] == "old_complex"


def test_unchanged_listed_file_contributes_no_function(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _repo(tmp_path)
    (tmp_path / "sample.py").write_text(_source(), encoding="utf-8")
    base = _commit(tmp_path, "baseline")
    files_from = _write_files_list(tmp_path, "sample.py")

    report = _run(tmp_path, files_from, base, capsys)

    assert report["function"] is None


def test_nested_project_root_returns_paths_relative_to_supplied_root(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    project = repo / "nested" / "project"
    project.mkdir(parents=True)
    _repo(repo)
    source = project / "app.py"
    source.write_text("def app():\n    return 1\n", encoding="utf-8")
    base = _commit(repo, "baseline")
    source.write_text("def app():\n    return 2\n", encoding="utf-8")

    changes = get_changed_lines(project, base)

    assert changes.lines == {Path("app.py"): frozenset({2})}
    assert changes.new_files == frozenset()


def test_unknown_commit_and_non_repository_raise_git_error(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _repo(repo)

    with pytest.raises(GitNotAvailableError, match="git diff|commit"):
        get_changed_lines(repo, "not-a-commit")
    with pytest.raises(GitNotAvailableError):
        get_changed_lines(tmp_path / "outside", "HEAD")


def test_without_diff_base_keeps_existing_all_functions_behavior(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = tmp_path / "sample.py"
    source.write_text(_source(), encoding="utf-8")
    files_from = _write_files_list(tmp_path, "sample.py")

    assert run_most_complex_function(str(tmp_path), str(files_from), Logger(quiet=True)) == 0

    report = json.loads(capsys.readouterr().out)
    assert report["function"]["function_name"] == "old_complex"


def test_diff_parser_records_new_side_hunks_new_files_and_deleted_files() -> None:
    diff = (
        "diff --git a/old.py b/old.py\n"
        "--- a/old.py\n"
        "+++ old.py\n"
        "@@ -1 +1,2 @@\n"
        "+added\n"
        "@@ -5,2 +6,3 @@\n"
        "+another\n"
        "@@ -10,2 +12,0 @@\n"
        "diff --git a/new.py b/new.py\n"
        "new file mode 100644\n"
        "--- /dev/null\n"
        "+++ new.py\n"
        "@@ -0,0 +1,2 @@\n"
        "+new\n"
        "diff --git a/gone.py b/gone.py\n"
        "deleted file mode 100644\n"
        "--- gone.py\n"
        "+++ /dev/null\n"
        "@@ -1,2 +0,0 @@\n"
    )

    changes = _parse_diff_output(diff)

    assert changes.lines == {
        Path("old.py"): frozenset({1, 2, 6, 7, 8, 12}),
        Path("new.py"): frozenset({1, 2}),
    }
    assert changes.new_files == frozenset({Path("new.py")})
    assert Path("gone.py") not in changes.lines
    assert Path("gone.py") not in changes.new_files
