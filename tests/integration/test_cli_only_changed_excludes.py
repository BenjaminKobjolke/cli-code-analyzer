"""CLI coverage for configured excludes in changed-file and single-file modes."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

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


def _repo(tmp_path: Path, *files: tuple[str, str]) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "analyzer-test@example.com")
    _git(repo, "config", "user.name", "Analyzer Test")
    for name, content in files:
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")
    return repo


def _run_cli(repo: Path, rules: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(ROOT / "main.py"),
            "--language", "python",
            "--path", str(repo),
            "--rules", str(rules),
            *extra,
        ],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=30,
    )


def _rules(path: Path, **settings: object) -> Path:
    rules = path / "rules.json"
    rules.write_text(json.dumps(settings), encoding="utf-8")
    return rules


def test_only_changed_reports_no_files_when_all_changes_are_globally_excluded(tmp_path: Path):
    repo = _repo(tmp_path, ("api/x.py", "value = 1\n"))
    (repo / "api/x.py").write_text("value = 2\n", encoding="utf-8")
    rules = _rules(tmp_path, global_exclude_paths=["api"])

    result = _run_cli(repo, rules, "--only-changed")

    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"
    assert "No changed files" in result.stderr


def test_file_mode_reports_when_target_is_excluded(tmp_path: Path):
    repo = _repo(tmp_path, ("api/x.py", "value = 1\n"))
    rules = _rules(tmp_path, global_exclude_paths=["api"])

    result = _run_cli(repo, rules, "--file", "api/x.py")

    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"
    assert "api/x.py" in result.stderr
    assert "excluded by the configured excludes" in result.stderr


def test_only_changed_applies_global_and_max_lines_excludes(tmp_path: Path):
    repo = _repo(tmp_path, ("src/a.py", "old = 1\n"), ("api/x.py", "old = 1\n"))
    (repo / "src/a.py").write_text("one = 1\ntwo = 2\n", encoding="utf-8")
    (repo / "api/x.py").write_text("one = 1\ntwo = 2\n", encoding="utf-8")
    rules = _rules(
        tmp_path,
        global_exclude_paths=["api"],
        max_lines_per_file={"enabled": True, "warning": 1, "error": 5},
    )

    result = _run_cli(repo, rules, "--only-changed", "--format", "json")

    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"
    output = json.loads(result.stdout)
    reported_paths = {violation["file_path"].replace("\\", "/") for violation in output["violations"]}
    assert "src/a.py" in reported_paths
    assert not any(path.startswith("api/") for path in reported_paths)
