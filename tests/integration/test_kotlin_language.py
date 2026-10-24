"""Integration tests for Kotlin discovery and CLI behavior."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from analyzer_registry import ANALYZER_REGISTRY, LANGUAGE_ALIASES
from file_discovery import FileDiscovery

ROOT = Path(__file__).resolve().parents[2]


def _rules_file(path: Path, *, complexity_error: int = 3) -> Path:
    rules_file = path / "rules.json"
    rules_file.write_text(json.dumps({
        "kotlin_complexity": {
            "enabled": True,
            "cyclomatic_complexity": {"warning": 2, "error": complexity_error},
        },
    }), encoding="utf-8")
    return rules_file


def _run_cli(path: Path, language: str = "kotlin", *, only_changed: bool = False):
    command = [
        sys.executable, str(ROOT / "main.py"), "--language", language,
        "--path", str(path), "--rules", str(_rules_file(path)), "--format", "json",
    ]
    if only_changed:
        command.append("--only-changed")
    result = subprocess.run(command, capture_output=True, text=True, timeout=60, check=False)
    start = result.stdout.find("{")
    assert start >= 0, f"no JSON output: stdout={result.stdout[:500]} stderr={result.stderr[:500]}"
    data, _end = json.JSONDecoder().raw_decode(result.stdout[start:])
    return data, result


def _complex_source() -> str:
    return """fun branching(value: Int): Int {
    if (value > 0 && value < 10) return 1
    return when (value) { 10 -> 2; 20 -> 3; else -> 0 }
}
"""


def test_kotlin_registry_and_alias():
    analyzers = {entry[0] for entry in ANALYZER_REGISTRY["kotlin"]}

    assert {"max_lines_per_file", "pmd_duplicates", "pmd_similar_code", "kotlin_complexity"} <= analyzers
    assert LANGUAGE_ALIASES["kt"] == "kotlin"


def test_discovery_includes_kotlin_and_skips_generated_directories(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "build").mkdir()
    (tmp_path / ".gradle").mkdir()
    (tmp_path / "src" / "App.kt").write_text("fun app() = 1\n", encoding="utf-8")
    (tmp_path / "src" / "Script.kts").write_text("println(1)\n", encoding="utf-8")
    (tmp_path / "build" / "Generated.kt").write_text("fun generated() = 1\n", encoding="utf-8")
    (tmp_path / ".gradle" / "cache.kt").write_text("fun cache() = 1\n", encoding="utf-8")

    found = {p.relative_to(tmp_path).as_posix() for p in FileDiscovery("kotlin", str(tmp_path)).discover()}

    assert found == {"src/App.kt", "src/Script.kts"}


def test_cli_reports_complexity_and_clean_exit_codes(tmp_path):
    (tmp_path / "Complex.kt").write_text(_complex_source(), encoding="utf-8")
    data, result = _run_cli(tmp_path)

    assert result.returncode == 1
    assert any(v["rule_name"] == "kotlin_complexity" for v in data["violations"])
    assert not data.get("failures")

    clean_path = tmp_path / "clean"
    clean_path.mkdir()
    (clean_path / "Simple.kt").write_text("fun simple() = 1\n", encoding="utf-8")
    clean_data, clean_result = _run_cli(clean_path)

    assert clean_result.returncode == 0
    assert clean_data["violations"] == []
    assert clean_data.get("failures") == []


@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
def test_only_changed_checks_untracked_kotlin_files(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True, timeout=10)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "tests@example.invalid"], check=True, timeout=10)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "Analyzer Tests"], check=True, timeout=10)
    old_file = tmp_path / "Old.kt"
    old_file.write_text(_complex_source(), encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "Old.kt"], check=True, timeout=10)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-qm", "add old source"], check=True, timeout=10)
    new_file = tmp_path / "New.kt"
    new_file.write_text("fun simple() = 1\n", encoding="utf-8")

    clean_data, clean_result = _run_cli(tmp_path, only_changed=True)
    assert clean_result.returncode == 0
    assert clean_data["violations"] == []

    new_file.write_text(_complex_source(), encoding="utf-8")
    issue_data, issue_result = _run_cli(tmp_path, only_changed=True)
    assert issue_result.returncode == 1
    findings = [v for v in issue_data["violations"] if v["rule_name"] == "kotlin_complexity"]
    assert [v["file_path"].replace("\\", "/") for v in findings] == ["New.kt"]


def test_cli_accepts_kt_alias(tmp_path):
    (tmp_path / "Complex.kt").write_text(_complex_source(), encoding="utf-8")

    data, result = _run_cli(tmp_path, language="kt")

    assert result.returncode == 1
    assert any(v["rule_name"] == "kotlin_complexity" for v in data["violations"])
