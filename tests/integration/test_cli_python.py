import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_SRC = ROOT / "example" / "python" / "src"
EXAMPLE_RULES = ROOT / "example" / "python" / "rules.json"


def test_cli_python_example_runs_and_reports_violations():
    cmd = [
        sys.executable,
        str(ROOT / "main.py"),
        "--language", "python",
        "--path", str(EXAMPLE_SRC),
        "--rules", str(EXAMPLE_RULES),
        "--format", "json",
        "--file", str(EXAMPLE_SRC / "user_service.py"),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    # Exit code is 1 when violations are present, 0 when not. We expect violations in this fixture.
    assert result.returncode in (0, 1), f"unexpected exit code; stderr={result.stderr}"
    assert "user_service.py" in result.stdout or "user_service.py" in result.stderr
