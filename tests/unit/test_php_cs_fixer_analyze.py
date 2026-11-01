import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

from logger import Logger
from models import RuleStatus
from project_wide_rules import FILTER_INCAPABLE
from rules.context import RuleContext
from rules.php_cs_fixer_analyze import PHPCSFixerAnalyzeRule


def _rule(
    tmp_path: Path,
    filter_files: set[str] | None = None,
    config: dict | None = None,
    output_folder: Path | None = None,
    max_errors: int | None = None,
) -> PHPCSFixerAnalyzeRule:
    return PHPCSFixerAnalyzeRule(
        RuleContext(
            config=config or {},
            base_path=tmp_path,
            filter_files=filter_files,
            output_folder=output_folder,
            max_errors=max_errors,
            logger=Logger(quiet=True),
        )
    )


def _touch(tmp_path: Path, *relative_paths: str) -> None:
    for relative_path in relative_paths:
        path = tmp_path / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("<?php\n", encoding="utf-8")


def _fixer_output(path: Path, fixer: str = "single_line_after_imports") -> str:
    return json.dumps({"files": [{"name": str(path), "appliedFixers": [fixer]}]})


def test_php_cs_fixer_scopes_changed_php_inside_analyze_path(tmp_path: Path, monkeypatch):
    _touch(tmp_path, "classes/Changed.php", "classes/Other.php", "src/Outside.php")
    rule = _rule(
        tmp_path,
        filter_files={"classes/Changed.php", "classes/Other.php", "src/Outside.php"},
        config={"analyze_path": "classes"},
    )
    monkeypatch.setattr(rule, "_ensure_fixer_config", lambda: tmp_path / "config.php")
    calls = []

    def fake_run(command, _cwd):
        calls.append(command)
        return SimpleNamespace(
            returncode=0,
            stdout=_fixer_output(tmp_path / "classes/Changed.php"),
            stderr="",
        )

    monkeypatch.setattr(rule, "_run_subprocess", fake_run)

    result = rule._run_fixer_check("php-cs-fixer")

    assert result.status == RuleStatus.OK
    assert [violation.file_path.replace("\\", "/") for violation in result.violations] == [
        "classes/Changed.php"
    ]
    assert len(calls) == 1
    assert str(tmp_path / "classes/Changed.php") in calls[0]
    assert str(tmp_path / "classes/Other.php") in calls[0]
    assert str(tmp_path / "src/Outside.php") not in calls[0]
    assert str(tmp_path / "classes") not in calls[0]


def test_php_cs_fixer_skips_when_no_changed_php_is_inside_analyze_path(
    tmp_path: Path, monkeypatch
):
    _touch(tmp_path, "src/Changed.php")
    rule = _rule(
        tmp_path,
        filter_files={"src/Changed.php"},
        config={"analyze_path": "classes"},
    )
    monkeypatch.setattr(rule, "_ensure_fixer_config", lambda: tmp_path / "config.php")
    calls = []
    monkeypatch.setattr(rule, "_run_subprocess", lambda *_args: calls.append(True))

    result = rule._run_fixer_check("php-cs-fixer")

    assert result.status == RuleStatus.OK
    assert result.violations == []
    assert calls == []


def test_php_cs_fixer_merges_batch_output_for_violations_and_csv(
    tmp_path: Path, monkeypatch
):
    output_folder = tmp_path / "reports"
    output_folder.mkdir()
    _touch(tmp_path, "src/Changed.php", "src/Other.php")
    rule = _rule(
        tmp_path,
        filter_files={"src/Changed.php", "src/Other.php"},
        output_folder=output_folder,
        max_errors=None,
    )
    monkeypatch.setattr(rule, "_ensure_fixer_config", lambda: tmp_path / "config.php")
    outputs = iter([
        _fixer_output(tmp_path / "src/Other.php", "other_fixer"),
        _fixer_output(tmp_path / "src/Changed.php", "changed_fixer"),
    ])
    monkeypatch.setattr(
        rule,
        "_scoped_commands",
        lambda *_args, **_kwargs: [["php-cs-fixer", "batch-1"], ["php-cs-fixer", "batch-2"]],
    )

    def fake_run(command, _cwd):
        return subprocess.CompletedProcess(command, 0, next(outputs), "")

    monkeypatch.setattr(rule, "_run_subprocess", fake_run)

    result = rule._run_fixer_check("php-cs-fixer")

    assert result.status == RuleStatus.OK
    assert [violation.file_path.replace("\\", "/") for violation in result.violations] == [
        "src/Other.php",
        "src/Changed.php",
    ]
    csv_content = (output_folder / "php_cs_fixer.csv").read_text(encoding="utf-8").replace(
        "\\", "/"
    )
    assert "src/Other.php" in csv_content
    assert "src/Changed.php" in csv_content


def test_php_cs_fixer_unparseable_scoped_output_is_failure(tmp_path: Path, monkeypatch):
    _touch(tmp_path, "src/Changed.php")
    rule = _rule(tmp_path, filter_files={"src/Changed.php"})
    monkeypatch.setattr(rule, "_ensure_fixer_config", lambda: tmp_path / "config.php")
    monkeypatch.setattr(
        rule,
        "_run_subprocess",
        lambda *_args: SimpleNamespace(returncode=0, stdout="not JSON", stderr=""),
    )

    result = rule._run_fixer_check("php-cs-fixer")

    assert result.status == RuleStatus.FAILED


def test_php_cs_fixer_preserves_full_project_command_without_filter(tmp_path: Path, monkeypatch):
    rule = _rule(tmp_path, config={"analyze_path": "classes"})
    monkeypatch.setattr(rule, "_ensure_fixer_config", lambda: tmp_path / "config.php")
    calls = []
    monkeypatch.setattr(
        rule,
        "_run_subprocess",
        lambda command, _cwd: calls.append(command)
        or SimpleNamespace(returncode=0, stdout='{"files": []}', stderr=""),
    )

    result = rule._run_fixer_check("php-cs-fixer")

    assert result.status == RuleStatus.OK
    assert len(calls) == 1
    assert calls[0][-1] == str(tmp_path / "classes")


def test_filter_incapable_keeps_graphify_fanout_but_scopes_php_rules():
    assert "graphify_fanout" in FILTER_INCAPABLE
    assert "php_cs_fixer" not in FILTER_INCAPABLE
    assert "intelephense_analyze" not in FILTER_INCAPABLE
