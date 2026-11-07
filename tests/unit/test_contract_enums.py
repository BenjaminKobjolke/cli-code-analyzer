"""Unit tests for shared API contract JSON validation."""

import json
from pathlib import Path

import pytest

from logger import Logger
from models import RuleStatus, Severity
from rules.context import RuleContext
from rules.contract_enums import ContractEnumsRule


def _make_rule(base_path: Path) -> ContractEnumsRule:
    return ContractEnumsRule(RuleContext(
        config={},
        base_path=base_path.resolve(),
        logger=Logger(quiet=True),
    ))


def _valid_enums() -> dict:
    return {
        "AppError": {
            "values": ["bad_request", "not_found"],
            "direction": "api_to_client",
            "description": "API error responses",
        }
    }


def _write_json(path: Path, value: object) -> Path:
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_valid_enums_file_has_no_violations(tmp_path):
    source = _write_json(tmp_path / "enums.json", _valid_enums())

    result = _make_rule(tmp_path).check(source)

    assert result.status == RuleStatus.OK
    assert result.violations == []


def test_malformed_json_reports_relative_file_and_parse_position(tmp_path):
    source = tmp_path / "enums.json"
    source.write_text('{\n  "AppError": ', encoding="utf-8")

    result = _make_rule(tmp_path).check(source)

    assert result.status == RuleStatus.OK
    assert len(result.violations) == 1
    violation = result.violations[0]
    assert violation.file_path == "enums.json"
    assert violation.severity == Severity.ERROR
    assert "line 2" in violation.message
    assert "column" in violation.message


def test_arbitrary_valid_json_is_accepted_outside_enums_file(tmp_path):
    source = _write_json(tmp_path / "settings.json", ["not", "an enum map"])

    result = _make_rule(tmp_path).check(source)

    assert result.status == RuleStatus.OK
    assert result.violations == []


def test_non_object_enums_root_is_reported(tmp_path):
    source = _write_json(tmp_path / "enums.json", ["AppError"])

    result = _make_rule(tmp_path).check(source)

    assert len(result.violations) == 1
    assert "top level" in result.violations[0].message.lower()


@pytest.mark.parametrize(
    ("entry", "expected"),
    [
        ("invalid entry", "AppError"),
        ({"direction": "api_to_client", "description": "API errors"}, "values"),
        ({"values": [], "direction": "api_to_client", "description": "API errors"}, "values"),
        ({"values": ["ok", 3], "direction": "api_to_client", "description": "API errors"}, "string"),
        ({"values": ["z", "a"], "direction": "api_to_client", "description": "API errors"}, "sorted"),
        ({"values": ["a", "a"], "direction": "api_to_client", "description": "API errors"}, "duplicate"),
        ({"values": ["a"], "description": "API errors"}, "direction"),
        ({"values": ["a"], "direction": "both", "description": "API errors"}, "direction"),
        ({"values": ["a"], "direction": "api_to_client"}, "description"),
        ({"values": ["a"], "direction": "api_to_client", "description": ""}, "description"),
    ],
)
def test_enum_entry_defects_name_enum_and_explain_issue(tmp_path, entry, expected):
    source = _write_json(tmp_path / "enums.json", {"AppError": entry})

    result = _make_rule(tmp_path).check(source)

    assert result.status == RuleStatus.OK
    assert result.violations
    assert all(violation.severity == Severity.ERROR for violation in result.violations)
    assert all("AppError" in violation.message for violation in result.violations)
    assert any(expected.lower() in violation.message.lower() for violation in result.violations)
    assert all(violation.file_path == "enums.json" for violation in result.violations)


def test_multiple_entry_defects_are_all_reported(tmp_path):
    source = _write_json(tmp_path / "enums.json", {
        "AppError": {"values": ["b", "a", "a"], "direction": "both", "description": ""},
        "NotAnObject": None,
    })

    result = _make_rule(tmp_path).check(source)

    messages = [violation.message for violation in result.violations]
    assert any("AppError" in message and "sorted" in message for message in messages)
    assert any("AppError" in message and "duplicate" in message for message in messages)
    assert any("AppError" in message and "direction" in message for message in messages)
    assert any("AppError" in message and "description" in message for message in messages)
    assert any("NotAnObject" in message for message in messages)


def test_invalid_utf8_is_reported_as_error(tmp_path):
    source = tmp_path / "enums.json"
    source.write_bytes(b'{"AppError": "\xff"}')

    result = _make_rule(tmp_path).check(source)

    assert result.status == RuleStatus.OK
    assert len(result.violations) == 1
    assert result.violations[0].severity == Severity.ERROR
    assert "UTF-8" in result.violations[0].message


def test_non_json_suffix_is_ignored(tmp_path):
    source = tmp_path / "enums.txt"
    source.write_text("not JSON", encoding="utf-8")

    result = _make_rule(tmp_path).check(source)

    assert result.status == RuleStatus.OK
    assert result.violations == []


def test_read_failure_returns_failed_result(tmp_path, monkeypatch):
    source = tmp_path / "enums.json"
    source.write_text("{}", encoding="utf-8")

    def fail_read_text(*args, **kwargs):
        raise OSError("permission denied")

    monkeypatch.setattr(Path, "read_text", fail_read_text)
    result = _make_rule(tmp_path).check(source)

    assert result.status == RuleStatus.FAILED
    assert "enums.json" in result.message
    assert "permission denied" in result.message
