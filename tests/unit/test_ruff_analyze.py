import json
from pathlib import Path
from types import SimpleNamespace

from logger import Logger
from models import RuleStatus
from rules.context import RuleContext
from rules.ruff_analyze import RuffAnalyzeRule


def _rule(tmp_path: Path, count: int = 1) -> RuffAnalyzeRule:
    names = {f'deep/{i:03d}_long_name.py' for i in range(count)}
    for name in names:
        path = tmp_path / name
        path.parent.mkdir(exist_ok=True)
        path.touch()
    return RuffAnalyzeRule(RuleContext(config={}, base_path=tmp_path, filter_files=names,
                                       max_errors=2, logger=Logger(quiet=True)))


def test_ruff_merges_batches_then_caps(tmp_path: Path, monkeypatch):
    monkeypatch.setattr('rules.filter_scope.MAX_COMMAND_CHARS', 220)
    rule = _rule(tmp_path, 4)
    calls = []

    def run(cmd, _cwd):
        calls.append(cmd)
        data = [{'code': 'F401', 'message': 'unused', 'filename': p,
                 'location': {'row': 1, 'column': 1}} for p in cmd[4:]]
        return SimpleNamespace(returncode=1, stdout=json.dumps(data), stderr='')

    rule._run_subprocess = run
    result = rule._run_ruff_check('ruff')
    assert result.status == RuleStatus.OK
    assert len(calls) > 1
    assert len(result.violations) == 2


def test_ruff_rejects_untrusted_output(tmp_path: Path):
    rule = _rule(tmp_path)
    for output in ('', 'not json', '{}'):
        rule._run_subprocess = lambda *_args, output=output: SimpleNamespace(
            returncode=1, stdout=output, stderr='bad start')
        assert rule._run_ruff_check('ruff').status == RuleStatus.FAILED
    rule._run_subprocess = lambda *_args: SimpleNamespace(returncode=0, stdout='[]', stderr='')
    assert rule._run_ruff_check('ruff').violations == []
