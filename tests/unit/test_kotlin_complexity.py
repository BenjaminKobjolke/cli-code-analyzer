"""Unit tests for Kotlin function complexity checks."""

from pathlib import Path

import lizard

from logger import Logger
from models import RuleStatus, Severity
from rules.context import RuleContext
from rules.kotlin_complexity import KotlinComplexityRule


def _make_rule(base_path: Path, config: dict) -> KotlinComplexityRule:
    return KotlinComplexityRule(RuleContext(
        config=config,
        base_path=base_path.resolve(),
        logger=Logger(quiet=True),
    ))


def _complex_kotlin() -> str:
    return """fun branching(value: Int): Int {
    if (value > 0 && value < 10) return 1
    return when (value) {
        10 -> 2
        20 -> 3
        else -> 0
    }
}
"""


def test_cyclomatic_complexity_reports_error_at_function_start(tmp_path):
    source = tmp_path / "Sample.kt"
    source.write_text(_complex_kotlin(), encoding="utf-8")
    rule = _make_rule(tmp_path, {"cyclomatic_complexity": {"warning": 2, "error": 3}})

    result = rule.check(source)

    assert result.status == RuleStatus.OK
    assert len(result.violations) == 1
    violation = result.violations[0]
    assert violation.severity == Severity.ERROR
    assert violation.line == 1
    assert "branching" in violation.message
    assert "cyclomatic complexity" in violation.message


def test_cyclomatic_complexity_warning_and_clean_thresholds(tmp_path):
    source = tmp_path / "Sample.kt"
    source.write_text(_complex_kotlin(), encoding="utf-8")

    warning = _make_rule(tmp_path, {"cyclomatic_complexity": {"warning": 2, "error": 20}}).check(source)
    clean = _make_rule(tmp_path, {"cyclomatic_complexity": {"warning": 20, "error": 30}}).check(source)

    assert [v.severity for v in warning.violations] == [Severity.WARNING]
    assert clean.violations == []


def test_exception_overrides_metric_threshold_for_one_file(tmp_path):
    source = tmp_path / "Sample.kt"
    source.write_text(_complex_kotlin(), encoding="utf-8")
    other = tmp_path / "Other.kt"
    other.write_text(_complex_kotlin(), encoding="utf-8")
    config = {"cyclomatic_complexity": {
        "warning": 2,
        "error": 3,
        "exceptions": [{"file": "Sample.kt", "warning": 20, "error": 30}],
    }}
    rule = _make_rule(tmp_path, config)

    assert rule.check(source).violations == []
    assert rule.check(other).violations[0].severity == Severity.ERROR


def test_missing_metric_block_is_not_checked(tmp_path):
    source = tmp_path / "Long.kt"
    source.write_text("fun longFunction() {\n" + "    val value = 1\n" * 120 + "}\n", encoding="utf-8")

    result = _make_rule(tmp_path, {"cyclomatic_complexity": {"warning": 10, "error": 15}}).check(source)

    assert result.violations == []


def test_function_length_and_parameter_count_are_checked(tmp_path):
    source = tmp_path / "Metrics.kt"
    source.write_text("fun manyParameters(a: Int, b: Int, c: Int): Int {\n" +
                      "    return a + b + c\n" * 8 + "}\n", encoding="utf-8")
    rule = _make_rule(tmp_path, {
        "function_length": {"warning": 5, "error": 7},
        "parameter_count": {"warning": 2, "error": 3},
    })

    result = rule.check(source)

    assert {v.rule_name for v in result.violations} == {"kotlin_complexity"}
    assert any("lines of code" in v.message for v in result.violations)
    assert any("parameters" in v.message and v.severity == Severity.ERROR for v in result.violations)


def test_non_kotlin_file_is_ignored(tmp_path):
    source = tmp_path / "sample.py"
    source.write_text("def f(): pass\n", encoding="utf-8")

    result = _make_rule(tmp_path, {"cyclomatic_complexity": {"warning": 1, "error": 2}}).check(source)

    assert result.status == RuleStatus.OK
    assert result.violations == []


def test_lizard_error_is_a_failed_result(tmp_path, monkeypatch):
    source = tmp_path / "Sample.kt"
    source.write_text(_complex_kotlin(), encoding="utf-8")

    def fail(*args, **kwargs):
        raise ValueError("bad Kotlin input")

    monkeypatch.setattr(lizard.FileAnalyzer, "analyze_source_code", fail)
    result = _make_rule(tmp_path, {"cyclomatic_complexity": {"warning": 2, "error": 3}}).check(source)

    assert result.status == RuleStatus.FAILED
    assert "bad Kotlin input" in result.message
