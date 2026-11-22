import json
from pathlib import Path
from types import SimpleNamespace

from exception_baseline import ExceptionBaseline
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


def test_ruff_skips_explicit_filter_files_excluded_by_config(tmp_path: Path):
    target = tmp_path / "vend" / "thing.py"
    target.parent.mkdir()
    target.touch()
    rule = RuffAnalyzeRule(RuleContext(
        config={"exclude_patterns": ["vend/**"]},
        base_path=tmp_path,
        filter_files={"vend/thing.py"},
        max_errors=2,
        logger=Logger(quiet=True),
    ))
    calls = []

    def run(cmd, _cwd):
        calls.append(cmd)
        return SimpleNamespace(returncode=0, stdout="[]", stderr="")

    rule._run_subprocess = run
    result = rule._run_ruff_check("ruff")

    assert result.status == RuleStatus.OK
    assert calls == []


def test_ruff_rejects_untrusted_output(tmp_path: Path):
    rule = _rule(tmp_path)
    for output in ('', 'not json', '{}'):
        rule._run_subprocess = lambda *_args, output=output: SimpleNamespace(
            returncode=1, stdout=output, stderr='bad start')
        assert rule._run_ruff_check('ruff').status == RuleStatus.FAILED
    rule._run_subprocess = lambda *_args: SimpleNamespace(returncode=0, stdout='[]', stderr='')
    assert rule._run_ruff_check('ruff').violations == []


def test_ruff_tracks_noqa_suppressed_complexity(tmp_path: Path):
    source = tmp_path / 'example.py'
    source.write_text('def complicated():  # noqa: C901\n    pass\n', encoding='utf-8')
    baseline = ExceptionBaseline(tmp_path / 'rules.exception_baseline.json')
    rule = RuffAnalyzeRule(RuleContext(
        config={}, base_path=tmp_path, filter_files={'example.py'},
        logger=Logger(quiet=True), exception_baseline=baseline,
    ))
    calls = []
    diagnostic = {
        'code': 'C901', 'filename': str(source),
        'location': {'row': 1, 'column': 1},
        'message': "'complicated' is too complex (15 > 10)",
    }

    def run(cmd, _cwd):
        calls.append(cmd)
        output = '[]' if len(calls) == 1 else json.dumps([diagnostic])
        return SimpleNamespace(returncode=0, stdout=output, stderr='')

    rule._run_subprocess = run
    result = rule._run_ruff_check('ruff')

    assert result.status == RuleStatus.OK
    assert len(calls) == 2
    assert '--ignore-noqa' in calls[1]
    assert '--select' in calls[1]
    assert calls[1][calls[1].index('--select') + 1] == 'C901,PLR0911,PLR0912,PLR0915'
    baseline.save()
    [entry] = json.loads(baseline.path.read_text(encoding='utf-8'))['entries']
    assert entry['rule'] == 'ruff_analyze'
    assert entry['file'] == 'example.py'
    assert entry['function'] == 'complicated'
    assert entry['metric'] == 'C901'
    assert entry['value'] == 15


def test_ruff_suppression_scan_failure_fails_rule(tmp_path: Path):
    source = tmp_path / 'example.py'
    source.write_text('def complicated():  # noqa\n    pass\n', encoding='utf-8')
    rule = RuffAnalyzeRule(RuleContext(
        config={}, base_path=tmp_path, filter_files={'example.py'},
        logger=Logger(quiet=True), exception_baseline=ExceptionBaseline(tmp_path / 'baseline.json'),
    ))
    calls = 0

    def run(_cmd, _cwd):
        nonlocal calls
        calls += 1
        if calls == 1:
            return SimpleNamespace(returncode=0, stdout='[]', stderr='')
        return SimpleNamespace(returncode=2, stdout='[]', stderr='ruff failed')

    rule._run_subprocess = run
    result = rule._run_ruff_check('ruff')

    assert result.status == RuleStatus.FAILED
    assert result.violations == []
