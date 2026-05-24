from pathlib import Path

from logger import Logger
from models import LogLevel, Severity, Violation
from rules.base import BaseRule
from rules.context import RuleContext


class _NoopRule(BaseRule):
    def check(self, file_path):
        return []


def _ctx(**overrides):
    base = {
        "config": {},
        "logger": Logger(quiet=True),
    }
    base.update(overrides)
    return RuleContext(**base)


def test_match_file_path_exact_glob_endswith():
    rule = _NoopRule(_ctx())
    assert rule._match_file_path("foo/bar.py", "foo/bar.py")
    assert rule._match_file_path("foo/bar.py", "*.py")
    assert rule._match_file_path("foo/bar.py", "bar.py")
    assert not rule._match_file_path("foo/bar.py", "baz.py")


def test_get_relative_path_inside_base(tmp_path: Path):
    rule = _NoopRule(_ctx(base_path=tmp_path))
    f = tmp_path / "sub" / "x.py"
    f.parent.mkdir(parents=True)
    f.write_text("")
    assert rule._get_relative_path(f).replace("\\", "/") == "sub/x.py"


def test_get_relative_path_outside_base_returns_absolute(tmp_path: Path):
    rule = _NoopRule(_ctx(base_path=tmp_path))
    other = tmp_path.parent / "elsewhere.py"
    other.write_text("")
    assert rule._get_relative_path(other) == str(other)


def test_get_threshold_for_file_picks_matching_exception(tmp_path: Path):
    rule = _NoopRule(_ctx(base_path=tmp_path))
    f = tmp_path / "a" / "big.py"
    f.parent.mkdir(parents=True)
    f.write_text("")
    config = {
        "warning": 300,
        "error": 500,
        "exceptions": [{"file": "a/big.py", "warning": 1000, "error": 2000}],
    }
    t = rule._get_threshold_for_file(f, config)
    assert t == {"warning": 1000.0, "error": 2000.0}


def test_get_threshold_for_file_falls_back_to_base(tmp_path: Path):
    rule = _NoopRule(_ctx(base_path=tmp_path))
    f = tmp_path / "no_exception.py"
    f.write_text("")
    config = {"warning": 300, "error": 500, "exceptions": [{"file": "other.py", "warning": 9}]}
    t = rule._get_threshold_for_file(f, config)
    assert t == {"warning": 300.0, "error": 500.0}


def test_filter_violations_by_log_level_error_only():
    rule = _NoopRule(_ctx(log_level=LogLevel.ERROR))
    v_err = Violation(file_path="x.py", rule_name="r", severity=Severity.ERROR, message="m")
    v_warn = Violation(file_path="x.py", rule_name="r", severity=Severity.WARNING, message="m")
    v_info = Violation(file_path="x.py", rule_name="r", severity=Severity.INFO, message="m")
    assert rule._filter_violations_by_log_level([v_err, v_warn, v_info]) == [v_err]


def test_filter_violations_by_log_level_warning_keeps_err_and_warn():
    rule = _NoopRule(_ctx(log_level=LogLevel.WARNING))
    v_err = Violation(file_path="x.py", rule_name="r", severity=Severity.ERROR, message="m")
    v_warn = Violation(file_path="x.py", rule_name="r", severity=Severity.WARNING, message="m")
    v_info = Violation(file_path="x.py", rule_name="r", severity=Severity.INFO, message="m")
    out = rule._filter_violations_by_log_level([v_err, v_warn, v_info])
    assert out == [v_err, v_warn]
