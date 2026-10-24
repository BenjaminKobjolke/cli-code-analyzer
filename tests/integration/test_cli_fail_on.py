import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tests.integration.test_cpp_language import _init_repo

ROOT = Path(__file__).resolve().parents[2]


def _make_project(tmp_path, source, rules):
    src = tmp_path / "src"
    src.mkdir()
    (src / "sample.py").write_text(source, encoding="utf-8")
    rules_file = tmp_path / "rules.json"
    rules_file.write_text(json.dumps(rules), encoding="utf-8")
    return src, rules_file


def _run_cli(src, rules_file, output=None, extra_args=(), cwd=None):
    command = [
        sys.executable,
        str(ROOT / "main.py"),
        "--language", "python",
        "--path", str(src),
        "--rules", str(rules_file),
    ]
    if output is not None:
        command.extend(["--output", str(output)])
    command.extend(extra_args)
    return subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=30)


def _commit_all(repo, message):
    subprocess.run(["git", "add", "old.py"], cwd=repo, check=True, capture_output=True, text=True, timeout=30)
    subprocess.run(["git", "commit", "-m", message], cwd=repo, check=True, capture_output=True, text=True, timeout=30)


@pytest.mark.skipif(shutil.which("ruff") is None, reason="Ruff is not installed")
def test_ruff_warning_fails_only_when_configured(tmp_path):
    src, rules_file = _make_project(
        tmp_path,
        "import os\n",
        {"fail_on": "warning", "ruff_analyze": {"enabled": True, "select": ["F"]}},
    )

    configured = _run_cli(src, rules_file)
    assert configured.returncode == 1, f"stdout={configured.stdout}\nstderr={configured.stderr}"

    rules_file.write_text(
        json.dumps({"ruff_analyze": {"enabled": True, "select": ["F"]}}),
        encoding="utf-8",
    )
    default = _run_cli(src, rules_file)
    assert default.returncode == 0, f"stdout={default.stdout}\nstderr={default.stderr}"


@pytest.mark.skipif(shutil.which("ruff") is None, reason="Ruff is not installed")
def test_fail_on_warnings_cli_flag_reports_ruff_warning_and_default_is_unchanged(tmp_path):
    src, rules_file = _make_project(
        tmp_path,
        "import os\n",
        {"ruff_analyze": {"enabled": True}},
    )

    enabled = _run_cli(src, rules_file, extra_args=("--fail-on-warnings", "--format", "json"))
    disabled = _run_cli(src, rules_file, extra_args=("--format", "json"))

    assert enabled.returncode == 1, f"stdout={enabled.stdout}\nstderr={enabled.stderr}"
    assert disabled.returncode == 0, f"stdout={disabled.stdout}\nstderr={disabled.stderr}"
    for result in (enabled, disabled):
        summary = json.loads(result.stdout)["summary"]
        assert summary["warnings"] >= 1
        assert summary["errors"] == 0


@pytest.mark.skipif(shutil.which("ruff") is None, reason="Ruff is not installed")
def test_fail_on_warnings_cli_flag_allows_clean_project(tmp_path):
    src, rules_file = _make_project(
        tmp_path,
        "x = 1\n",
        {"ruff_analyze": {"enabled": True}},
    )

    for extra_args in ((), ("--fail-on-warnings",)):
        result = _run_cli(src, rules_file, extra_args=extra_args)
        assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"


@pytest.mark.skipif(shutil.which("ruff") is None, reason="Ruff is not installed")
@pytest.mark.skipif(shutil.which("git") is None, reason="git is required for --only-changed")
def test_only_changed_fail_on_warnings_checks_only_changed_files(tmp_path):
    repo = tmp_path / "project"
    _init_repo(repo)
    (repo / "old.py").write_text("import os\n", encoding="utf-8")
    _commit_all(repo, "add existing warning")
    rules_file = tmp_path / "rules.json"
    rules_file.write_text(json.dumps({"ruff_analyze": {"enabled": True}}), encoding="utf-8")
    new_file = repo / "new.py"
    new_file.write_text("x = 1\n", encoding="utf-8")
    args = ("--only-changed", "--fail-on-warnings", "--format", "json")

    clean_changed_file = _run_cli(repo, rules_file, extra_args=args, cwd=repo)
    assert clean_changed_file.returncode == 0, (
        f"stdout={clean_changed_file.stdout}\nstderr={clean_changed_file.stderr}"
    )

    new_file.write_text("import sys\n", encoding="utf-8")
    warning_in_changed_file = _run_cli(repo, rules_file, extra_args=args, cwd=repo)
    assert warning_in_changed_file.returncode == 1, (
        f"stdout={warning_in_changed_file.stdout}\nstderr={warning_in_changed_file.stderr}"
    )
    summary = json.loads(warning_in_changed_file.stdout)["summary"]
    assert summary["warnings"] >= 1
    assert summary["errors"] == 0


def test_error_finding_fails_when_warnings_are_configured(tmp_path):
    src, rules_file = _make_project(
        tmp_path,
        "\n".join(f"value_{line} = {line}" for line in range(10)),
        {"fail_on": "warning", "max_lines_per_file": {"enabled": True, "warning": 3, "error": 5}},
    )

    result = _run_cli(src, rules_file)

    assert result.returncode == 1, f"stdout={result.stdout}\nstderr={result.stderr}"


def test_builtin_warning_fails_when_configured_and_writes_csv(tmp_path):
    src, rules_file = _make_project(
        tmp_path,
        "\n".join(f"value_{line} = {line}" for line in range(4)),
        {"fail_on": "warning", "max_lines_per_file": {"enabled": True, "warning": 3, "error": 5}},
    )

    result = _run_cli(src, rules_file, output=tmp_path / "reports")

    assert result.returncode == 1, f"stdout={result.stdout}\nstderr={result.stderr}"
    assert (tmp_path / "reports" / "line_count_report.csv").exists()

    rules_file.write_text(
        json.dumps({"max_lines_per_file": {"enabled": True, "warning": 3, "error": 5}}),
        encoding="utf-8",
    )
    default = _run_cli(src, rules_file)
    assert default.returncode == 0, f"stdout={default.stdout}\nstderr={default.stderr}"


def test_clean_project_succeeds_with_warning_threshold(tmp_path):
    src, rules_file = _make_project(
        tmp_path,
        "value_1 = 1\nvalue_2 = 2\n",
        {"fail_on": "warning", "max_lines_per_file": {"enabled": True, "warning": 3, "error": 5}},
    )

    result = _run_cli(src, rules_file)

    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"


def test_invalid_fail_on_configuration_exits_nonzero(tmp_path):
    src, rules_file = _make_project(tmp_path, "value = 1\n", {"fail_on": "warnings"})

    result = _run_cli(src, rules_file)

    assert result.returncode == 1
    assert "fail_on" in result.stdout + result.stderr
