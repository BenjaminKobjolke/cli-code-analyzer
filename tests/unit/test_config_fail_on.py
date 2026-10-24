import json

import pytest

from config import Config
from logger import Logger
from models import LogLevel


def _write_rules(tmp_path, payload):
    rules_file = tmp_path / "rules.json"
    rules_file.write_text(json.dumps(payload), encoding="utf-8")
    return str(rules_file)


def test_fail_on_defaults_to_error(tmp_path):
    config = Config(_write_rules(tmp_path, {}), logger=Logger(quiet=True))

    assert config.get_global_fail_on() == LogLevel.ERROR


@pytest.mark.parametrize(
    ("value", "expected"),
    [("warning", LogLevel.WARNING), ("all", LogLevel.ALL)],
)
def test_fail_on_accepts_valid_levels(tmp_path, value, expected):
    config = Config(_write_rules(tmp_path, {"fail_on": value}), logger=Logger(quiet=True))

    assert config.get_global_fail_on() == expected


def test_fail_on_rejects_invalid_level(tmp_path):
    config = Config(_write_rules(tmp_path, {"fail_on": "warnings"}), logger=Logger(quiet=True))

    with pytest.raises(SystemExit) as error:
        config.get_global_fail_on()

    assert error.value.code == 1
