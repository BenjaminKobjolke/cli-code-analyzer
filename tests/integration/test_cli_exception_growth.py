"""CLI integration coverage for exception-growth baseline lifecycle."""

import json
import subprocess
import sys
from pathlib import Path

from analyzer import AnalyzerConfig, CodeAnalyzer
from config import Config
from exception_baseline import BaselineKey, ExceptionBaseline
from models import RuleResult, RuleStatus

ROOT = Path(__file__).resolve().parents[2]


def _make_project(tmp_path: Path, *, enabled: bool | None = None) -> tuple[Path, Path, Path]:
    source_root = tmp_path / "src"
    source_root.mkdir()
    source = source_root / "example.py"
    source.write_text("line\n" * 5, encoding="utf-8")

    rules: dict = {
        "max_lines_per_file": {
            "enabled": True,
            "warning": 3,
            "error": 4,
            "exceptions": [
                {"file": "src/example.py", "warning": 10, "error": 12}
            ],
        }
    }
    if enabled is not None:
        rules["exception_growth"] = enabled
    rules_file = tmp_path / "rules.json"
    rules_file.write_text(json.dumps(rules), encoding="utf-8")
    return source_root, source, rules_file


def _run_cli(
    source_root: Path,
    rules_file: Path,
    *arguments: str,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(ROOT / "main.py"),
            "--language",
            "python",
            "--path",
            str(source_root.parent),
            "--rules",
            str(rules_file),
            "--format",
            "json",
            *arguments,
        ],
        cwd=source_root.parent,
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_exception_growth_config_defaults_on_and_can_be_disabled(tmp_path: Path) -> None:
    rules_file = tmp_path / "rules.json"
    rules_file.write_text("{}", encoding="utf-8")
    config = Config(str(rules_file))
    assert config.is_exception_growth_enabled()

    rules_file.write_text('{"exception_growth": false}', encoding="utf-8")
    assert not Config(str(rules_file)).is_exception_growth_enabled()

    rules_file.write_text('{"exception_growth": true}', encoding="utf-8")
    assert Config(str(rules_file)).is_exception_growth_enabled()


def test_cli_creates_baseline_and_reports_growth_warning(tmp_path: Path) -> None:
    source_root, source, rules_file = _make_project(tmp_path)
    baseline_path = rules_file.with_suffix(".exception_baseline.json")

    initial = _run_cli(source_root, rules_file)
    assert initial.returncode == 0, f"stdout={initial.stdout}\nstderr={initial.stderr}"
    assert baseline_path.exists()
    assert json.loads(baseline_path.read_text(encoding="utf-8"))["entries"][0]["value"] == 5

    source.write_text("line\n" * 7, encoding="utf-8")
    grown = _run_cli(source_root, rules_file)
    assert grown.returncode == 0, f"stdout={grown.stdout}\nstderr={grown.stderr}"
    assert "exception_growth" in grown.stdout
    assert "grew from 5 to 7" in grown.stdout


def test_cli_growth_warning_fails_with_fail_on_warnings(tmp_path: Path) -> None:
    source_root, source, rules_file = _make_project(tmp_path)
    assert _run_cli(source_root, rules_file).returncode == 0

    source.write_text("line\n" * 7, encoding="utf-8")
    result = _run_cli(source_root, rules_file, "--fail-on-warnings")

    assert result.returncode == 1, f"stdout={result.stdout}\nstderr={result.stderr}"
    assert "exception_growth" in result.stdout


def test_cli_opt_out_does_not_create_or_update_baseline(tmp_path: Path) -> None:
    source_root, source, rules_file = _make_project(tmp_path, enabled=False)
    baseline_path = rules_file.with_suffix(".exception_baseline.json")

    initial = _run_cli(source_root, rules_file)
    assert initial.returncode == 0, f"stdout={initial.stdout}\nstderr={initial.stderr}"
    assert not baseline_path.exists()

    source.write_text("line\n" * 7, encoding="utf-8")
    grown = _run_cli(source_root, rules_file)
    assert grown.returncode == 0, f"stdout={grown.stdout}\nstderr={grown.stderr}"
    assert "exception_growth" not in grown.stdout
    assert not baseline_path.exists()


