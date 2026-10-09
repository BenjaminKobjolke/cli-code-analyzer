"""Native-tool smoke test for the Dart pipeline.

Proves the dart_analyze rule runs through the real CLI and returns a genuine
OK/violations result (not a FAILED). Skips when the dart SDK is absent so CI
without Dart does not fail.
"""
import importlib.util
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


@pytest.mark.skipif(shutil.which('dart') is None or shutil.which('git') is None,
                    reason='dart SDK or git not installed')
def test_cli_dart_analyzes_large_changed_scope(tmp_path):
    subprocess.run(['git', 'init', '-q', str(tmp_path)], check=True, timeout=10)
    rules = tmp_path / 'rules.json'
    rules.write_text(json.dumps({'dart_analyze': {'enabled': True}}), encoding='utf-8')
    paths = []
    for i in range(125):
        path = tmp_path / 'deep_long_folder_name' / f'file_{i:03d}_with_long_name.dart'
        path.parent.mkdir(exist_ok=True)
        path.write_text(f'void function{i}() {{ var unusedVariable = 1; }}\n', encoding='utf-8')
        paths.append(path)
    cmd = [sys.executable, str(ROOT / 'main.py'), '--language', 'flutter', '--path', str(tmp_path),
           '--rules', str(rules), '--format', 'json', '--only-changed', '--maxamountoferrors', '200']
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120, check=False)
    data = json.loads(result.stdout[result.stdout.find('{'):result.stdout.rfind('}') + 1])
    assert not data['failures'], data['failures']
    found = {v['file_path'].replace('\\', '/') for v in data['violations'] if v['rule_name'] == 'dart_analyze'}
    assert found == {str(p.relative_to(tmp_path)).replace('\\', '/') for p in paths}


@pytest.mark.skipif(shutil.which('dart') is None or importlib.util.find_spec('dart_lsp_watcher') is None,
                    reason='dart SDK or dart-lsp-mcp not installed')
def test_cli_dart_unused_code_confirms_source_references(tmp_path):
    (tmp_path / 'pubspec.yaml').write_text('name: unused_code_fixture\n', encoding='utf-8')
    lib = tmp_path / 'lib'
    lib.mkdir()
    (lib / 'keys.dart').write_text(
        'class Keys {\n  Keys._();\n  static const member = 1;\n}\n', encoding='utf-8')
    (lib / 'app.dart').write_text("import 'keys.dart';\nfinal value = Keys.member;\n", encoding='utf-8')
    (lib / 'dead.dart').write_text('class Dead { Dead(); }\n', encoding='utf-8')
    rules = tmp_path / 'rules.json'
    rules.write_text(json.dumps({'dart_unused_code': {'enabled': True}}), encoding='utf-8')
    cmd = [sys.executable, str(ROOT / 'main.py'), '--language', 'flutter', '--path', str(tmp_path),
           '--rules', str(rules), '--format', 'json', '--maxamountoferrors', '50']
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=180, check=False)
    data = json.loads(result.stdout[result.stdout.find('{'):result.stdout.rfind('}') + 1])
    assert not data['failures'], data['failures']
    messages = [v['message'] for v in data['violations'] if v['rule_name'] == 'dart_unused_code']
    assert any("Unused class 'Dead'" in message for message in messages)
    assert not any("Unused class 'Keys'" in message for message in messages)
