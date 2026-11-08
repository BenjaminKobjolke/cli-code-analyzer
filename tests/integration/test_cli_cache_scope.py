"""CLI integration coverage for violation-cache file scope."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CHANGED_SINCE_ENV = "CLI_ANALYZER_CHANGED_SINCE"
CACHE_HIT_MESSAGE = "Using cached results (no fresh analysis)"

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


def _run_cli(
    repo: Path,
    rules: Path,
    output: Path,
    env: dict[str, str],
) -> subprocess.CompletedProcess[str]:
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
            "--output",
            str(output),
        ],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )


def _make_repo(tmp_path: Path) -> tuple[Path, Path, Path, str]:
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
    (repo / "small.py").write_text("value = 2\n", encoding="utf-8")
    rules = tmp_path / "rules.json"
    rules.write_text(
        json.dumps({"max_lines_per_file": {"enabled": True, "warning": 3, "error": 5}}),
        encoding="utf-8",
    )
    return repo, rules, tmp_path / "out", base


def test_wider_filtered_run_does_not_reuse_narrow_cache(tmp_path: Path) -> None:
    repo, rules, output, base = _make_repo(tmp_path)
    env = os.environ.copy()
    env.pop(CHANGED_SINCE_ENV, None)

    narrow = _run_cli(repo, rules, output, env)
    assert narrow.returncode == 0, f"stdout={narrow.stdout}\nstderr={narrow.stderr}"
    assert (output / "_violations_cache.db").exists()

    wider_env = env.copy()
    wider_env[CHANGED_SINCE_ENV] = base
    wider = _run_cli(repo, rules, output, wider_env)
    assert wider.returncode == 1, f"stdout={wider.stdout}\nstderr={wider.stderr}"
    report = (output / "line_count_report.csv").read_text(encoding="utf-8")
    assert "big.py" in report and "ERROR" in report
    assert CACHE_HIT_MESSAGE not in wider.stderr


def test_repeat_filtered_run_uses_cache(tmp_path: Path) -> None:
    repo, rules, output, _ = _make_repo(tmp_path)
    env = os.environ.copy()
    env.pop(CHANGED_SINCE_ENV, None)

    first = _run_cli(repo, rules, output, env)
    assert first.returncode == 0, f"stdout={first.stdout}\nstderr={first.stderr}"
    assert CACHE_HIT_MESSAGE not in first.stderr

    second = _run_cli(repo, rules, output, env)
    assert second.returncode == 0, f"stdout={second.stdout}\nstderr={second.stderr}"
    assert CACHE_HIT_MESSAGE in second.stderr
