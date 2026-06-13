"""Spec for orchestrator failure handling (RED until analyzer.py gains it).

A FAILED rule result must be recorded, mirrored as an ERROR violation (so existing
error-counting / exit-code paths light up), and retrievable via get_failures(). A
rule whose check() raises unexpectedly must be caught and turned into a FAILED
result, never crash the whole run or silently vanish.
"""
from pathlib import Path

from analyzer import AnalyzerConfig, CodeAnalyzer
from logger import Logger
from models import RuleResult, RuleStatus, Severity, Violation

# The analyzer's own rules file — exists in the repo root.
RULES_FILE = str(Path(__file__).resolve().parents[2] / "code_analysis_rules.json")


def _analyzer(tmp_path: Path) -> CodeAnalyzer:
    cfg = AnalyzerConfig(
        languages="php",
        path=str(tmp_path),
        rules_file=RULES_FILE,
        logger=Logger(quiet=True),
    )
    return CodeAnalyzer(cfg)


class _FakeRule:
    rule_name = "fake_tool"

    def __init__(self, result=None, exc=None):
        self._result = result
        self._exc = exc

    def check(self, file_path):
        if self._exc is not None:
            raise self._exc
        return self._result


def test_record_failed_mirrors_error_violation(tmp_path: Path):
    a = _analyzer(tmp_path)
    res = RuleResult(rule_name="pmd_duplicates", status=RuleStatus.FAILED, message="boom")
    a._record(res)

    assert a.get_failures() == [res]
    assert any(
        v.severity == Severity.ERROR and "pmd_duplicates" in v.rule_name
        for v in a.violations
    )


def test_record_ok_extends_violations_without_failure(tmp_path: Path):
    a = _analyzer(tmp_path)
    v = Violation(file_path="a.php", rule_name="x", severity=Severity.WARNING, message="m")
    a._record(RuleResult(rule_name="x", status=RuleStatus.OK, violations=[v]))

    assert v in a.violations
    assert a.get_failures() == []


def test_run_and_record_catches_unexpected_exception(tmp_path: Path):
    a = _analyzer(tmp_path)
    a._run_and_record(_FakeRule(exc=RuntimeError("kaboom")), tmp_path)

    failures = a.get_failures()
    assert len(failures) == 1
    assert failures[0].status == RuleStatus.FAILED
    assert "kaboom" in (failures[0].message or "")


def test_run_and_record_passes_through_ok(tmp_path: Path):
    a = _analyzer(tmp_path)
    v = Violation(file_path="a.php", rule_name="fake_tool", severity=Severity.WARNING, message="m")
    a._run_and_record(_FakeRule(result=RuleResult(rule_name="fake_tool", status=RuleStatus.OK, violations=[v])), tmp_path)

    assert v in a.violations
    assert a.get_failures() == []
