"""Tests for PMD CPD scoping under --only-changed / --file.

Covers the --file-list vs -d command construction in _run_pmd_cpd, the
resolve_filtered_pmd_files helper (extension + exclude filtering), and the
"fewer than 2 changed files" short-circuit in _run.
"""
from pathlib import Path
from types import SimpleNamespace

from logger import Logger
from models import RuleStatus
from rules import PMDDuplicatesRule
from rules.context import RuleContext
from rules.pmd_base import resolve_filtered_pmd_files

EMPTY_CPD = '<?xml version="1.0"?><pmd-cpd></pmd-cpd>'


def _rule(tmp_path: Path, filter_files=None, language="flutter",
          filter_mode=None) -> PMDDuplicatesRule:
    return PMDDuplicatesRule(RuleContext(
        config={}, base_path=tmp_path, language=language,
        filter_files=filter_files, filter_mode=filter_mode, logger=Logger(quiet=True),
    ))


def _capture_cmd(rule):
    """Replace _run_subprocess with a spy returning empty CPD output."""
    seen = {}

    def fake(cmd, *_args, **_kwargs):
        seen['cmd'] = cmd
        if '--file-list' in cmd:
            file_list = Path(cmd[cmd.index('--file-list') + 1])
            seen['file_paths'] = {
                Path(line)
                for line in file_list.read_text(encoding="utf-8").splitlines()
            }
        return SimpleNamespace(returncode=0, stdout=EMPTY_CPD, stderr="")

    rule._run_subprocess = fake
    return seen


def test_run_pmd_cpd_uses_file_list_when_filtered(tmp_path: Path):
    a = tmp_path / "a.dart"
    a.write_text("")
    b = tmp_path / "b.dart"
    b.write_text("")
    rule = _rule(tmp_path)
    seen = _capture_cmd(rule)
    rule._run_pmd_cpd("pmd", "dart", tmp_path, 100, [], [], filtered=[a, b])
    cmd = seen['cmd']
    assert '--file-list' in cmd
    assert '-d' not in cmd


def test_run_pmd_cpd_uses_curated_file_list_when_not_filtered(tmp_path: Path):
    source = tmp_path / "source.dart"
    source.write_text("")
    cache = tmp_path / ".pytest_cache"
    cache.mkdir()
    cached_source = cache / "cached.dart"
    cached_source.write_text("")
    rule = _rule(tmp_path)
    seen = _capture_cmd(rule)
    rule._run_pmd_cpd(
        "pmd", "dart", tmp_path, 100, [".pytest_cache"], [], filtered=None,
    )
    cmd = seen['cmd']
    assert '--file-list' in cmd
    assert '-d' not in cmd
    assert source.resolve() in seen['file_paths']
    assert cached_source.resolve() not in seen['file_paths']


def test_resolve_filtered_pmd_files_filters_ext_and_excludes(tmp_path: Path):
    for name in ("keep.dart", "gen.g.dart", "note.txt"):
        (tmp_path / name).write_text("")
    rule = _rule(tmp_path, filter_files={"keep.dart", "gen.g.dart", "note.txt"})
    out = resolve_filtered_pmd_files(rule, ["*.g.dart"])
    assert out == [tmp_path / "keep.dart"]


def test_run_skips_when_fewer_than_two_changed_files(tmp_path: Path):
    a = tmp_path / "a.dart"
    a.write_text("")
    rule = _rule(tmp_path, filter_files={"a.dart"})
    # Pretend PMD is installed so we reach the filter logic.
    rule._get_tool_path = lambda *_args, **_kwargs: "pmd"
    called = {'ran': False}
    rule._run_subprocess = lambda *_args, **_kwargs: called.__setitem__('ran', True)
    result = rule._run(a)
    assert result.status == RuleStatus.OK
    assert result.violations == []
    assert called['ran'] is False  # short-circuited before invoking PMD


def test_file_filter_scans_full_curated_list_so_duplicates_can_be_found(tmp_path: Path):
    a = tmp_path / "a.dart"
    a.write_text("")
    rule = _rule(tmp_path, filter_files={"a.dart"}, filter_mode="file")
    rule._get_tool_path = lambda *_args, **_kwargs: "pmd"
    seen = _capture_cmd(rule)
    result = rule._run(a)
    assert result.status == RuleStatus.OK
    assert '--file-list' in seen['cmd']
    assert '-d' not in seen['cmd']
