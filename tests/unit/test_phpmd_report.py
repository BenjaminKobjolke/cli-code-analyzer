import subprocess
from pathlib import Path

import pytest

from models import RuleStatus, Severity
from project_wide_rules import PROJECT_WIDE_ANALYZERS
from rules.phpmd_analyze import PHPMDAnalyzeRule
from tests.unit.phpmd_test_helpers import _rule

_PHPMD_2_15_OUTPUT = '''Deprecated: Optional parameter $child declared before required parameter $parent is implicitly treated as a required parameter in vendor/pdepend/src/Parser.php on line 223

Deprecated: Creation of dynamic property PDepend\\Parser\\Token::$image is deprecated in vendor/pdepend/src/Parser.php on line 481

PHP Deprecated: Return type of PHPMD\\Rule\\AbstractRule::getPriority() should either be compatible with ... in vendor/phpmd/src/Rule/AbstractRule.php on line 58

<?xml version="1.0" encoding="UTF-8" ?>
<pmd version="2.15.0"><file name="src/Example.php" /></pmd>'''


@pytest.mark.parametrize(
    "exclude_patterns",
    [
        ["generated/**", "tests/fixtures/**"],
        {"php": ["generated/**", "tests/fixtures/**"]},
    ],
    ids=["flat", "php-keyed"],
)
def test_phpmd_project_scan_combines_configured_exclusions(
    tmp_path: Path, monkeypatch, exclude_patterns
):
    rule = _rule(tmp_path, config={"exclude_patterns": exclude_patterns})
    calls = []
    generated_file = tmp_path / "generated" / "generated.php"
    fixture_file = tmp_path / "tests" / "fixtures" / "fixture.php"
    generated_file.parent.mkdir(parents=True)
    fixture_file.parent.mkdir(parents=True)
    generated_file.write_text("<?php\n", encoding="utf-8")
    fixture_file.write_text("<?php\n", encoding="utf-8")

    monkeypatch.setattr(rule, "_get_tool_path", lambda *_args: "phpmd")
    monkeypatch.setattr("rules.phpmd_analyze.get_bundled_php_tool_path", lambda *_args: None)
    monkeypatch.setattr(
        rule,
        "_run_subprocess",
        lambda command, _cwd, **_kwargs: calls.append(command) or subprocess.CompletedProcess(
            command, 0, '<pmd version="1" />', ""
        ),
    )

    result = rule.check(tmp_path / "src" / "Example.php")

    assert result.status == RuleStatus.OK
    command = calls[0]
    file_args = command[2:command.index("--format")]
    assert file_args == [str(tmp_path / "src" / "Example.php")]
    excludes = command[command.index("--exclude") + 1].split(",")
    assert "*/vendor/*" in excludes
    assert "generated/**" in excludes
    assert "tests/fixtures/**" in excludes


def test_phpmd_prefers_bundled_executable_to_global_lookup(tmp_path: Path, monkeypatch):
    rule = _rule(tmp_path)
    commands = []
    monkeypatch.setattr(
        "rules.phpmd_analyze.get_bundled_php_tool_path",
        lambda *_args: "bundled/phpmd",
    )
    monkeypatch.setattr(
        rule, "_get_tool_path", lambda *_args: pytest.fail("global lookup should not run")
    )
    monkeypatch.setattr(
        rule,
        "_run_subprocess",
        lambda command, _cwd, **_kwargs: commands.append(command) or subprocess.CompletedProcess(
            command, 0, "<pmd />", ""
        ),
    )

    result = rule.check(tmp_path / "src" / "Example.php")

    assert result.status == RuleStatus.OK
    assert commands[0][0] == "bundled/phpmd"


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


def test_phpmd_ignores_php_deprecation_notices_before_xml(tmp_path: Path):
    rule = _rule(tmp_path)
    assert rule._parse_report(_PHPMD_2_15_OUTPUT) == []


def test_phpmd_successful_run_keeps_xml_separate_from_php_deprecation_stderr(
    tmp_path: Path, monkeypatch
):
    rule = _rule(tmp_path)
    monkeypatch.setattr("rules.phpmd_analyze.get_bundled_php_tool_path", lambda *_args: None)
    monkeypatch.setattr(rule, "_get_tool_path", lambda *_args: "phpmd")
    monkeypatch.setattr(
        rule,
        "_run_subprocess",
        lambda command, _cwd, **_kwargs: subprocess.CompletedProcess(
            command, 0, _PHPMD_2_15_OUTPUT,
            "Deprecated: PHP 8.5 runtime notice in vendor code on line 42",
        ),
    )

    result = rule.check(tmp_path / "src" / "Example.php")

    assert result.status == RuleStatus.OK
    assert result.violations == []


