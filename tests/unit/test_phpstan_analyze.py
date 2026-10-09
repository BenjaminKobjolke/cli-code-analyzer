import json
from pathlib import Path
from types import SimpleNamespace

from logger import Logger
from models import RuleStatus
from rules.context import RuleContext
from rules.phpstan_analyze import PHPStanAnalyzeRule
from rules.phpstan_config import build_phpstan_config


def _rule(tmp_path: Path, config: dict, filter_files=None) -> PHPStanAnalyzeRule:
    return PHPStanAnalyzeRule(RuleContext(
        config=config,
        base_path=tmp_path,
        filter_files=filter_files,
        logger=Logger(quiet=True),
    ))


def test_build_phpstan_config_includes_project_config_and_excludes(tmp_path: Path):
    neon = build_phpstan_config(
        tmp_path / "phpstan.neon",
        [(tmp_path / "tools" / "phpstan-bootstrap.php").as_posix()],
        [(tmp_path / "vendor").as_posix()],
    )

    assert "includes:" in neon
    assert f"- {(tmp_path / 'phpstan.neon').as_posix()}" in neon
    assert "bootstrapFiles:" in neon
    assert f"- {(tmp_path / 'tools' / 'phpstan-bootstrap.php').as_posix()}" in neon
    assert "excludePaths:" in neon
    assert f"- {(tmp_path / 'vendor').as_posix()} (?)" in neon


def test_run_phpstan_uses_bootstrap_files_with_changed_file_scope(tmp_path: Path):
    bootstrap = tmp_path / "tools" / "phpstan-bootstrap.php"
    bootstrap.parent.mkdir()
    bootstrap.write_text("<?php\n", encoding="utf-8")
    changed = tmp_path / "src" / "Changed.php"
    changed.parent.mkdir()
    changed.write_text("<?php\n", encoding="utf-8")

    rule = _rule(
        tmp_path,
        {
            "level": 5,
            "bootstrap_files": ["tools/phpstan-bootstrap.php"],
            "exclude_patterns": ["vendor/**"],
        },
        filter_files={"src/Changed.php"},
    )

    seen = {}

    def fake_run(cmd, *_args, **_kwargs):
        seen["cmd"] = cmd
        config_path = Path(cmd[cmd.index("-c") + 1])
        seen["config"] = config_path.read_text(encoding="utf-8")
        return SimpleNamespace(returncode=0, stdout='{"totals":{"errors":0,"file_errors":0},"files":[],"errors":[]}', stderr="")

    rule._run_subprocess = fake_run

    result = rule._run_phpstan_check("phpstan")

    assert result.status == RuleStatus.OK
    assert result.violations == []
    assert "-c" in seen["cmd"]
    assert str(changed) in seen["cmd"]
    assert "bootstrapFiles:" in seen["config"]
    assert f"- {bootstrap.as_posix()}" in seen["config"]
    assert f"- {(tmp_path / 'vendor').as_posix()} (?)" in seen["config"]


def test_phpstan_merges_batches_and_empty_files_list(tmp_path: Path, monkeypatch):
    monkeypatch.setattr('rules.filter_scope.MAX_COMMAND_CHARS', 240)
    names = {f'deep/{i:03d}_long_name.php' for i in range(4)}
    for name in names:
        path = tmp_path / name
        path.parent.mkdir(exist_ok=True)
        path.touch()
    rule = _rule(tmp_path, {}, filter_files=names)
    calls = []

    def run(cmd, _cwd):
        calls.append(cmd)
        paths = [p for p in cmd if p.endswith('.php')]
        files = {p: {'messages': [{'message': 'bad', 'line': 1}]} for p in paths} if len(calls) > 1 else []
        return SimpleNamespace(returncode=1, stdout=json.dumps({'files': files, 'errors': []}), stderr='')

    rule._run_subprocess = run
    result = rule._run_phpstan_check('phpstan')
    assert result.status == RuleStatus.OK
    assert len(calls) > 1
    assert result.violations


def test_phpstan_empty_output_fails(tmp_path: Path):
    rule = _rule(tmp_path, {})
    rule._run_subprocess = lambda *_args: SimpleNamespace(returncode=1, stdout='', stderr='bad config')
    assert rule._run_phpstan_check('phpstan').status == RuleStatus.FAILED


def test_phpstan_rejects_missing_or_mistyped_file_messages(tmp_path: Path):
    rule = _rule(tmp_path, {})
    for files in ('{"some.php": {}}', '{"some.php": {"messages": {}}}'):
        output = json.dumps({'files': json.loads(files), 'errors': []})
        rule._run_subprocess = lambda *_args, output=output: SimpleNamespace(
            returncode=0, stdout=output, stderr='')
        assert rule._run_phpstan_check('phpstan').status == RuleStatus.FAILED


def test_phpstan_merges_file_errors_from_each_batch(tmp_path: Path, monkeypatch):
    monkeypatch.setattr('rules.filter_scope.MAX_COMMAND_CHARS', 240)
    names = {f'deep/{i:03d}_long_name.php' for i in range(4)}
    for name in names:
        path = tmp_path / name
        path.parent.mkdir(exist_ok=True)
        path.touch()
    rule = _rule(tmp_path, {}, filter_files=names)
    calls = []

    def run(cmd, _cwd):
        calls.append(cmd)
        files = {p: {'messages': [{'message': 'bad', 'line': 1}]} for p in cmd if p.endswith('.php')}
        return SimpleNamespace(returncode=1, stdout=json.dumps({'files': files, 'errors': []}), stderr='')

    rule._run_subprocess = run
    result = rule._run_phpstan_check('phpstan')
    assert result.status == RuleStatus.OK
    assert len(calls) > 1
    assert len(result.violations) == 4


def test_phpstan_cleans_temp_config_when_scope_empty(tmp_path: Path, monkeypatch):
    bootstrap = tmp_path / 'bootstrap.php'
    bootstrap.touch()
    rule = _rule(tmp_path, {'bootstrap_files': ['bootstrap.php']}, filter_files={'missing.dart'})
    created = []
    import rules.phpstan_analyze as module
    original = module.tempfile.mkstemp

    def make_temp(*args, **kwargs):
        fd, path = original(*args, **kwargs)
        created.append(path)
        return fd, path

    monkeypatch.setattr(module.tempfile, 'mkstemp', make_temp)
    assert rule._run_phpstan_check('phpstan').status == RuleStatus.OK
    assert created and not Path(created[0]).exists()
