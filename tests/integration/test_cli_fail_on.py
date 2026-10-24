import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _make_project(tmp_path, source, rules):
    src = tmp_path / "src"
    src.mkdir()
    (src / "sample.py").write_text(source, encoding="utf-8")
    rules_file = tmp_path / "rules.json"
    rules_file.write_text(json.dumps(rules), encoding="utf-8")
    return src, rules_file


def _run_cli(src, rules_file, output=None):
    command = [
        sys.executable,
        str(ROOT / "main.py"),
        "--language", "python",
        "--path", str(src),
        "--rules", str(rules_file),
    ]
    if output is not None:
        command.extend(["--output", str(output)])
    return subprocess.run(command, capture_output=True, text=True, timeout=30)


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
