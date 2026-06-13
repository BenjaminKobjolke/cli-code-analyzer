"""Native-tool smoke test for the Dart pipeline.

Proves the dart_analyze rule runs through the real CLI and returns a genuine
OK/violations result (not a FAILED). Skips when the dart SDK is absent so CI
without Dart does not fail.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).parent / "fixtures" / "flutter"


@pytest.mark.skipif(shutil.which("dart") is None, reason="dart SDK not installed")
def test_cli_dart_runs_dart_analyze_without_tool_failure(tmp_path):
    rules = {"dart_analyze": {"enabled": True}}
    rules_file = tmp_path / "rules.json"
    rules_file.write_text(json.dumps(rules), encoding="utf-8")
    cmd = [
        sys.executable, str(ROOT / "main.py"),
        "--language", "flutter",
        "--path", str(FIXTURE),
        "--rules", str(rules_file),
        "--format", "json",
        "--file", str(FIXTURE / "a.dart"),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    text = result.stdout.strip()
    start = text.find("{")
    assert start != -1, f"no JSON in stdout; stdout={result.stdout[:500]} stderr={result.stderr[:300]}"
    data = json.loads(text[start:])
    # The rule ran; it must not report itself as a failed/untrusted tool.
    assert not data.get("failures"), f"unexpected tool failure {data.get('failures')}"
