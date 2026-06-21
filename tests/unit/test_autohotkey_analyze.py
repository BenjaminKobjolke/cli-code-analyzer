"""Unit specs for AutoHotkeyAnalyzeRule.

Covers stderr parsing, version detection, #Include root detection, interpreter
command shape (+ cwd), and the missing-interpreter skip path. The real AHK
interpreter is never invoked: _get_tool_path / _run_subprocess are stubbed.
"""
import subprocess
from pathlib import Path

from logger import Logger
from models import RuleStatus, Severity
from rules.autohotkey_analyze import AutoHotkeyAnalyzeRule
from rules.context import RuleContext


def _make_rule(base_path: Path, filter_files=None) -> AutoHotkeyAnalyzeRule:
    ctx = RuleContext(
        config={},
        base_path=Path(base_path).resolve(),
        logger=Logger(quiet=True),
        filter_files=filter_files,
    )
    return AutoHotkeyAnalyzeRule(ctx)


def _completed(stderr: str, code: int = 2) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=["ahk"], returncode=code, stdout="", stderr=stderr)


# ----------------------------------------------------------------- stderr parsing

def test_parse_single_error_with_continuation(tmp_path):
    rule = _make_rule(tmp_path)
    f = tmp_path / "script.ahk"
    stderr = (
        f'{f} (12) : ==> Missing close-quote\n'
        '     Specifically: "unterminated\n'
    )
    violations = rule._parse_stderr(stderr)
    assert len(violations) == 1
    v = violations[0]
    assert v.severity == Severity.ERROR
    assert v.line == 12
    assert v.file_path == "script.ahk"
    assert "Missing close-quote" in v.message
    assert "Specifically:" in v.message  # continuation folded in


def test_parse_clean_output_is_empty(tmp_path):
    assert _make_rule(tmp_path)._parse_stderr("") == []


def test_parse_multiple_errors(tmp_path):
    rule = _make_rule(tmp_path)
    a, b = tmp_path / "a.ahk", tmp_path / "b.ahk"
    stderr = f"{a} (1) : ==> Err A\n{b} (5) : ==> Err B\n"
    violations = rule._parse_stderr(stderr)
    assert [(v.file_path, v.line) for v in violations] == [("a.ahk", 1), ("b.ahk", 5)]


# ------------------------------------------------------------- version detection

def test_version_detection(tmp_path):
    v2 = tmp_path / "v2.ahk"
    v2.write_text("#Requires AutoHotkey v2.0\nMsgBox('hi')\n", encoding="utf-8")
    v1 = tmp_path / "v1.ahk"
    v1.write_text("MsgBox, hi\nreturn\n", encoding="utf-8")
    rule = _make_rule(tmp_path)
    assert rule._is_v2(v2) is True
    assert rule._is_v2(v1) is False


# --------------------------------------------------------------- root detection

def test_root_detection_excludes_included_files(tmp_path):
    root = tmp_path / "main.ahk"
    root.write_text("#Include lib.ahk\nExitApp\n", encoding="utf-8")
    lib = tmp_path / "lib.ahk"
    lib.write_text("Foo() {\n}\n", encoding="utf-8")

    rule = _make_rule(tmp_path)
    files = rule._discover_ahk_files()
    adjacency, included = rule._build_include_graph(files)

    assert lib.resolve() in included
    assert root.resolve() not in included
    roots = [f for f in files if f not in included]
    assert roots == [root.resolve()]


def test_include_detected_despite_bom(tmp_path):
    # BOM-prefixed .ahk must still have its #Include recognized (utf-8-sig read).
    root = tmp_path / "main.ahk"
    root.write_text("#Include lib.ahk\nExitApp\n", encoding="utf-8-sig")
    (tmp_path / "lib.ahk").write_text("Foo() {\n}\n", encoding="utf-8")
    rule = _make_rule(tmp_path)
    files = rule._discover_ahk_files()
    _, included = rule._build_include_graph(files)
    assert (tmp_path / "lib.ahk").resolve() in included


def test_duplicate_violations_are_deduped(tmp_path, monkeypatch):
    # Two roots each surface the same broken shared lib -> reported once.
    a = tmp_path / "a.ahk"
    a.write_text("#Requires AutoHotkey v2.0\n#Include shared.ahk\nExitApp\n", encoding="utf-8")
    b = tmp_path / "b.ahk"
    b.write_text("#Requires AutoHotkey v2.0\n#Include shared.ahk\nExitApp\n", encoding="utf-8")
    (tmp_path / "shared.ahk").write_text("Foo() {\n}\n", encoding="utf-8")
    shared = (tmp_path / "shared.ahk").resolve()

    rule = _make_rule(tmp_path)
    monkeypatch.setattr(rule, "_get_tool_path", lambda exe, key: "fake.exe")
    monkeypatch.setattr(rule, "_run_subprocess",
                        lambda cmd, cwd=None, timeout=300: _completed(f"{shared} (1) : ==> Boom\n"))
    result = rule.check(a)
    assert len(result.violations) == 1


