"""Integration tests for contract JSON discovery and CLI behavior."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from analyzer_registry import ANALYZER_REGISTRY, LANGUAGE_ALIASES
from file_discovery import DEFAULT_EXCLUDE_PATTERNS, FileDiscovery

ROOT = Path(__file__).resolve().parents[2]


def _rules_file(path: Path, config: dict | None = None) -> Path:
    rules = path / "rules.json"
    rules.write_text(json.dumps(config or {}), encoding="utf-8")
    return rules


def _run_cli(path: Path, *, language: str = "contract", extra_args: tuple[str, ...] = (),
             config: dict | None = None) -> subprocess.CompletedProcess[str]:
    rules = _rules_file(path, config)
    return subprocess.run(
        [
            sys.executable, str(ROOT / "main.py"), "--language", language,
            "--path", str(path), "--rules", str(rules), "--format", "json",
            *extra_args,
        ],
        cwd=path,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def _valid_enum() -> str:
    return json.dumps({
        "Example": {
            "values": ["first", "second"],
            "direction": "api_to_client",
            "description": "An example enum",
        },
    })


def test_contract_registry_and_json_alias():
    assert [entry[0] for entry in ANALYZER_REGISTRY["contract"]] == ["contract_enums"]
    assert LANGUAGE_ALIASES["json"] == "contract"


def test_contract_discovery_includes_json_and_skips_local_state(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "tickets").mkdir()
    (tmp_path / "graphify-out").mkdir()
    (tmp_path / "code_analysis_results").mkdir()
    (tmp_path / "tmp").mkdir()
    for name in (
        "src/enums.json", "coding-rules.json", "tickets/local.json",
        "graphify-out/graph.json", "code_analysis_results/report.json",
        "tmp/cache.json", "coding-rules.json",
    ):
        (tmp_path / name).write_text("{}", encoding="utf-8")

    found = {
        path.relative_to(tmp_path).as_posix()
        for path in FileDiscovery("contract", str(tmp_path)).discover()
    }

    assert found == {"src/enums.json"}
    assert "contract" in DEFAULT_EXCLUDE_PATTERNS


def test_contract_cli_is_default_on_and_fail_on_warnings_exits_nonzero(tmp_path: Path):
    (tmp_path / "enums.json").write_text(_valid_enum(), encoding="utf-8")
    clean = _run_cli(tmp_path, language="json", extra_args=("--fail-on-warnings",))
    assert clean.returncode == 0, f"stdout={clean.stdout}\nstderr={clean.stderr}"

    (tmp_path / "enums.json").write_text('{"Example": {"values": ["z", "a"]}}', encoding="utf-8")
    invalid = _run_cli(tmp_path, extra_args=("--fail-on-warnings",))
    assert invalid.returncode == 1, f"stdout={invalid.stdout}\nstderr={invalid.stderr}"
    output = json.loads(invalid.stdout)
    assert any("Example" in violation["message"] for violation in output["violations"])


def test_contract_cli_honors_explicit_rule_disable(tmp_path: Path):
    (tmp_path / "enums.json").write_text('{"Example": {"values": []}}', encoding="utf-8")

    result = _run_cli(tmp_path, config={"contract_enums": {"enabled": False}})

    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"
    assert json.loads(result.stdout)["violations"] == []


def test_contract_cli_lists_analyzer():
    result = subprocess.run(
        [sys.executable, str(ROOT / "main.py"), "--list-analyzers", "contract"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"
    assert "contract_enums" in result.stdout


@pytest.mark.skipif(shutil.which("git") is None, reason="git is required for --only-changed")
def test_only_changed_checks_untracked_contract_json_and_ignores_unchanged(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True, timeout=10)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "tests@example.invalid"],
                   check=True, timeout=10)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Analyzer Tests"],
                   check=True, timeout=10)
    (repo / "baseline.json").write_text("{}", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "baseline.json"], check=True, timeout=10)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "add baseline"], check=True, timeout=10)

    no_changes = _run_cli(repo, extra_args=("--only-changed",))
    assert no_changes.returncode == 0, f"stdout={no_changes.stdout}\nstderr={no_changes.stderr}"
    assert json.loads(no_changes.stdout)["summary"]["total"] == 0

    (repo / "enums.json").write_text('{"Example": {"values": ["z", "a"]}}', encoding="utf-8")
    changed = _run_cli(repo, extra_args=("--only-changed", "--fail-on-warnings"))
    assert changed.returncode == 1, f"stdout={changed.stdout}\nstderr={changed.stderr}"
    violations = json.loads(changed.stdout)["violations"]
    assert any(v["file_path"].replace("\\", "/") == "enums.json" for v in violations)
