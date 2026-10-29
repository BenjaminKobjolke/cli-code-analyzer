import subprocess
from pathlib import Path

from logger import Logger
from models import RuleStatus, Severity
from project_wide_rules import PROJECT_WIDE_ANALYZERS
from rules.context import RuleContext
from rules.phpmd_analyze import PHPMDAnalyzeRule


def _rule(tmp_path: Path, filter_files=None) -> PHPMDAnalyzeRule:
    source = tmp_path / "src" / "Example.php"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("<?php\n", encoding="utf-8")
    return PHPMDAnalyzeRule(RuleContext(
        config={},
        base_path=tmp_path,
        logger=Logger(quiet=True),
        filter_files=filter_files,
    ))


def test_phpmd_invokes_xml_report_with_scoped_php_files(tmp_path: Path, monkeypatch):
    rule = _rule(tmp_path, {"src/Example.php"})
    calls = []

    monkeypatch.setattr(rule, "_get_tool_path", lambda *_args: "phpmd")
    monkeypatch.setattr(
        rule,
        "_run_subprocess",
        lambda command, cwd: calls.append((command, cwd)) or subprocess.CompletedProcess(
            command, 0, '<pmd version="1"><file name="Example.php" /></pmd>', ""
        ),
    )

    result = rule.check(tmp_path / "src" / "Example.php")

    assert result.status == RuleStatus.OK
    assert len(calls) == 1
    command, cwd = calls[0]
    assert command[:2] == ["phpmd", str(tmp_path / "src" / "Example.php")]
    assert command[2:4] == ["xml", "codesize,design"]
    assert "--ignore-violations-on-exit" in command
    assert cwd == tmp_path


def test_phpmd_maps_supported_function_findings_and_ignores_unknown_rules(tmp_path: Path):
    rule = _rule(tmp_path)
    report = '''<?xml version="1.0"?>
    <pmd version="1"><file name="src/Example.php">
      <violation beginline="18" endline="60" rule="ExcessiveMethodLength"
        ruleset="Code Size Rules" package="app" class="QueueBuilder" method="buildContent" priority="3">
        This method is too long.
      </violation>
      <violation beginline="7" endline="7" rule="UnusedPrivateField" priority="3">ignored</violation>
    </file></pmd>'''

    violations = rule._parse_report(report)

    assert len(violations) == 1
    violation = violations[0]
    assert violation.file_path == "src/Example.php"
    assert violation.line == 18
    assert violation.severity == Severity.WARNING
    assert "ExcessiveMethodLength" in violation.message
    assert "QueueBuilder::buildContent" in violation.message
    assert "too long" in violation.message


def test_phpmd_findings_include_function_and_review_details(tmp_path: Path):
    rule = _rule(tmp_path)
    report = '''<pmd><file name="src/Example.php">
      <violation beginline="18" rule="ExcessiveMethodLength" class="QueueBuilder" method="buildContent">
        This method is too long.
      </violation>
    </file></pmd>'''

    violation = rule._parse_report(report)[0]

    assert violation.function_name == "buildContent"
    assert violation.confidence == "high"
    assert violation.evidence == "This method is too long."
    assert violation.recommendation


def test_phpmd_parses_each_supported_rule_id(tmp_path: Path):
    rule = _rule(tmp_path)
    supported_rules = (
        "CyclomaticComplexity",
        "NPathComplexity",
        "ExcessiveMethodLength",
        "ExcessiveParameterList",
    )
    findings = "".join(
        f'<violation beginline="{line}" rule="{name}" class="Example" method="run">{name}</violation>'
        for line, name in enumerate(supported_rules, start=1)
    )

    violations = rule._parse_report(
        f'<pmd><file name="src/Example.php">{findings}</file></pmd>'
    )

    assert [item.line for item in violations] == [1, 2, 3, 4]
    assert all("Example::run" in item.message for item in violations)
    assert all(name in item.message for name, item in zip(supported_rules, violations, strict=True))


def test_phpmd_is_registered_as_a_project_wide_analyzer():
    assert ("phpmd_analyze", PHPMDAnalyzeRule) in PROJECT_WIDE_ANALYZERS


def test_phpmd_missing_executable_is_a_failure(tmp_path: Path, monkeypatch):
    rule = _rule(tmp_path)
    monkeypatch.setattr(rule, "_get_tool_path", lambda *_args: None)

    result = rule.check(tmp_path / "src" / "Example.php")

    assert result.status == RuleStatus.FAILED
    assert "PHPMD executable not found" in result.message


def test_phpmd_nonzero_exit_is_a_failure(tmp_path: Path, monkeypatch):
    rule = _rule(tmp_path)
    monkeypatch.setattr(rule, "_get_tool_path", lambda *_args: "phpmd")
    monkeypatch.setattr(
        rule,
        "_run_subprocess",
        lambda command, cwd: subprocess.CompletedProcess(command, 1, "<pmd />", "invalid ruleset"),
    )

    result = rule.check(tmp_path / "src" / "Example.php")

    assert result.status == RuleStatus.FAILED
    assert "exit 1" in result.message


def test_phpmd_malformed_and_empty_reports_are_failures(tmp_path: Path, monkeypatch):
    rule = _rule(tmp_path)
    monkeypatch.setattr(rule, "_get_tool_path", lambda *_args: "phpmd")
    output = iter(("not xml", ""))
    monkeypatch.setattr(
        rule,
        "_run_subprocess",
        lambda command, cwd: subprocess.CompletedProcess(command, 0, next(output), ""),
    )

    malformed = rule.check(tmp_path / "src" / "Example.php")
    assert malformed.status == RuleStatus.FAILED
    assert "PHPMD" in malformed.message

    rule._executed = False
    empty = rule.check(tmp_path / "src" / "Example.php")
    assert empty.status == RuleStatus.FAILED
    assert "PHPMD" in empty.message
