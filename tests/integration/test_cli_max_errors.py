import csv
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# max_lines_per_file is a built-in rule (no external tools), so this test is
# deterministic on any machine. error threshold = 5 lines below.
RULES = {
    "log_level": "all",
    "max_errors": 2,
    "max_lines_per_file": {"enabled": True, "warning": 3, "error": 5},
}


def _make_project(tmp_path, file_count):
    src = tmp_path / "src"
    src.mkdir()
    for i in range(file_count):
        # 10 lines each -> exceeds the error threshold of 5.
        (src / f"mod_{i}.py").write_text("\n".join(f"x{i}_{n} = {n}" for n in range(10)), encoding="utf-8")
    rules_file = tmp_path / "rules.json"
    rules_file.write_text(json.dumps(RULES), encoding="utf-8")
    return src, rules_file


def test_rules_json_max_errors_caps_per_rule_csv(tmp_path):
    # 5 files -> 5 max_lines violations of the same rule type.
    src, rules_file = _make_project(tmp_path, file_count=5)
    output = tmp_path / "reports"
    cmd = [
        sys.executable,
        str(ROOT / "main.py"),
        "--language", "python",
        "--path", str(src),
        "--rules", str(rules_file),
        "--output", str(output),
        # NOTE: no -m flag, so the cap must come from rules.json "max_errors".
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    assert result.returncode in (0, 1), f"stderr={result.stderr}"

    report = output / "line_count_report.csv"
    assert report.exists(), f"missing report; stdout={result.stdout}"
    with open(report, encoding="utf-8") as f:
        rows = list(csv.reader(f))
    # Header + at most max_errors (2) data rows, despite 5 violations existing.
    assert len(rows) == 3, f"expected header + 2 capped rows, got {rows}"
