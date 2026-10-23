"""CLI tests for the most-complex-function JSON mode."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _run(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "main.py"), *arguments],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def _git(root: Path, *arguments: str) -> None:
    subprocess.run(
        ["git", "-C", str(root), *arguments],
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
    )


def _input_list(root: Path, *paths: str) -> Path:
    files_from = root / "changed-files.txt"
    files_from.write_text("\n".join(paths), encoding="utf-8")
    return files_from


def test_cli_prints_only_json_with_winning_function_and_full_line_range(tmp_path):
    source = tmp_path / "sample.py"
    source.write_text(
        "def simple():\n    return 1\n\n"
        "def complex():\n"
        "    if first:\n        pass\n"
        "    if second:\n        pass\n"
        "    return 2\n",
        encoding="utf-8",
    )
    files_from = _input_list(tmp_path, "sample.py")

    result = _run(
        "--most-complex-function",
        "--path",
        str(tmp_path),
        "--files-from",
        str(files_from),
    )

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["function"] == {
        "file_path": "sample.py",
        "function_name": "complex",
        "language": "python",
        "start_line": 4,
        "end_line": 9,
        "complexity": 3,
    }
    assert report["errors"] == []
    assert result.stderr == ""


def test_cli_returns_null_for_file_without_functions(tmp_path):
    (tmp_path / "empty.py").write_text("# no functions\n", encoding="utf-8")
    files_from = _input_list(tmp_path, "empty.py")

    result = _run(
        "--most-complex-function", "--path", str(tmp_path), "--files-from", str(files_from)
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"function": None, "errors": []}


def test_cli_requires_files_from(tmp_path):
    result = _run("--most-complex-function", "--path", str(tmp_path))

    assert result.returncode == 2
    assert result.stdout == ""
    assert "--files-from is required" in result.stderr


@pytest.mark.parametrize("option", [("--files-from", "files.txt"), ("--diff-base", "HEAD")])
def test_cli_rejects_function_options_without_mode(option):
    result = _run(*option)

    assert result.returncode == 2
    assert result.stdout == ""
    assert "require --most-complex-function" in result.stderr


@pytest.mark.skipif(shutil.which("git") is None, reason="Git is not installed")
def test_cli_diff_base_selects_changed_function_only(tmp_path):
    source = tmp_path / "sample.py"
    source.write_text(
        "def simple():\n    return 1\n\n"
        "def complex():\n"
        "    if first:\n        pass\n"
        "    if second:\n        pass\n"
        "    return 2\n",
        encoding="utf-8",
    )
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Test")
    _git(tmp_path, "add", "sample.py")
    _git(tmp_path, "commit", "-qm", "initial")
    base = subprocess.run(
        ["git", "-C", str(tmp_path), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
    ).stdout.strip()
    source.write_text(source.read_text(encoding="utf-8").replace("return 1", "return 3"), encoding="utf-8")
    files_from = _input_list(tmp_path, "sample.py")

    result = _run(
        "--most-complex-function",
        "--path",
        str(tmp_path),
        "--files-from",
        str(files_from),
        "--diff-base",
        base,
    )

    assert result.returncode == 0, result.stderr
    function = json.loads(result.stdout)["function"]
    assert function["function_name"] == "simple"
    assert function["start_line"] == 1
    assert function["end_line"] == 2


@pytest.mark.skipif(shutil.which("git") is None, reason="Git is not installed")
def test_cli_invalid_diff_base_is_an_error_without_stdout(tmp_path):
    source = tmp_path / "sample.py"
    source.write_text("def simple():\n    return 1\n", encoding="utf-8")
    _git(tmp_path, "init", "-q")
    files_from = _input_list(tmp_path, "sample.py")

    result = _run(
        "--most-complex-function",
        "--path",
        str(tmp_path),
        "--files-from",
        str(files_from),
        "--diff-base",
        "missing-commit",
    )

    assert result.returncode == 2
    assert result.stdout == ""
    assert "failed" in result.stderr.lower()