def test_phpmd_rejects_unexpected_text_before_xml(tmp_path: Path):
    rule = _rule(tmp_path)

    with pytest.raises(ValueError, match="unexpected text before its XML report"):
        rule._parse_report('Warning: PHPMD failed unexpectedly\n<pmd />')


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
        "CouplingBetweenObjects",
        "EmptyCatchBlock",
    )
    findings = "".join(
        f'<violation beginline="{line}" rule="{name}" class="Example" method="run">{name}</violation>'
        for line, name in enumerate(supported_rules, start=1)
    )

    violations = rule._parse_report(
        f'<pmd><file name="src/Example.php">{findings}</file></pmd>'
    )

    assert [item.line for item in violations] == [1, 2, 3, 4, 5, 6]
    assert all("Example::run" in item.message for item in violations)
    assert all(name in item.message for name, item in zip(supported_rules, violations, strict=True))


def test_phpmd_is_registered_as_a_project_wide_analyzer():
    assert ("phpmd_analyze", PHPMDAnalyzeRule) in PROJECT_WIDE_ANALYZERS


def test_phpmd_missing_executable_is_a_failure(tmp_path: Path, monkeypatch):
    rule = _rule(tmp_path)
    monkeypatch.setattr("rules.phpmd_analyze.get_bundled_php_tool_path", lambda *_args: None)
    monkeypatch.setattr(rule, "_get_tool_path", lambda *_args: None)

    result = rule.check(tmp_path / "src" / "Example.php")

    assert result.status == RuleStatus.FAILED
    assert "PHPMD executable not found" in result.message


@pytest.mark.parametrize(
    "stderr",
    ["invalid ruleset"],
)
def test_phpmd_nonzero_exit_is_a_failure(tmp_path: Path, monkeypatch, stderr: str):
    rule = _rule(tmp_path)
    monkeypatch.setattr("rules.phpmd_analyze.get_bundled_php_tool_path", lambda *_args: None)
    monkeypatch.setattr(rule, "_get_tool_path", lambda *_args: "phpmd")
    monkeypatch.setattr(
        rule,
        "_run_subprocess",
        lambda command, _cwd, **_kwargs: subprocess.CompletedProcess(command, 1, "<pmd />", stderr),
    )

    result = rule.check(tmp_path / "src" / "Example.php")

    assert result.status == RuleStatus.FAILED
    assert "exit 1" in result.message


def test_phpmd_recursive_inheritance_case_completes_with_scoped_findings(
    tmp_path: Path, monkeypatch
):
    source_file = tmp_path / "src" / "Example.php"
    rule = _rule(tmp_path, {"src/Example.php"})
    report = '''<pmd version="2.15.0"><file name="src/Example.php">
      <violation beginline="12" rule="ExcessiveMethodLength" class="Example" method="run">
        Method exceeds the configured length.
      </violation>
    </file></pmd>'''
    calls = []
    monkeypatch.setattr("rules.phpmd_analyze.get_bundled_php_tool_path", lambda *_args: None)
    monkeypatch.setattr(rule, "_get_tool_path", lambda *_args: "phpmd")
    monkeypatch.setattr(
        rule,
        "_run_subprocess",
        lambda command, _cwd, **_kwargs: calls.append(command)
        or subprocess.CompletedProcess(command, 0, report, ""),
    )

    result = rule.check(source_file)

    assert result.status == RuleStatus.OK
    assert len(result.violations) == 1
    assert result.violations[0].file_path == "src/Example.php"
    assert result.violations[0].line == 12
    assert "ExcessiveMethodLength" in result.violations[0].message
    assert calls[0][:3] == ["phpmd", "analyze", str(source_file)]


def test_phpmd_malformed_and_empty_reports_are_failures(tmp_path: Path, monkeypatch):
    rule = _rule(tmp_path)
    monkeypatch.setattr("rules.phpmd_analyze.get_bundled_php_tool_path", lambda *_args: None)
    monkeypatch.setattr(rule, "_get_tool_path", lambda *_args: "phpmd")
    output = iter(("not xml", ""))
    monkeypatch.setattr(
        rule,
        "_run_subprocess",
        lambda command, _cwd, **_kwargs: subprocess.CompletedProcess(command, 0, next(output), ""),
    )

    malformed = rule.check(tmp_path / "src" / "Example.php")
    assert malformed.status == RuleStatus.FAILED
    assert "PHPMD" in malformed.message

    rule._executed = False
    empty = rule.check(tmp_path / "src" / "Example.php")
    assert empty.status == RuleStatus.FAILED
    assert "PHPMD" in empty.message
