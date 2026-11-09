import subprocess
import sys
from pathlib import Path

import pytest

from models import RuleStatus
from tests.unit.phpmd_test_helpers import _rule


def test_phpmd_invokes_xml_report_with_scoped_php_files(tmp_path: Path, monkeypatch):
    rule = _rule(tmp_path, {"src/Example.php"})
    calls = []

    monkeypatch.setattr(rule, "_get_tool_path", lambda *_args: "phpmd")
    monkeypatch.setattr("rules.phpmd_analyze.get_bundled_php_tool_path", lambda *_args: None)
    monkeypatch.setattr(
        rule,
        "_run_subprocess",
        lambda command, cwd, **_kwargs: calls.append((command, cwd)) or subprocess.CompletedProcess(
            command, 0, '<pmd version="1"><file name="Example.php" /></pmd>', ""
        ),
    )

    result = rule.check(tmp_path / "src" / "Example.php")

    assert result.status == RuleStatus.OK
    assert len(calls) == 1
    command, cwd = calls[0]
    assert command[:3] == ["phpmd", "analyze", str(tmp_path / "src" / "Example.php")]
    assert command[command.index("--format") + 1] == "xml"
    assert command.count("--ruleset") == 2
    assert command[command.index("--ruleset") + 1] == "codesize"
    second_ruleset = command.index("--ruleset", command.index("--ruleset") + 1)
    assert command[second_ruleset + 1] == "design"
    assert command[command.index("--suffixes") + 1] == "php"
    assert "--ignore-violations-on-exit" in command
    assert cwd == tmp_path


@pytest.mark.parametrize(
    ("platform", "expected_threads"),
    [("win32", ["--threads=1"]), ("linux", ["--threads=1"])],
)
def test_phpmd_uses_single_pdepend_thread_to_avoid_worker_streams(
    tmp_path: Path, monkeypatch, platform: str, expected_threads: list[str]
):
    rule = _rule(tmp_path)
    calls = []
    monkeypatch.setattr(sys, "platform", platform)
    monkeypatch.setattr(rule, "_get_tool_path", lambda *_args: "phpmd")
    monkeypatch.setattr("rules.phpmd_analyze.get_bundled_php_tool_path", lambda *_args: None)
    monkeypatch.setattr(
        rule,
        "_run_subprocess",
        lambda command, _cwd, **_kwargs: calls.append(command) or subprocess.CompletedProcess(
            command, 0, "<pmd />", ""
        ),
    )

    result = rule.check(tmp_path / "src" / "Example.php")

    assert result.status == RuleStatus.OK
    command = calls[0]
    assert (
        [argument for argument in command if argument.startswith("--threads")]
        == expected_threads
    )


def test_phpmd_large_scope_keeps_all_files_and_findings(tmp_path: Path, monkeypatch):
    rule = _rule(tmp_path)
    files = [tmp_path / "src" / f"File{index:03}.php" for index in range(555)]
    for source in files:
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text("<?php\n", encoding="utf-8")
    (tmp_path / "src" / "Example.php").unlink()

    commands = []
    monkeypatch.setattr(rule, "_get_tool_path", lambda *_args: "phpmd")
    monkeypatch.setattr("rules.phpmd_analyze.get_bundled_php_tool_path", lambda *_args: None)

    def report_each_scoped_file(command, _cwd, **_kwargs):
        commands.append(command)
        scoped_files = command[2:command.index("--format")]
        report = "".join(
            f'<file name="{path}"><violation beginline="1" '
            'rule="ExcessiveMethodLength">finding</violation></file>'
            for path in scoped_files
        )
        return subprocess.CompletedProcess(command, 0, f"<pmd>{report}</pmd>", "")

    monkeypatch.setattr(rule, "_run_subprocess", report_each_scoped_file)

    result = rule.check(files[0])

    assert result.status == RuleStatus.OK
    assert len(commands) > 1
    assert all("--threads=1" in command for command in commands)
    assert {item.file_path for item in result.violations} == {
        f"src/{source.name}" for source in files
    }
    assert len(result.violations) == len(files)


def test_phpmd_worker_stream_corruption_is_reported_as_failure(
    tmp_path: Path, monkeypatch
):
    rule = _rule(tmp_path)
    monkeypatch.setattr(rule, "_get_tool_path", lambda *_args: "phpmd")
    monkeypatch.setattr("rules.phpmd_analyze.get_bundled_php_tool_path", lambda *_args: None)
    monkeypatch.setattr(
        rule,
        "_run_subprocess",
        lambda command, _cwd, **_kwargs: subprocess.CompletedProcess(
            command,
            1,
            "",
            'In WorkerProtocol.php line 85: Corrupt worker stream, expected a frame header',
        ),
    )

    result = rule.check(tmp_path / "src" / "Example.php")

    assert result.status == RuleStatus.FAILED
    assert "Corrupt worker stream" in result.message


