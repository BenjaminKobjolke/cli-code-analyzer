"""Spec for the typed RuleResult contract (RED until models.py / base.py gain it).

A rule must be able to say WHICH of three things happened, not just "here are
violations": it ran OK (violations may be empty == genuinely clean), it FAILED
(tool missing/crashed/unparseable — result untrustworthy), or it was SKIPPED
(not applicable). The base helpers stamp rule_name so it can never be forgotten.
"""
from logger import Logger
from models import RuleResult, RuleStatus, Severity, Violation
from rules.base import BaseRule
from rules.context import RuleContext


class _DummyRule(BaseRule):
    rule_name = "dummy"

    def check(self, file_path):
        return self._ok([])


def _rule() -> _DummyRule:
    return _DummyRule(RuleContext(config={}, logger=Logger(quiet=True)))


def test_rule_result_defaults():
    r = RuleResult(rule_name="x", status=RuleStatus.OK)
    assert r.violations == []
    assert r.message is None


def test_ok_helper_stamps_name_and_status():
    v = Violation(file_path="a.php", rule_name="dummy", severity=Severity.WARNING, message="m")
    res = _rule()._ok([v])
    assert res.status == RuleStatus.OK
    assert res.rule_name == "dummy"
    assert res.violations == [v]


def test_failed_helper_carries_message():
    res = _rule()._failed("phpstan binary not found")
    assert res.status == RuleStatus.FAILED
    assert res.rule_name == "dummy"
    assert res.message == "phpstan binary not found"
    assert res.violations == []


def test_skipped_helper_carries_message():
    res = _rule()._skipped("language not supported by PMD")
    assert res.status == RuleStatus.SKIPPED
    assert res.rule_name == "dummy"
    assert res.message == "language not supported by PMD"
