"""Unit tests for PHP function-level quality metrics."""

from pathlib import Path

from analyzer import AnalyzerConfig, CodeAnalyzer
from logger import Logger
from models import RuleStatus, Severity
from rules.context import RuleContext
from rules.php_function_quality import PHPFunctionQualityRule


def _rule(base_path: Path, config: dict | None = None) -> PHPFunctionQualityRule:
    return PHPFunctionQualityRule(RuleContext(
        config=config or {},
        base_path=base_path.resolve(),
        logger=Logger(quiet=True),
    ))


def _write_php(tmp_path: Path, source: str, name: str = "Example.php") -> Path:
    file_path = tmp_path / name
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text("<?php\n" + source, encoding="utf-8")
    return file_path


def test_defaults_report_long_complex_deep_and_cognitive_functions(tmp_path: Path):
    body = "\n".join(f"        if ($value === {index}) {{ return {index}; }}" for index in range(55))
    source = _write_php(
        tmp_path,
        "function overloaded($value) {\n"
        "    if ($value) {\n"
        "        while ($value) {\n"
        "            switch ($value) {\n"
        f"{body}\n"
        "            }\n"
        "        }\n"
        "    }\n"
        "}\n",
    )

    result = _rule(tmp_path).check(source)

    assert result.status == RuleStatus.OK
    assert {v.message.split(":", 1)[0] for v in result.violations} == {"overloaded"}
    assert {v.rule_name for v in result.violations} == {"php_function_quality"}
    assert {v.severity for v in result.violations} == {Severity.WARNING}
    assert {"function length", "cyclomatic complexity", "cognitive complexity", "nesting depth"} <= {
        metric for violation in result.violations for metric in (
            "function length", "cyclomatic complexity", "cognitive complexity", "nesting depth"
        ) if metric in violation.message
    }
    assert all(violation.line == 2 for violation in result.violations)


def test_threshold_overrides_and_parameter_count_are_respected(tmp_path: Path):
    source = _write_php(tmp_path, "function compact($a, $b, $c) {\n    return $a + $b + $c;\n}\n")
    config = {
        "function_length": {"warning": 1, "error": 2, "exceptions": [{"file": "Example.php", "warning": 20, "error": 30}]},
        "cyclomatic_complexity": {"warning": 100, "error": 200},
        "cognitive_complexity": {"warning": 100, "error": 200},
        "nesting_depth": {"warning": 100, "error": 200},
        "parameter_count": {"warning": 2, "error": 3},
    }

    result = _rule(tmp_path, config).check(source)
    other = _write_php(tmp_path, "function compact($a, $b, $c) {\n    return $a + $b + $c;\n}\n", "Other.php")
    other_result = _rule(tmp_path, config).check(other)

    assert len(result.violations) == 1
    assert "compact" in result.violations[0].message
    assert "parameters" in result.violations[0].message
    assert result.violations[0].severity == Severity.ERROR
    assert any("function length" in v.message and v.severity == Severity.ERROR for v in other_result.violations)
    assert all(v.file_path == "Other.php" and v.line == 2 for v in other_result.violations)


def test_findings_include_function_and_actionable_metric_details(tmp_path: Path):
    source = _write_php(tmp_path, "function overloaded($value) {\n" + "    if ($value) { return 1; }\n" * 12 + "}\n")

    result = _rule(tmp_path, {"cyclomatic_complexity": {"warning": 2}}).check(source)

    finding = next(v for v in result.violations if "cyclomatic complexity" in v.message)
    assert finding.function_name == "overloaded"
    assert finding.confidence == "high"
    assert finding.evidence.startswith("cyclomatic complexity: ")
    assert "configured limit: 2" in finding.evidence
    assert finding.recommendation


def test_safe_function_stays_clean_and_non_php_is_ignored(tmp_path: Path):
    source = _write_php(tmp_path, "function findLabel($items) {\n    return $items[0] ?? '';\n}\n")
    safe = _rule(tmp_path).check(source)
    other = tmp_path / "Example.py"
    other.write_text("def unrelated():\n    return 1\n", encoding="utf-8")

    ignored = _rule(tmp_path, {"function_length": {"warning": 1}}).check(other)

    assert safe.status == RuleStatus.OK
    assert safe.violations == []
    assert ignored.status == RuleStatus.OK
    assert ignored.violations == []


def test_excluded_php_paths_are_not_analyzed(tmp_path: Path):
    source = _write_php(
        tmp_path,
        "function tooLong() {\n" + "    echo 'x';\n" * 55 + "}\n",
        "vendor/Example.php",
    )

    result = _rule(tmp_path, {"exclude_patterns": ["vendor/**"]}).check(source)

    assert result.status == RuleStatus.OK
    assert result.violations == []

    quoted_controls = _write_php(
        tmp_path,
        "function showHelp() {\n"
        "    // if, while, and nested blocks in comments are not code\n"
        '    return "if ($value) { while ($value) {} }";\n'
        "}\n",
        "Quoted.php",
    )
    token_thresholds = {
        "function_length": {"warning": 100},
        "cyclomatic_complexity": {"warning": 100},
        "cognitive_complexity": {"warning": 1},
        "nesting_depth": {"warning": 1},
    }
    quoted_result = _rule(tmp_path, token_thresholds).check(quoted_controls)
    assert quoted_result.violations == []


def test_php_function_quality_is_registered_and_dispatched(tmp_path: Path):
    source = _write_php(
        tmp_path,
        "function longEnough() {\n" + "    $value = 1;\n" * 55 + "}\n",
    )
    rules_file = tmp_path / "rules.json"
    rules_file.write_text("{}", encoding="utf-8")
    analyzer = CodeAnalyzer(AnalyzerConfig(
        languages="php",
        path=str(tmp_path),
        rules_file=str(rules_file),
        only_analyzers={"php_function_quality"},
        logger=Logger(quiet=True),
    ))

    analyzer.analyze()

    findings = [v for result in analyzer.results for v in result.violations]
    assert any(v.file_path == "Example.php" and "function length" in v.message for v in findings)
