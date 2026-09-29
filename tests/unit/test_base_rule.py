import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from logger import Logger
from models import LogLevel, Severity, Violation
from rules.base import BaseRule
from rules.context import RuleContext


class _NoopRule(BaseRule):
    def check(self, _file_path):
        return []


def _ctx(**overrides):
    base = {
        "config": {},
        "logger": Logger(quiet=True),
    }
    base.update(overrides)
    return RuleContext(**base)


def _process_exists(pid: int) -> bool:
    if sys.platform == "win32":
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            check=False,
        )
        return f'"{pid}"' in result.stdout
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def _force_kill(pid: int) -> None:
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/T", "/F", "/PID", str(pid)],
            capture_output=True,
            check=False,
        )
    else:
        os.kill(pid, signal.SIGKILL)


def test_run_subprocess_timeout_kills_grandchild(tmp_path: Path):
    pid_file = tmp_path / "grandchild.pid"
    code = (
        "import pathlib, subprocess, sys, time; "
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'], "
        "stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); "
        "pathlib.Path(sys.argv[1]).write_text(str(child.pid)); time.sleep(60)"
    )
    rule = _NoopRule(_ctx())

    with pytest.raises(subprocess.TimeoutExpired):
        rule._run_subprocess([sys.executable, "-c", code, str(pid_file)], timeout=3)

    child_pid = int(pid_file.read_text())
    deadline = time.monotonic() + 5
    while _process_exists(child_pid) and time.monotonic() < deadline:
        time.sleep(0.1)
    gone = not _process_exists(child_pid)
    if not gone:
        _force_kill(child_pid)
    assert gone


def test_run_subprocess_returns_completed_process():
    result = _NoopRule(_ctx())._run_subprocess(
        [sys.executable, "-c", "print('done')"]
    )

    assert isinstance(result, subprocess.CompletedProcess)
    assert result.returncode == 0
    assert result.stdout.strip() == "done"


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
    assert t == {"warning": 1000.0, "error": 2000.0, "info": None}


def test_get_threshold_for_file_falls_back_to_base(tmp_path: Path):
    rule = _NoopRule(_ctx(base_path=tmp_path))
    f = tmp_path / "no_exception.py"
    f.write_text("")
    config = {"warning": 300, "error": 500, "exceptions": [{"file": "other.py", "warning": 9}]}
    t = rule._get_threshold_for_file(f, config)
    assert t == {"warning": 300.0, "error": 500.0, "info": None}


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
