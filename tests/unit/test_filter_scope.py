"""Tests for filter-file scoping: BaseRule._filtered_paths / _scope_args and
the PMD CPD --file-list command construction used under --only-changed / --file.
"""
from pathlib import Path

from logger import Logger
from rules.base import BaseRule
from rules.context import RuleContext


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