def test_full_run_prunes_only_successful_rules(tmp_path: Path) -> None:
    source_root, _source, rules_file = _make_project(tmp_path)
    baseline = ExceptionBaseline(rules_file.with_suffix(".exception_baseline.json"))
    baseline.observe(BaselineKey("max_lines_per_file", "src/example.py", "lines"), 5)
    baseline.observe(BaselineKey("max_lines_per_file", "src/removed.py", "lines"), 8)
    baseline.observe(BaselineKey("ruff_analyze", "src/ruff.py", "C901", "gone"), 15)
    baseline.save()

    result = _run_cli(source_root, rules_file)

    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"
    entries = json.loads(baseline.path.read_text(encoding="utf-8"))["entries"]
    assert {(entry["rule"], entry["file"]) for entry in entries} == {
        ("max_lines_per_file", "src/example.py"),
        ("ruff_analyze", "src/ruff.py"),
    }


def test_failed_rule_does_not_prune_its_baseline_entries(tmp_path: Path) -> None:
    rules_file = tmp_path / "rules.json"
    rules_file.write_text("{}", encoding="utf-8")
    analyzer = CodeAnalyzer(AnalyzerConfig(
        languages="python",
        path=str(tmp_path),
        rules_file=str(rules_file),
    ))
    baseline = analyzer.exception_baseline_lifecycle.baseline
    assert baseline is not None
    baseline.observe(BaselineKey("ruff_analyze", "src/removed.py", "C901", "legacy"), 15)
    baseline.save()
    analyzer.results.append(RuleResult("ruff_analyze", RuleStatus.FAILED))

    analyzer.exception_baseline_lifecycle.save(analyzer.results, filtered=False)

    entries = json.loads(baseline.path.read_text(encoding="utf-8"))["entries"]
    assert [(entry["rule"], entry["file"]) for entry in entries] == [
        ("ruff_analyze", "src/removed.py")
    ]


def test_filtered_run_does_not_prune_unseen_entries(tmp_path: Path) -> None:
    source_root, _source, rules_file = _make_project(tmp_path)
    baseline = ExceptionBaseline(rules_file.with_suffix(".exception_baseline.json"))
    baseline.observe(BaselineKey("max_lines_per_file", "src/removed.py", "lines"), 8)
    baseline.save()

    result = _run_cli(source_root, rules_file, "--file", "src/example.py")

    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"
    entries = json.loads(baseline.path.read_text(encoding="utf-8"))["entries"]
    assert any(entry["file"] == "src/removed.py" for entry in entries)


def test_no_files_run_does_not_create_baseline(tmp_path: Path) -> None:
    empty_root = tmp_path / "empty"
    empty_root.mkdir()
    rules_file = tmp_path / "rules.json"
    rules_file.write_text('{"exception_growth": true}', encoding="utf-8")

    result = _run_cli(empty_root, rules_file)

    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"
    assert not rules_file.with_suffix(".exception_baseline.json").exists()


def test_cache_only_file_query_does_not_change_baseline(tmp_path: Path) -> None:
    source_root, _source, rules_file = _make_project(tmp_path)
    output = tmp_path / "reports"
    baseline = ExceptionBaseline(rules_file.with_suffix(".exception_baseline.json"))
    baseline.observe(BaselineKey("max_lines_per_file", "src/removed.py", "lines"), 8)
    baseline.save()
    before = baseline.path.read_bytes()

    build = _run_cli(source_root, rules_file, "--output", str(output), "--build-cache")
    assert build.returncode == 0, f"stdout={build.stdout}\nstderr={build.stderr}"
    after_build = baseline.path.read_bytes()
    assert after_build != before

    query = _run_cli(
        source_root,
        rules_file,
        "--output",
        str(output),
        "--file",
        "src/example.py",
    )

    assert query.returncode == 0, f"stdout={query.stdout}\nstderr={query.stderr}"
    assert "Using cached results" in query.stderr
    assert baseline.path.read_bytes() == after_build
