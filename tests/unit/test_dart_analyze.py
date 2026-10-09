import csv
import json
from pathlib import Path
from types import SimpleNamespace

from logger import Logger
from models import RuleStatus
from rules.context import RuleContext
from rules.dart_analyze import DartAnalyzeRule


def _rule(tmp_path: Path, count: int = 2, output: bool = False) -> DartAnalyzeRule:
    names = {f"deep/{i:03d}_long_name.dart" for i in range(count)}
    for name in names:
        path = tmp_path / name
        path.parent.mkdir(exist_ok=True)
        path.touch()
    out = tmp_path / 'out' if output else None
    if out:
        out.mkdir()
    return DartAnalyzeRule(RuleContext(config={}, base_path=tmp_path, filter_files=names,
                                       logger=Logger(quiet=True), output_folder=out))


def _diagnostic(path: str) -> dict:
    return {'code': 'unused_local_variable', 'severity': 'WARNING', 'problemMessage': 'unused',
            'location': {'file': path, 'range': {'start': {'line': 1, 'column': 1}}}}


def test_dart_merges_batches_and_csv(tmp_path: Path, monkeypatch):
    monkeypatch.setattr('rules.filter_scope.MAX_COMMAND_CHARS', 230)
    rule = _rule(tmp_path, 4, output=True)
    calls = []

    def run(cmd, _cwd):
        calls.append(cmd)
        return SimpleNamespace(returncode=1, stdout=json.dumps({'diagnostics': [_diagnostic(p) for p in cmd[4:]]}), stderr='')

    rule._run_subprocess = run
    result = rule._run_dart_analyze(['dart'])
    assert result.status == RuleStatus.OK
    assert len(calls) > 1
    assert len(result.violations) == 4
    with (tmp_path / 'out' / 'dart_analyze.csv').open(newline='', encoding='utf-8') as f:
        assert len(list(csv.reader(f))) == 5


def test_dart_rejects_untrusted_output(tmp_path: Path):
    rule = _rule(tmp_path, 1)
    for stdout, stderr in [('', 'The command line is too long.'), ('not json', ''), ('[]', '')]:
        rule._run_subprocess = lambda *_args, stdout=stdout, stderr=stderr: SimpleNamespace(
            returncode=1, stdout=stdout, stderr=stderr)
        result = rule._run_dart_analyze(['dart'])
        assert result.status == RuleStatus.FAILED
        assert 'dart analyze' in result.message
        if stderr:
            assert stderr in result.message


def test_dart_small_scope_uses_one_command(tmp_path: Path):
    rule = _rule(tmp_path, 1)
    calls = []

    def run(cmd, _cwd):
        calls.append(cmd)
        return SimpleNamespace(returncode=1, stdout=json.dumps({'diagnostics': [_diagnostic(cmd[-1])]}), stderr='')

    rule._run_subprocess = run
    result = rule._run_dart_analyze(['dart'])
    assert result.status == RuleStatus.OK
    assert len(calls) == len(result.violations) == 1
