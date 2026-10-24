"""Integration coverage for Arduino and general C++ support."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from analyzer import AnalyzerConfig, CodeAnalyzer
from analyzer_registry import LANGUAGE_ALIASES, get_analyzers_for_language
from file_discovery import FileDiscovery
from logger import Logger

ROOT = Path(__file__).resolve().parents[2]


def test_cpp_registered_with_arduino_aliases() -> None:
    names = [name for name, _description, _requires in get_analyzers_for_language("cpp")]
    assert names == ["max_lines_per_file", "pmd_duplicates", "pmd_similar_code"]
    assert {alias: LANGUAGE_ALIASES[alias] for alias in ("arduino", "ino", "c++")} == {
        "arduino": "cpp",
        "ino": "cpp",
        "c++": "cpp",
    }


def test_discovery_finds_cpp_extensions_and_excludes_build_caches(tmp_path: Path) -> None:
    extensions = ("ino", "cpp", "h", "hpp", "c", "cc")
    for extension in extensions:
        (tmp_path / f"source.{extension}").write_text("int value;\n", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("not source\n", encoding="utf-8")
    (tmp_path / ".pio" / "libdeps" / "x").mkdir(parents=True)
    (tmp_path / ".pio" / "libdeps" / "x" / "lib.cpp").write_text("int lib;\n", encoding="utf-8")
    (tmp_path / "build").mkdir()
    (tmp_path / "build" / "generated.cpp").write_text("int generated;\n", encoding="utf-8")

    found = {path.relative_to(tmp_path).as_posix() for path in FileDiscovery("cpp", str(tmp_path)).discover()}

    assert found == {f"source.{extension}" for extension in extensions}


def test_max_lines_analyzer_checks_ino_files(tmp_path: Path) -> None:
    sketch = tmp_path / "large.ino"
    sketch.write_text("\n".join(f"// line {line}" for line in range(600)), encoding="utf-8")
    rules = tmp_path / "rules.json"
    rules.write_text(json.dumps({"max_lines_per_file": {"enabled": True, "warning": 300, "error": 500}}))

    analyzer = CodeAnalyzer(AnalyzerConfig(
        languages="cpp",
        path=str(tmp_path),
        rules_file=str(rules),
        logger=Logger(quiet=True),
    ))
    analyzer.analyze()

    assert analyzer.get_file_count() == 1
    assert any(v.rule_name == "max_lines_per_file" and v.file_path.endswith("large.ino") for v in analyzer.violations)


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True, timeout=30)


def _init_repo(repo: Path) -> None:
    repo.mkdir()
    _git("init", cwd=repo)
    _git("config", "user.email", "analyzer-test@example.com", cwd=repo)
    _git("config", "user.name", "Analyzer Test", cwd=repo)
    (repo / "sketch.ino").write_text("void setup() {}\n", encoding="utf-8")
    (repo / "lib.cpp").write_text("void library() {}\n", encoding="utf-8")
    _git("add", "sketch.ino", "lib.cpp", cwd=repo)
    _git("commit", "-m", "initial", cwd=repo)


def _run_changed_analysis(repo: Path, rules: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "main.py"), "--language", "arduino", "--path", str(repo),
         "--rules", str(rules), "--only-changed", "--format", "json"],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=60,
    )


def _report(result: subprocess.CompletedProcess[str]) -> dict:
    start = result.stdout.find("{")
    assert start >= 0, result.stdout
    return json.JSONDecoder().raw_decode(result.stdout[start:])[0]


@pytest.mark.skipif(shutil.which("git") is None, reason="git is required for --only-changed")
def test_only_changed_analyzes_changed_ino_and_returns_finding_exit_code(tmp_path: Path) -> None:
    repo = tmp_path / "changed"
    _init_repo(repo)
    rules = tmp_path / "rules.json"
    rules.write_text(json.dumps({"max_lines_per_file": {"enabled": True, "warning": 300, "error": 500}}))
    (repo / "sketch.ino").write_text("\n".join(f"// line {line}" for line in range(600)), encoding="utf-8")
    (repo / "new_header.h").write_text("void new_function();\n", encoding="utf-8")

    result = _run_changed_analysis(repo, rules)

    report = _report(result)
    assert result.returncode == 1
    violations = [v for v in report["violations"] if v["rule_name"] == "max_lines_per_file"]
    assert len(violations) == 1
    assert Path(violations[0]["file_path"]).name == "sketch.ino"


@pytest.mark.skipif(shutil.which("git") is None, reason="git is required for --only-changed")
def test_only_changed_includes_untracked_cpp_header(tmp_path: Path) -> None:
    repo = tmp_path / "untracked"
    _init_repo(repo)
    rules = tmp_path / "rules.json"
    rules.write_text(json.dumps({"max_lines_per_file": {"enabled": True, "warning": 300, "error": 500}}))
    (repo / "new_header.h").write_text("\n".join(f"// line {line}" for line in range(600)), encoding="utf-8")

    result = _run_changed_analysis(repo, rules)

    report = _report(result)
    assert result.returncode == 1
    violations = [v for v in report["violations"] if v["rule_name"] == "max_lines_per_file"]
    assert len(violations) == 1
    assert Path(violations[0]["file_path"]).name == "new_header.h"


@pytest.mark.skipif(shutil.which("git") is None, reason="git is required for --only-changed")
def test_only_changed_clean_cpp_project_returns_zero(tmp_path: Path) -> None:
    repo = tmp_path / "clean"
    _init_repo(repo)
    rules = tmp_path / "rules.json"
    rules.write_text(json.dumps({"max_lines_per_file": {"enabled": True, "warning": 300, "error": 500}}))
    (repo / "sketch.ino").write_text("void setup() { pinMode(LED_BUILTIN, OUTPUT); }\n", encoding="utf-8")

    result = _run_changed_analysis(repo, rules)

    assert result.returncode == 0, result.stderr
    assert not _report(result)["violations"]
