import pytest

from logger import Logger
from models import LogLevel, OutputLevel, Severity, Violation
from report_config import ReportConfig
from reporter import Reporter


def _reporter(
    violations: list[Violation],
    *,
    fail_on_findings: bool = False,
    log_level: LogLevel = LogLevel.ALL,
    output_folder=None,
) -> Reporter:
    return Reporter(ReportConfig(
        violations=violations,
        file_count=1,
        output_level=OutputLevel.MINIMAL,
        log_level=log_level,
        output_folder=output_folder,
        logger=Logger(quiet=True),
        fail_on_findings=fail_on_findings,
    ))


def _violation(severity: Severity) -> Violation:
    return Violation(file_path="a.py", rule_name="r", severity=severity, message="m")


def test_clean_report_succeeds_with_strict_mode(capsys):
    reporter = _reporter([], fail_on_findings=True)

    assert reporter.report() is False
    assert reporter.report_json() is False
    capsys.readouterr()


@pytest.mark.parametrize("severity", [Severity.ERROR, Severity.WARNING, Severity.INFO])
def test_any_reported_severity_fails_with_strict_mode(severity, capsys):
    reporter = _reporter([_violation(severity)], fail_on_findings=True)

    assert reporter.report() is True
    assert reporter.report_json() is True
    capsys.readouterr()


@pytest.mark.parametrize(
    ("severity", "expected"),
    [(Severity.WARNING, False), (Severity.INFO, False), (Severity.ERROR, True)],
)
def test_default_mode_preserves_error_only_exit_contract(severity, expected):
    reporter = _reporter([_violation(severity)])

    assert reporter.report() is expected


def test_strict_mode_fails_when_csv_output_contains_warning(tmp_path):
    reporter = _reporter(
        [_violation(Severity.WARNING)],
        fail_on_findings=True,
        output_folder=tmp_path,
    )

    assert reporter.report() is True


def test_strict_mode_ignores_findings_filtered_from_report():
    reporter = _reporter(
        [_violation(Severity.WARNING)],
        fail_on_findings=True,
        log_level=LogLevel.ERROR,
    )

    assert reporter.report() is False
