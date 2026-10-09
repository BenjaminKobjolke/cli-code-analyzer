"""A failed tool must remain failed across cache paths."""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_dart_failure_is_not_cached_as_clean(tmp_path: Path):
    source = tmp_path / 'lib' / 'a.dart'
    source.parent.mkdir()
    source.write_text('void main() {}\n', encoding='utf-8')
    rules = tmp_path / 'rules.json'
    rules.write_text(json.dumps({'dart_analyze': {'enabled': True}}), encoding='utf-8')
    bin_dir = tmp_path / 'bin'
    bin_dir.mkdir()
    if os.name == 'nt':
        fake = bin_dir / 'dart.bat'
        fake.write_text('@echo off\necho not json\nexit /b 1\n', encoding='utf-8')
    else:
        fake = bin_dir / 'dart'
        fake.write_text('#!/bin/sh\necho not json\nexit 1\n', encoding='utf-8')
        fake.chmod(0o755)
    env = os.environ.copy()
    env['PATH'] = str(bin_dir) + os.pathsep + env.get('PATH', '')
    out = tmp_path / 'out'
    base = [sys.executable, str(ROOT / 'main.py'), '--language', 'flutter', '--path', str(tmp_path),
            '--rules', str(rules), '--output', str(out), '--format', 'json']

    for extra in (['--file', str(source)], ['--file', str(source)], ['--build-cache']):
        result = subprocess.run([*base, *extra], env=env, capture_output=True, text=True, timeout=30, check=False)
        assert result.returncode == 1, result.stdout + result.stderr
        data = json.loads(result.stdout[result.stdout.find('{'):result.stdout.rfind('}') + 1])
        assert any(f['rule_name'] == 'dart_analyze' for f in data['failures'])
        assert not (out / '_violations_cache.db').exists()
