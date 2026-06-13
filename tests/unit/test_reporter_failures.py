"""Spec for reporter surfacing tool failures (RED until reporter.py gains it).

A run with zero violations but a FAILED rule must NOT report success — report()
has to return True (has_errors) so the process exits non-zero.
"""
from logger import Logger
from models import OutputLevel, RuleResult, RuleStatus
from reporter import Reporter


def test_failure_makes_report_signal_error():
    failure = RuleResult(rule_name="pmd_duplicates", status=RuleStatus.FAILED, message="boom")
    reporter = Reporter(
        violations=[],
        file_count=1,
        output_level=OutputLevel.MINIMAL,
        failures=[failure],
        logger=Logger(quiet=True),
    )
    assert reporter.report() is True


def test_no_failures_no_violations_reports_clean():
    reporter = Reporter(
        violations=[],
        file_count=1,
        output_level=OutputLevel.MINIMAL,
        failures=[],
        logger=Logger(quiet=True),
    )
    assert reporter.report() is False
