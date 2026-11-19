import json
from pathlib import Path
from types import SimpleNamespace

from logger import Logger
from models import RuleStatus
from rules.context import RuleContext
from rules.eslint_analyze import ESLintAnalyzeRule


def _rule(tmp_path: Path, count: int = 1) -> ESLintAnalyzeRule:
    names = {f'deep/{i:03d}_long_name.js' for i in range(count)}
    for name in names:
        path = tmp_path / name
        path.parent.mkdir(exist_ok=True)
        path.touch()
    return ESLintAnalyzeRule(RuleContext(config={'extensions': ['.js']}, base_path=tmp_path,
                                         filter_files=names, max_errors=2, logger=Logger(quiet=True)))


def test_eslint_merges_batches_then_caps(tmp_path: Path, monkeypatch):
    monkeypatch.setattr('rules.filter_scope.MAX_COMMAND_CHARS', 220)
    rule = _rule(tmp_path, 4)
    calls = []

    def run(cmd, _cwd):
        calls.append(cmd)
        data = [{'filePath': p, 'messages': [{'ruleId': 'no-unused-vars', 'message': 'unused',
                                             'line': 1, 'column': 1, 'severity': 2}]} for p in cmd[4:]]
        return SimpleNamespace(returncode=1, stdout=json.dumps(data), stderr='')

    rule._run_subprocess = run
    result = rule._run_eslint_check('eslint')
    assert result.status == RuleStatus.OK
    assert len(calls) > 1
    assert len(result.violations) == 2


def test_eslint_rejects_untrusted_output(tmp_path: Path):
    rule = _rule(tmp_path)
    for output in ('', 'not json', '{}'):
        rule._run_subprocess = lambda *_args, output=output: SimpleNamespace(
            returncode=1, stdout=output, stderr='bad start')
        assert rule._run_eslint_check('eslint').status == RuleStatus.FAILED
    rule._run_subprocess = lambda *_args: SimpleNamespace(returncode=0, stdout='[]', stderr='')
    assert rule._run_eslint_check('eslint').violations == []


def test_eslint_rejects_missing_or_mistyped_file_fields(tmp_path: Path):
    rule = _rule(tmp_path)
    for output in ('[{}]', '[{"filePath": "a.js"}]', '[{"filePath": 1, "messages": []}]',
                   '[{"filePath": "a.js", "messages": {}}]'):
        rule._run_subprocess = lambda *_args, output=output: SimpleNamespace(
            returncode=0, stdout=output, stderr='')
        assert rule._run_eslint_check('eslint').status == RuleStatus.FAILED


def _monorepo(tmp_path: Path, filter_files: set[str] | None) -> ESLintAnalyzeRule:
    """Two packages with their own flat config, none at the root (pnpm/npm workspaces)."""
    for name in ('frontend/eslint.config.js', 'backend/eslint.config.js',
                 'frontend/src/a.ts', 'backend/src/b.ts', 'vitest.config.ts',
                 'frontend/node_modules/pkg/eslint.config.js'):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
    (tmp_path / 'package.json').write_text('{}', encoding='utf-8')
    # The workspace's ESLint sits at the root; neither package has its own.
    root_bin = tmp_path / 'node_modules' / '.bin'
    root_bin.mkdir(parents=True)
    for name in ('eslint', 'eslint.cmd'):
        (root_bin / name).touch()
    return ESLintAnalyzeRule(RuleContext(config={'extensions': ['.ts']}, base_path=tmp_path,
                                         filter_files=filter_files, logger=Logger(quiet=True)))


def _recording_eslint(rule: ESLintAnalyzeRule) -> list[tuple[list[str], Path]]:
    calls: list[tuple[list[str], Path]] = []

    def run(cmd, cwd):
        calls.append((cmd, Path(cwd)))
        root = Path(cwd)
        data = [{'filePath': str(root / 'src' / 'x.ts'),
                 'messages': [{'ruleId': 'no-undef', 'message': 'undefined', 'line': 1,
                               'column': 1, 'severity': 2}]}]
        return SimpleNamespace(returncode=1, stdout=json.dumps(data), stderr='')

    rule._run_subprocess = run
    return calls


def test_eslint_runs_once_per_package_without_a_root_config(tmp_path: Path):
    rule = _monorepo(tmp_path, None)
    calls = _recording_eslint(rule)

    result = rule._run(tmp_path)

    assert result.status == RuleStatus.OK
    assert sorted(cwd.name for _cmd, cwd in calls) == ['backend', 'frontend']
    for cmd, cwd in calls:
        assert cmd[-1] == str(cwd)
    assert {Path(violation.file_path).as_posix() for violation in result.violations} == {
        'backend/src/x.ts', 'frontend/src/x.ts'}


def test_eslint_packages_get_only_their_own_changed_files(tmp_path: Path):
    rule = _monorepo(tmp_path, {'frontend/src/a.ts', 'vitest.config.ts'})
    calls = _recording_eslint(rule)

    rule._run(tmp_path)

    assert len(calls) == 1
    cmd, cwd = calls[0]
    assert cwd.name == 'frontend'
    assert cmd[-1] == str(tmp_path / 'frontend' / 'src' / 'a.ts')
