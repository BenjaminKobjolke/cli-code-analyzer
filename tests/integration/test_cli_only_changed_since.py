"""CLI integration coverage for the changed-since environment variable."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CHANGED_SINCE_ENV = "CLI_ANALYZER_CHANGED_SINCE"


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


def _run_cli(repo: Path, rules: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(ROOT / "main.py"),
            "--language",
            "python",
            "--path",
            str(repo),
            "--rules",
            str(rules),
            "--only-changed",
        ],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_only_changed_includes_committed_files_since_env_commit(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "analyzer-test@example.com")
    _git(repo, "config", "user.name", "Analyzer Test")
    (repo / "ok.py").write_text("value = 1\n", encoding="utf-8")
    _git(repo, "add", "ok.py")
    _git(repo, "commit", "-m", "base")
    base = _git(repo, "rev-parse", "HEAD")
    (repo / "big.py").write_text(
        "\n".join(f"value_{line} = {line}" for line in range(10)) + "\n",
        encoding="utf-8",
    )
    _git(repo, "add", "big.py")
    _git(repo, "commit", "-m", "add large file")
    rules = tmp_path / "rules.json"
    rules.write_text(
        json.dumps({"max_lines_per_file": {"enabled": True, "warning": 3, "error": 5}}),
        encoding="utf-8",
    )

    without_variable = os.environ.copy()
    without_variable.pop(CHANGED_SINCE_ENV, None)
    unchanged = _run_cli(repo, rules, without_variable)
    assert unchanged.returncode == 0, f"stdout={unchanged.stdout}\nstderr={unchanged.stderr}"
    assert "No changed files" in unchanged.stderr

    blank_variable = without_variable.copy()
    blank_variable[CHANGED_SINCE_ENV] = "   "
    blank = _run_cli(repo, rules, blank_variable)
    assert blank.returncode == 0, f"stdout={blank.stdout}\nstderr={blank.stderr}"
    assert "No changed files" in blank.stderr

    since_base = without_variable.copy()
    since_base[CHANGED_SINCE_ENV] = base
    analyzed = _run_cli(repo, rules, since_base)
    assert analyzed.returncode == 1, f"stdout={analyzed.stdout}\nstderr={analyzed.stderr}"
    assert "big.py" in analyzed.stdout + analyzed.stderr

    invalid_commit = without_variable.copy()
    invalid_commit[CHANGED_SINCE_ENV] = "not-a-commit"
    invalid = _run_cli(repo, rules, invalid_commit)
    assert invalid.returncode == 1
    assert CHANGED_SINCE_ENV in invalid.stderr
