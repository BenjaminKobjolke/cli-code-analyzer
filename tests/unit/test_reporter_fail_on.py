import pytest

from logger import Logger
from models import LogLevel, OutputLevel, Severity, Violation
from report_config import ReportConfig
from reporter import Reporter


def _violation(severity):
    return Violation("sample.py", "sample_rule", severity, "finding")


def _reporter(violations, **kwargs):
    config = ReportConfig(
        violations=violations,
        file_count=1,
        output_level=kwargs.pop("output_level", OutputLevel.NORMAL),
        logger=Logger(quiet=True),
        **kwargs,
    )
    return Reporter(config)


def test_warning_only_default_fail_on_keeps_existing_behavior():
    assert _reporter([_violation(Severity.WARNING)]).report() is False


@pytest.mark.parametrize("output_level", list(OutputLevel))
def test_fail_on_warnings_fails_for_each_console_output_level(output_level):
    reporter = _reporter(
        [_violation(Severity.WARNING)],
        output_level=output_level,
        fail_on_warnings=True,
    )

    assert reporter.report() is True


def test_fail_on_warnings_does_not_fail_on_info():
    assert _reporter(
        [_violation(Severity.INFO)],
        fail_on_warnings=True,
    ).report() is False


def test_fail_on_warnings_keeps_stronger_configured_threshold():
    assert _reporter(
        [_violation(Severity.INFO)],
        fail_on_warnings=True,
        fail_on=LogLevel.ALL,
    ).report() is True


@pytest.mark.parametrize("output_level", list(OutputLevel))
def test_warning_fails_for_each_console_output_level(output_level):
    reporter = _reporter(
        [_violation(Severity.WARNING)],
        output_level=output_level,
        fail_on=LogLevel.WARNING,
    )

    assert reporter.report() is True


def test_warning_fails_for_csv_output(tmp_path):
    reporter = _reporter(
        [_violation(Severity.WARNING)],
        output_folder=tmp_path,
        fail_on=LogLevel.WARNING,
    )

    assert reporter.report() is True


def test_warning_fails_for_json_output(capsys):
    reporter = _reporter(
        [_violation(Severity.WARNING)],
        fail_on=LogLevel.WARNING,
    )

    assert reporter.report_json() is True
    assert '"WARNING"' in capsys.readouterr().out


def test_error_fails_with_default_threshold():
    assert _reporter([_violation(Severity.ERROR)]).report() is True


def test_info_only_fails_only_for_all_threshold():
    info = [_violation(Severity.INFO)]

    assert _reporter(info, fail_on=LogLevel.WARNING).report() is False
    assert _reporter(info, fail_on=LogLevel.ALL).report() is True


def test_hidden_warning_does_not_fail():
    reporter = _reporter(
        [_violation(Severity.WARNING)],
        fail_on=LogLevel.WARNING,
        log_level=LogLevel.ERROR,
    )

    assert reporter.report() is False


def test_fail_on_findings_remains_supported():
    reporter = _reporter(
        [_violation(Severity.WARNING)],
        fail_on_findings=True,
    )

    assert reporter.report() is True


def test_no_violations_never_fails():
    assert _reporter([], fail_on=LogLevel.ALL).report() is False