def test_phpmd_timeout_is_reported_as_a_failed_result(tmp_path: Path, monkeypatch):
    rule = _rule(tmp_path)
    monkeypatch.setattr("rules.phpmd_analyze.get_bundled_php_tool_path", lambda *_args: None)
    monkeypatch.setattr(rule, "_get_tool_path", lambda *_args: "phpmd")

    def timeout(*_args, **_kwargs):
        raise subprocess.TimeoutExpired("phpmd analyze", timeout=300)

    monkeypatch.setattr(rule, "_run_subprocess", timeout)

    result = rule.check(tmp_path / "src" / "Example.php")

    assert result.status == RuleStatus.FAILED
    assert "timed out" in result.message.lower()


def test_phpmd_runs_with_isolated_pdepend_cache(tmp_path: Path, monkeypatch):
    rule = _rule(tmp_path)
    global_cache = tmp_path / "global-cache"
    global_cache.mkdir()
    monkeypatch.setenv("XDG_CACHE_HOME", str(global_cache))
    calls = []

    monkeypatch.setattr("rules.phpmd_analyze.get_bundled_php_tool_path", lambda *_args: None)
    monkeypatch.setattr(rule, "_get_tool_path", lambda *_args: "phpmd")

    def run_with_cache(command, cwd, env=None):
        assert env is not None
        cache_dir = Path(env["XDG_CACHE_HOME"])
        assert cache_dir.is_dir()
        assert cache_dir != global_cache
        assert global_cache not in cache_dir.parents
        assert "PATH" in env
        calls.append((command, cwd, cache_dir))
        return subprocess.CompletedProcess(command, 0, "<pmd />", "")

    monkeypatch.setattr(rule, "_run_subprocess", run_with_cache)

    result = rule.check(tmp_path / "src" / "Example.php")

    assert result.status == RuleStatus.OK
    assert len(calls) == 1
    assert not calls[0][2].exists()


def test_phpmd_cleans_isolated_cache_after_timeout(tmp_path: Path, monkeypatch):
    rule = _rule(tmp_path)
    cache_dirs = []
    monkeypatch.setattr("rules.phpmd_analyze.get_bundled_php_tool_path", lambda *_args: None)
    monkeypatch.setattr(rule, "_get_tool_path", lambda *_args: "phpmd")

    def timeout(command, _cwd, env=None):
        assert env is not None
        cache_dir = Path(env["XDG_CACHE_HOME"])
        assert cache_dir.is_dir()
        cache_dirs.append(cache_dir)
        raise subprocess.TimeoutExpired(command, timeout=300)

    monkeypatch.setattr(rule, "_run_subprocess", timeout)

    result = rule.check(tmp_path / "src" / "Example.php")

    assert result.status == RuleStatus.FAILED
    assert "timed out" in result.message.lower()
    assert len(cache_dirs) == 1
    assert not cache_dirs[0].exists()


def test_phpmd_project_scan_uses_discovered_files_and_keeps_exclusions(
    tmp_path: Path, monkeypatch
):
    rule = _rule(tmp_path)
    calls = []
    source = tmp_path / "src" / "Example.php"
    vendor_file = tmp_path / "vendor" / "dependency.php"
    node_module_file = tmp_path / "node_modules" / "dependency.php"
    vendor_file.parent.mkdir(parents=True)
    node_module_file.parent.mkdir(parents=True)
    vendor_file.write_text("<?php\n", encoding="utf-8")
    node_module_file.write_text("<?php\n", encoding="utf-8")

    monkeypatch.setattr(rule, "_get_tool_path", lambda *_args: "phpmd")
    monkeypatch.setattr("rules.phpmd_analyze.get_bundled_php_tool_path", lambda *_args: None)
    monkeypatch.setattr(
        rule,
        "_run_subprocess",
        lambda command, _cwd, **_kwargs: calls.append(command) or subprocess.CompletedProcess(
            command, 0,
            '<pmd version="1"><file name="src/Example.php">'
            '<violation beginline="2" rule="ExcessiveMethodLength">long</violation>'
            '</file></pmd>',
            "",
        ),
    )

    result = rule.check(source)

    command = calls[0]
    file_args = command[2:command.index("--format")]
    assert file_args == [str(source)]
    assert result.status == RuleStatus.OK
    excludes = command[command.index("--exclude") + 1].split(",")
    assert [violation.file_path for violation in result.violations] == ["src/Example.php"]
    assert "*/vendor/*" in excludes
    assert "*\\vendor\\*" in excludes
    assert "*/node_modules/*" in excludes
