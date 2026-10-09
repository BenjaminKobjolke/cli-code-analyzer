"""Tests for filter-file scoping: BaseRule._filtered_paths / _scope_args and
the PMD CPD --file-list command construction used under --only-changed / --file.
"""
from pathlib import Path
from subprocess import list2cmdline
from types import SimpleNamespace

import pytest

from logger import Logger
from rules.base import BaseRule
from rules.context import RuleContext
from rules.filter_scope import MAX_COMMAND_CHARS, ToolOutputError


class _NoopRule(BaseRule):
    def check(self, _file_path):
        return []


def _ctx(**overrides):
    base = {"config": {}, "logger": Logger(quiet=True)}
    base.update(overrides)
    return RuleContext(**base)


def _touch(tmp_path: Path, *names: str) -> None:
    for name in names:
        p = tmp_path / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("")


# --- _filtered_paths -------------------------------------------------------

def test_filtered_paths_none_when_no_filter(tmp_path: Path):
    rule = _NoopRule(_ctx(base_path=tmp_path))
    assert rule._filtered_paths(('.py',)) is None


def test_filtered_paths_empty_when_no_matching_extension(tmp_path: Path):
    _touch(tmp_path, "a.dart")
    rule = _NoopRule(_ctx(base_path=tmp_path, filter_files={"a.dart"}))
    assert rule._filtered_paths(('.py',)) == []


def test_filtered_paths_returns_existing_matches_only(tmp_path: Path):
    _touch(tmp_path, "src/a.py")  # exists; "src/gone.py" intentionally not created
    rule = _NoopRule(_ctx(base_path=tmp_path, filter_files={"src/a.py", "src/gone.py"}))
    out = rule._filtered_paths(('.py',))
    assert out == [tmp_path / "src" / "a.py"]


# --- _scope_args -----------------------------------------------------------

def test_scope_args_whole_project_fallback_when_no_filter(tmp_path: Path):
    rule = _NoopRule(_ctx(base_path=tmp_path))
    assert rule._scope_args(('.py',), [str(tmp_path)]) == [str(tmp_path)]


def test_scope_args_cwd_based_whole_project_is_empty(tmp_path: Path):
    rule = _NoopRule(_ctx(base_path=tmp_path))
    assert rule._scope_args(('.dart',)) == []


def test_scope_args_none_signals_skip_when_filter_has_no_match(tmp_path: Path):
    _touch(tmp_path, "a.dart")
    rule = _NoopRule(_ctx(base_path=tmp_path, filter_files={"a.dart"}))
    assert rule._scope_args(('.py',), [str(tmp_path)]) is None


def test_scope_args_returns_file_paths_when_filtered(tmp_path: Path):
    _touch(tmp_path, "a.py", "b.py")
    rule = _NoopRule(_ctx(base_path=tmp_path, filter_files={"a.py"}))
    assert rule._scope_args(('.py',), [str(tmp_path)]) == [str(tmp_path / "a.py")]


def test_scoped_commands_preserve_whole_project_and_empty_filter(tmp_path: Path):
    rule = _NoopRule(_ctx(base_path=tmp_path))
    assert rule._scoped_commands(['tool'], ('.py',)) == [['tool']]
    assert rule._scoped_commands(['tool'], ('.py',), [str(tmp_path)]) == [['tool', str(tmp_path)]]
    rule.filter_files = {'missing.dart'}
    assert rule._scoped_commands(['tool'], ('.py',)) is None


def test_scoped_commands_batch_long_file_lists(tmp_path: Path):
    names = {f"deep/folder_{i:03d}_long_name/file_{i:03d}_long_name.dart" for i in range(150)}
    _touch(tmp_path, *names)
    rule = _NoopRule(_ctx(base_path=tmp_path, filter_files=names))
    commands = rule._scoped_commands(['dart', 'analyze'], ('.dart',))
    assert len(commands) > 1
    assert all(c[:2] == ['dart', 'analyze'] and len(list2cmdline(c)) <= MAX_COMMAND_CHARS for c in commands)
    assert sorted(path for c in commands for path in c[2:]) == sorted(str(tmp_path / n) for n in names)


def test_scoped_commands_keep_small_scope_together_and_reject_one_oversize_path(tmp_path: Path, monkeypatch):
    _touch(tmp_path, 'a.py', 'b.py')
    rule = _NoopRule(_ctx(base_path=tmp_path, filter_files={'a.py', 'b.py'}))
    commands = rule._scoped_commands(['tool'], ('.py',))
    assert len(commands) == 1
    assert set(commands[0][1:]) == {str(tmp_path / 'a.py'), str(tmp_path / 'b.py')}
    monkeypatch.setattr('rules.filter_scope.MAX_COMMAND_CHARS', 5)
    with pytest.raises(ToolOutputError, match='a.py|b.py'):
        rule._scoped_commands(['tool'], ('.py',))


def test_run_json_rejects_untrusted_output(tmp_path: Path):
    rule = _NoopRule(_ctx(base_path=tmp_path))
    rule._run_subprocess = lambda *_args: SimpleNamespace(returncode=0, stdout='[]', stderr='')
    assert rule._run_json('tool', [['tool']], tmp_path) == [[]]
    for code in (0, 1):
        rule._run_subprocess = lambda *_args, code=code: SimpleNamespace(
            returncode=code, stdout='', stderr='bad start')
        with pytest.raises(ToolOutputError, match='tool.*bad start'):
            rule._run_json('tool', [['tool']], tmp_path)
    rule._run_subprocess = lambda *_args: SimpleNamespace(returncode=1, stdout='not json', stderr='')
    with pytest.raises(ToolOutputError, match='tool JSON'):
        rule._run_json('tool', [['tool']], tmp_path)


def test_run_json_returns_one_document_per_command(tmp_path: Path):
    rule = _NoopRule(_ctx(base_path=tmp_path))
    rule._run_subprocess = lambda cmd, _cwd: SimpleNamespace(returncode=0, stdout=f'[{cmd[1]}]', stderr='')
    assert rule._run_json('tool', [['tool', '1'], ['tool', '2']], tmp_path) == [[1], [2]]