def test_standalone_file_is_a_root(tmp_path):
    solo = tmp_path / "solo.ahk"
    solo.write_text("ExitApp\n", encoding="utf-8")
    rule = _make_rule(tmp_path)
    files = rule._discover_ahk_files()
    _, included = rule._build_include_graph(files)
    assert included == set()


# --------------------------------------------------------- interpreter cmd shape

def test_validate_root_v2_command_and_cwd(tmp_path, monkeypatch):
    root = tmp_path / "app.ahk"
    root.write_text("#Requires AutoHotkey v2.0\nExitApp\n", encoding="utf-8")
    rule = _make_rule(tmp_path)
    monkeypatch.setattr(rule, "_get_tool_path", lambda exe, key: "C:/ahk/AutoHotkey64.exe")

    captured = {}

    def fake_run(cmd, cwd=None, timeout=300):
        captured["cmd"] = cmd
        captured["cwd"] = cwd
        return _completed("", code=0)

    monkeypatch.setattr(rule, "_run_subprocess", fake_run)
    result = rule._validate_root(root)

    assert result == []
    assert "/validate" in captured["cmd"]
    assert any(a.startswith("/ErrorStdOut") for a in captured["cmd"])
    assert captured["cwd"] == root.parent


def test_validate_root_v1_command_uses_ilib(tmp_path, monkeypatch):
    root = tmp_path / "legacy.ahk"
    root.write_text("MsgBox, hi\n", encoding="utf-8")
    rule = _make_rule(tmp_path)
    monkeypatch.setattr(rule, "_get_tool_path", lambda exe, key: "C:/ahk/AutoHotkeyU64.exe")

    captured = {}
    monkeypatch.setattr(rule, "_run_subprocess",
                        lambda cmd, cwd=None, timeout=300: captured.update(cmd=cmd) or _completed("", 0))
    rule._validate_root(root)
    assert "/iLib" in captured["cmd"]
    assert "/validate" not in captured["cmd"]


def test_validate_root_returns_none_when_interpreter_missing(tmp_path, monkeypatch):
    root = tmp_path / "x.ahk"
    root.write_text("ExitApp\n", encoding="utf-8")
    rule = _make_rule(tmp_path)
    monkeypatch.setattr(rule, "_get_tool_path", lambda exe, key: None)
    assert rule._validate_root(root) is None


# --------------------------------------------------------------- _run integration

def test_run_skips_when_no_interpreter(tmp_path, monkeypatch):
    (tmp_path / "a.ahk").write_text("ExitApp\n", encoding="utf-8")
    rule = _make_rule(tmp_path)
    monkeypatch.setattr(rule, "_get_tool_path", lambda exe, key: None)
    result = rule.check(tmp_path / "a.ahk")
    assert result.status == RuleStatus.SKIPPED


def test_run_reports_parsed_violation(tmp_path, monkeypatch):
    root = tmp_path / "main.ahk"
    root.write_text("#Requires AutoHotkey v2.0\nExitApp\n", encoding="utf-8")
    rule = _make_rule(tmp_path)
    monkeypatch.setattr(rule, "_get_tool_path", lambda exe, key: "fake.exe")
    monkeypatch.setattr(rule, "_run_subprocess",
                        lambda cmd, cwd=None, timeout=300: _completed(f"{root} (2) : ==> Boom\n"))
    result = rule.check(root)
    assert result.status == RuleStatus.OK
    assert len(result.violations) == 1
    assert result.violations[0].line == 2


def test_run_clean_returns_ok_no_violations(tmp_path, monkeypatch):
    root = tmp_path / "main.ahk"
    root.write_text("#Requires AutoHotkey v2.0\nExitApp\n", encoding="utf-8")
    rule = _make_rule(tmp_path)
    monkeypatch.setattr(rule, "_get_tool_path", lambda exe, key: "fake.exe")
    monkeypatch.setattr(rule, "_run_subprocess",
                        lambda cmd, cwd=None, timeout=300: _completed("", 0))
    result = rule.check(root)
    assert result.status == RuleStatus.OK
    assert result.violations == []


def test_filter_mode_scopes_to_roots_covering_changed_file(tmp_path, monkeypatch):
    root = tmp_path / "main.ahk"
    root.write_text("#Requires AutoHotkey v2.0\n#Include lib.ahk\nExitApp\n", encoding="utf-8")
    lib = tmp_path / "lib.ahk"
    lib.write_text("Foo() {\n}\n", encoding="utf-8")
    other = tmp_path / "other.ahk"
    other.write_text("#Requires AutoHotkey v2.0\nExitApp\n", encoding="utf-8")

    # Only lib.ahk changed -> only its root (main.ahk) should be validated.
    rule = _make_rule(tmp_path, filter_files={"lib.ahk"})
    validated = []
    monkeypatch.setattr(rule, "_get_tool_path", lambda exe, key: "fake.exe")
    monkeypatch.setattr(rule, "_run_subprocess",
                        lambda cmd, cwd=None, timeout=300: validated.append(cmd[-1]) or _completed("", 0))
    rule.check(root)
    assert str(root.resolve()) in validated
    assert str(other.resolve()) not in validated
