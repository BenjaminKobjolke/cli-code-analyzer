"""Tests for dart_code_linter per-file/per-metric `exceptions` threshold overrides.

Drives DartCodeLinterRule._check_metric_threshold directly with hand-built
metric dicts. Exceptions live at config['dart_code_linter']['exceptions'] as a
top-level list whose entries carry an optional `metric` field to scope them.
"""
from pathlib import Path

from logger import Logger
from rules import DartCodeLinterRule
from rules.context import RuleContext

METRICS = {'number-of-methods': {'warning': 10, 'error': 20},
           'halstead-volume': {'warning': 100, 'error': 200}}


def _rule(tmp_path: Path, exceptions=None) -> DartCodeLinterRule:
    config = {'metrics': METRICS}
    if exceptions is not None:
        config['exceptions'] = exceptions
    return DartCodeLinterRule(RuleContext(config=config, base_path=tmp_path, logger=Logger(quiet=True)))


def _file(tmp_path: Path, name: str) -> str:
    p = tmp_path / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("")
    return str(p)


def _metric(metric_id: str, value: float) -> dict:
    return {'metricsId': metric_id, 'value': value}


def test_metric_scoped_exception_raises_threshold_no_violation(tmp_path: Path):
    fp = _file(tmp_path, "lib/data/local_datasource.dart")
    rule = _rule(tmp_path, [
        {"file": "lib/data/local_datasource.dart", "metric": "number-of-methods",
         "warning": 35, "error": 45, "reason": "cohesive data-access layer"},
    ])
    # value 30 is above base error 20 but below exception warning 35 -> no violation
    assert rule._check_metric_threshold(fp, _metric('number-of-methods', 30), METRICS) is None


def test_value_above_exception_threshold_still_violates(tmp_path: Path):
    fp = _file(tmp_path, "lib/data/local_datasource.dart")
    rule = _rule(tmp_path, [
        {"file": "lib/data/local_datasource.dart", "metric": "number-of-methods",
         "warning": 35, "error": 45, "reason": "cohesive"},
    ])
    v = rule._check_metric_threshold(fp, _metric('number-of-methods', 50), METRICS)
    assert v is not None
    assert "45" in v.message  # reported at the exception threshold


def test_exception_scoped_to_metric_a_does_not_affect_metric_b(tmp_path: Path):
    fp = _file(tmp_path, "lib/data/local_datasource.dart")
    rule = _rule(tmp_path, [
        {"file": "lib/data/local_datasource.dart", "metric": "number-of-methods",
         "warning": 35, "error": 45, "reason": "cohesive"},
    ])
    # halstead-volume must still use base error 200
    v = rule._check_metric_threshold(fp, _metric('halstead-volume', 250), METRICS)
    assert v is not None
    assert "200" in v.message


def test_exception_without_metric_applies_to_all_metrics(tmp_path: Path):
    fp = _file(tmp_path, "lib/data/local_datasource.dart")
    rule = _rule(tmp_path, [
        {"file": "lib/data/local_datasource.dart", "warning": 500, "error": 1000, "reason": "all"},
    ])
    assert rule._check_metric_threshold(fp, _metric('number-of-methods', 40), METRICS) is None
    assert rule._check_metric_threshold(fp, _metric('halstead-volume', 250), METRICS) is None


def test_partial_override_error_only_keeps_base_warning(tmp_path: Path):
    fp = _file(tmp_path, "lib/data/local_datasource.dart")
    rule = _rule(tmp_path, [
        {"file": "lib/data/local_datasource.dart", "metric": "number-of-methods",
         "error": 45, "reason": "partial"},
    ])
    # value 12: above base warning 10 (kept), below exception error 45 -> WARNING at 10
    v = rule._check_metric_threshold(fp, _metric('number-of-methods', 12), METRICS)
    assert v is not None
    assert "10" in v.message


def test_non_matching_file_uses_base_threshold(tmp_path: Path):
    fp = _file(tmp_path, "lib/other.dart")
    rule = _rule(tmp_path, [
        {"file": "lib/data/local_datasource.dart", "metric": "number-of-methods",
         "warning": 35, "error": 45, "reason": "cohesive"},
    ])
    v = rule._check_metric_threshold(fp, _metric('number-of-methods', 40), METRICS)
    assert v is not None
    assert "20" in v.message  # base error threshold
