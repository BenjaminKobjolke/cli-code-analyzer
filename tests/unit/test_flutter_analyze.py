from pathlib import Path
from types import SimpleNamespace

from logger import Logger
from models import RuleStatus
from rules.context import RuleContext
from rules.flutter_analyze import FlutterAnalyzeRule


def _rule(tmp_path: Path, count: int = 1) -> FlutterAnalyzeRule:
    names = {f'deep/{i:03d}_long_name.dart' for i in range(count)}
    for name in names:
        path = tmp_path / name
        path.parent.mkdir(exist_ok=True)
        path.touch()
    return FlutterAnalyzeRule(RuleContext(config={}, base_path=tmp_path, filter_files=names, logger=Logger(quiet=True)))


def test_flutter_merges_batches(tmp_path: Path, monkeypatch):
    monkeypatch.setattr('rules.filter_scope.MAX_COMMAND_CHARS', 220)
    rule = _rule(tmp_path, 4)
    calls = []

    def run(cmd, _cwd):
        calls.append(cmd)
        path = cmd[-1]
        output = f'warning - unused - {path}:1:1 - unused_local_variable\n'
        return SimpleNamespace(returncode=1, stdout=output, stderr='')

    rule._run_subprocess = run
    result = rule._run_flutter_analyze(['flutter'])
    assert result.status == RuleStatus.OK
    assert len(calls) > 1
    assert len(result.violations) == len(calls)


def test_flutter_distinguishes_errors_from_issues(tmp_path: Path):
    rule = _rule(tmp_path)
    for code, output, status in [(1, 'The command line is too long.', RuleStatus.FAILED),
                                 (0, 'No issues found!', RuleStatus.OK),
                                 (1, 'warning - unused - foo.dart:1:1 - unused_local_variable', RuleStatus.OK)]:
        rule._run_subprocess = lambda *_args, code=code, output=output: SimpleNamespace(
            returncode=code, stdout=output, stderr='')
        assert rule._run_flutter_analyze(['flutter']).status == status
