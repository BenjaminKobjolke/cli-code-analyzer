"""Unit tests for exception growth tracking in threshold rules."""

import json
from pathlib import Path

from exception_baseline import BaselineKey, ExceptionBaseline
from logger import Logger
from rules.context import RuleContext
from rules.kotlin_complexity import KotlinComplexityRule
from rules.max_lines import MaxLinesRule


def _max_lines_rule(
    base_path: Path,
    config: dict,
    baseline: ExceptionBaseline | None = None,
) -> MaxLinesRule:
    return MaxLinesRule(
        RuleContext(
            config=config,
            base_path=base_path,
            logger=Logger(quiet=True),
            exception_baseline=baseline,
        )
    )


def _lines(path: Path, count: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("line\n" * count, encoding="utf-8")


def test_max_lines_exception_records_and_warns_on_growth(tmp_path: Path) -> None:
    source = tmp_path / "src" / "example.py"
    _lines(source, 5)
    baseline = ExceptionBaseline(tmp_path / "rules.exception_baseline.json")
    config = {
        "warning": 3,
        "error": 4,
        "exceptions": [{"file": "src/example.py", "warning": 10, "error": 12}],
    }

    assert _max_lines_rule(tmp_path, config, baseline).check(source).violations == []
    baseline.save()
    assert (
        json.loads(baseline.path.read_text(encoding="utf-8"))["entries"][0]["value"]
        == 5
    )

    _lines(source, 7)
    assert _max_lines_rule(tmp_path, config, baseline).check(source).violations == []
    [warning] = baseline.growth_violations()
    assert warning.rule_name == "exception_growth"
    assert warning.file_path == "src/example.py"
    assert "5" in warning.message and "7" in warning.message


def test_max_lines_without_exception_does_not_track(tmp_path: Path) -> None:
    source = tmp_path / "example.py"
    _lines(source, 5)
    baseline = ExceptionBaseline(tmp_path / "baseline.json")

    _max_lines_rule(tmp_path, {"warning": 3, "error": 4}, baseline).check(source)

    assert baseline.growth_violations() == []
    baseline.save()
    assert not baseline.path.exists()


def test_max_lines_below_base_threshold_does_not_track(tmp_path: Path) -> None:
    source = tmp_path / "src" / "example.py"
    _lines(source, 5)
    baseline = ExceptionBaseline(tmp_path / "baseline.json")
    config = {
        "warning": 10,
        "error": 20,
        "exceptions": [{"file": "src/example.py", "warning": 15, "error": 25}],
    }

    _max_lines_rule(tmp_path, config, baseline).check(source)

    assert baseline.growth_violations() == []
    baseline.save()
    assert not baseline.path.exists()


def test_description_only_exception_does_not_track(tmp_path: Path) -> None:
    source = tmp_path / "src" / "example.py"
    _lines(source, 5)
    baseline = ExceptionBaseline(tmp_path / "baseline.json")
    config = {
        "warning": 3,
        "error": 4,
        "exceptions": [{"file": "src/example.py", "description": "legacy file"}],
    }

    _max_lines_rule(tmp_path, config, baseline).check(source)

    assert baseline.growth_violations() == []
    baseline.save()
    assert not baseline.path.exists()


def test_max_lines_works_without_a_baseline(tmp_path: Path) -> None:
    source = tmp_path / "example.py"
    _lines(source, 5)

    result = MaxLinesRule(
        RuleContext(
            config={"warning": 3, "error": 4},
            base_path=tmp_path,
            logger=Logger(quiet=True),
        )
    ).check(source)

    assert len(result.violations) == 1
    assert result.violations[0].rule_name == "max_lines_per_file"


def test_kotlin_exception_baseline_includes_function_name(tmp_path: Path) -> None:
    source = tmp_path / "Sample.kt"
    source.write_text(
        "fun sample() {\n    val value = 1\n    println(value)\n}\n", encoding="utf-8"
    )
    baseline = ExceptionBaseline(tmp_path / "baseline.json")
    rule = KotlinComplexityRule(
        RuleContext(
            config={
                "function_length": {
                    "warning": 2,
                    "error": 3,
                    "exceptions": [{"file": "Sample.kt", "warning": 10, "error": 12}],
                },
            },
            base_path=tmp_path,
            logger=Logger(quiet=True),
            exception_baseline=baseline,
        )
    )

    assert rule.check(source).violations == []

    baseline.save()
    [entry] = json.loads(baseline.path.read_text(encoding="utf-8"))["entries"]
    assert entry["rule"] == "kotlin_complexity"
    assert entry["metric"] == "function_length"
    assert entry["function"] == "sample"


def test_fractional_metric_baseline_round_trips_and_reports_growth(
    tmp_path: Path,
) -> None:
    path = tmp_path / "baseline.json"
    key = BaselineKey("crap", "src/example.py", "crap")
    baseline = ExceptionBaseline(path)
    baseline.observe(key, 12.5)
    baseline.save()

    loaded = ExceptionBaseline(path)
    loaded.observe(key, 13.25)

    [warning] = loaded.growth_violations()
    assert "12.5" in warning.message and "13.25" in warning.message
    loaded.save()
    [entry] = json.loads(path.read_text(encoding="utf-8"))["entries"]
    assert entry["value"] == 12.5
