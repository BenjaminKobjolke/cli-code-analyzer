import csv
from io import StringIO
from pathlib import Path

import pytest

from logger import Logger
from models import OutputLevel, Severity, Violation
from report_config import ReportConfig
from report_files import build_json, write_csv_reports
from reporter import Reporter


def test_violation_metadata_defaults_to_none_for_existing_callers():
    violation = Violation("sample.php", "php_quality", Severity.WARNING, "finding")

    assert violation.function_name is None
    assert violation.confidence is None
    assert violation.evidence is None
    assert violation.recommendation is None


def test_violation_accepts_optional_function_metadata():
    violation = Violation(
        "sample.php",
        "php_quality",
        Severity.WARNING,
        "finding",
        line=12,
        function_name="buildContent",
        confidence="medium",
        evidence="$repository->findById($id)",
        recommendation="Batch the repository lookup.",
    )

    assert violation.function_name == "buildContent"
    assert violation.confidence == "medium"
    assert violation.evidence == "$repository->findById($id)"
    assert violation.recommendation == "Batch the repository lookup."


@pytest.mark.parametrize("output_level", [OutputLevel.NORMAL, OutputLevel.VERBOSE])
def test_console_report_displays_metadata_when_present_and_hides_absent_metadata(output_level):
    stream = StringIO()
    legacy = Violation("legacy.php", "legacy_rule", Severity.WARNING, "legacy finding")
    enriched = Violation(
        "sample.php",
        "php_quality",
        Severity.WARNING,
        "finding",
        function_name="buildContent",
        confidence="medium",
        evidence="$repository->findById($id)",
        recommendation="Batch the repository lookup.",
    )
    reporter = Reporter(ReportConfig(
        violations=[legacy, enriched],
        file_count=2,
        output_level=output_level,
        logger=Logger(stream=stream),
    ))

    reporter.report()

    output = stream.getvalue()
    assert "Function: buildContent" in output
    assert "Confidence: medium" in output
    assert "Evidence: $repository->findById($id)" in output
    assert "Recommendation: Batch the repository lookup." in output
    legacy_section = output.split("legacy.php", maxsplit=1)[1].split("sample.php", maxsplit=1)[0]
    assert "Function:" not in legacy_section


def test_json_report_preserves_legacy_keys_and_includes_optional_metadata():
    legacy = Violation("legacy.php", "legacy_rule", Severity.WARNING, "legacy finding", line=4)
    enriched = Violation(
        "sample.php",
        "php_quality",
        Severity.WARNING,
        "finding",
        line=12,
        function_name="buildContent",
        confidence="medium",
        evidence="$repository->findById($id)",
        recommendation="Batch the repository lookup.",
    )

    result = build_json([legacy, enriched], [])

    assert result["violations"][0] == {
        "file_path": "legacy.php",
        "rule_name": "legacy_rule",
        "severity": "WARNING",
        "message": "legacy finding",
        "line": 4,
    }
    assert result["violations"][1] == {
        "file_path": "sample.php",
        "rule_name": "php_quality",
        "severity": "WARNING",
        "message": "finding",
        "line": 12,
        "function_name": "buildContent",
        "confidence": "medium",
        "evidence": "$repository->findById($id)",
        "recommendation": "Batch the repository lookup.",
    }


def test_csv_report_keeps_existing_columns_and_appends_optional_metadata(tmp_path: Path):
    legacy = Violation("legacy.php", "php_quality", Severity.WARNING, "legacy finding", line=4)
    enriched = Violation(
        "sample.php",
        "php_quality",
        Severity.WARNING,
        "finding",
        line=12,
        function_name="buildContent",
        confidence="medium",
        evidence="$repository->findById($id)",
        recommendation="Batch the repository lookup.",
    )

    write_csv_reports([legacy, enriched], tmp_path, None, Logger(quiet=True))

    with (tmp_path / "php_quality.csv").open(encoding="utf-8", newline="") as file:
        rows = list(csv.reader(file))
    assert rows[0][:5] == ["file_path", "line", "column", "severity", "message"]
    assert rows[0][5:] == ["function_name", "confidence", "evidence", "recommendation"]
    assert rows[1] == ["legacy.php", "4", "", "WARNING", "legacy finding", "", "", "", ""]
    assert rows[2] == [
        "sample.php",
        "12",
        "",
        "WARNING",
        "finding",
        "buildContent",
        "medium",
        "$repository->findById($id)",
        "Batch the repository lookup.",
    ]
