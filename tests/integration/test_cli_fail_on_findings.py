import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RULES = {
    "log_level": "all",
    "max_lines_per_file": {"enabled": True, "warning": 3, "error": 5},
}


def _make_project(tmp_path: Path, line_count: int) -> tuple[Path, Path]:
    src = tmp_path / "src"
    src.mkdir()
    (src / "module.py").write_text(
        "\n".join(f"value_{line} = {line}" for line in range(line_count)),
        encoding="utf-8",
    )
    rules_file = tmp_path / "rules.json"
    rules_file.write_text(json.dumps(RULES), encoding="utf-8")
    return src, rules_file


def _run_cli(src: Path, rules_file: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(ROOT / "main.py"),
            "--language", "python",
            "--path", str(src),
            "--rules", str(rules_file),
            *arguments,
        ],
        capture_output=True,
        text=True,
        timeout=180,
    )


def test_clean_project_succeeds_with_strict_mode(tmp_path):
    src, rules_file = _make_project(tmp_path, line_count=2)

    result = _run_cli(src, rules_file, "--fail-on-findings")

    assert result.returncode == 0, result.stderr


def test_warning_only_fails_only_when_strict_mode_is_enabled(tmp_path):
    src, rules_file = _make_project(tmp_path, line_count=4)

    default_result = _run_cli(src, rules_file)
    strict_result = _run_cli(src, rules_file, "--fail-on-findings")

    assert default_result.returncode == 0, default_result.stderr
    assert strict_result.returncode == 1, strict_result.stderr


def test_error_fails_with_strict_mode(tmp_path):
    src, rules_file = _make_project(tmp_path, line_count=10)

    result = _run_cli(src, rules_file, "--fail-on-findings")

    assert result.returncode == 1, result.stderr


def test_json_warning_fails_with_strict_mode(tmp_path):
    src, rules_file = _make_project(tmp_path, line_count=4)

    result = _run_cli(src, rules_file, "--fail-on-findings", "--format", "json")

    assert result.returncode == 1, result.stderr
