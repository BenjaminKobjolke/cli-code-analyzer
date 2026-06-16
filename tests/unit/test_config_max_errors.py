import json

from config import Config


def _write_rules(tmp_path, payload):
    rules_file = tmp_path / "rules.json"
    rules_file.write_text(json.dumps(payload), encoding="utf-8")
    return str(rules_file)


def test_max_errors_returns_positive_int(tmp_path):
    cfg = Config(_write_rules(tmp_path, {"max_errors": 20}))
    assert cfg.get_global_max_errors() == 20


def test_max_errors_absent_returns_none(tmp_path):
    cfg = Config(_write_rules(tmp_path, {"log_level": "error"}))
    assert cfg.get_global_max_errors() is None


def test_max_errors_zero_returns_none(tmp_path):
    cfg = Config(_write_rules(tmp_path, {"max_errors": 0}))
    assert cfg.get_global_max_errors() is None


def test_max_errors_negative_returns_none(tmp_path):
    cfg = Config(_write_rules(tmp_path, {"max_errors": -5}))
    assert cfg.get_global_max_errors() is None


def test_max_errors_non_int_returns_none(tmp_path):
    # Strings and bools are not valid caps.
    assert Config(_write_rules(tmp_path, {"max_errors": "20"})).get_global_max_errors() is None
    assert Config(_write_rules(tmp_path, {"max_errors": True})).get_global_max_errors() is None
