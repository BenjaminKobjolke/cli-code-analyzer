import json
import re
from pathlib import Path

import pytest

from exception_baseline import BaselineKey, ExceptionBaseline, baseline_path_for
from models import Severity


def _key(file: str = "src/example.py", function: str | None = None) -> BaselineKey:
    return BaselineKey(
        rule="max_lines_per_file",
        file=file,
        metric="lines",
        function=function,
    )


def test_new_observation_is_recorded_and_duplicate_observations_use_maximum(
    tmp_path: Path,
) -> None:
    path = tmp_path / "rules.exception_baseline.json"
    baseline = ExceptionBaseline(path)

    baseline.observe(_key(), 12)
    baseline.observe(_key(), 14)
    baseline.observe(_key(), 15)
    baseline.observe(_key(), 13)
    baseline.observe(_key(), 13)

    assert baseline.growth_violations() == []
    baseline.save()

    document = json.loads(path.read_text(encoding="utf-8"))
    assert document["entries"] == [
        {
            "file": "src/example.py",
            "function": None,
            "metric": "lines",
            "rule": "max_lines_per_file",
            "value": 15,
        }
    ]


def test_growth_keeps_baseline_and_returns_warning_violation(tmp_path: Path) -> None:
    path = tmp_path / "rules.exception_baseline.json"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "entries": [
                    {
                        "rule": "max_lines_per_file",
                        "file": "src/example.py",
                        "metric": "lines",
                        "function": None,
                        "value": 12,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    baseline = ExceptionBaseline(path)

    baseline.observe(_key(), 15)

    [violation] = baseline.growth_violations()
    assert violation.rule_name == "exception_growth"
    assert violation.file_path == "src/example.py"
    assert violation.function_name is None
    assert violation.severity == Severity.WARNING
    assert "12" in violation.message
    assert "15" in violation.message

    baseline.save()
    document = json.loads(path.read_text(encoding="utf-8"))
    assert document["entries"][0]["value"] == 12


def test_shrink_lowers_the_recorded_value(tmp_path: Path) -> None:
    path = tmp_path / "rules.exception_baseline.json"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "entries": [
                    {
                        "rule": "max_lines_per_file",
                        "file": "src/example.py",
                        "metric": "lines",
                        "function": None,
                        "value": 12,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    baseline = ExceptionBaseline(path)

    baseline.observe(_key(), 8)

    assert baseline.growth_violations() == []
    baseline.save()
    assert json.loads(path.read_text(encoding="utf-8"))["entries"][0]["value"] == 8


def test_selective_pruning_removes_only_unobserved_entries(tmp_path: Path) -> None:
    path = tmp_path / "rules.exception_baseline.json"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "entries": [
                    {
                        "rule": key.rule,
                        "file": key.file,
                        "metric": key.metric,
                        "function": key.function,
                        "value": value,
                    }
                    for key, value in ((_key(), 12), (_key("src/removed.py"), 7))
                ],
            }
        ),
        encoding="utf-8",
    )
    baseline = ExceptionBaseline(path)

    baseline.observe(_key(), 12)
    baseline.save(prune_unseen=True)

    entries = json.loads(path.read_text(encoding="utf-8"))["entries"]
    assert [entry["file"] for entry in entries] == ["src/example.py"]


def test_json_write_is_sorted_stable_and_skipped_when_unchanged(tmp_path: Path) -> None:
    path = tmp_path / "rules.exception_baseline.json"
    baseline = ExceptionBaseline(path)
    baseline.observe(_key("z.py"), 2)
    baseline.observe(_key("a.py"), 1)
    baseline.save()
    first = path.read_bytes()

    baseline.save()

    assert path.read_bytes() == first
    assert first.endswith(b"\n")
    assert first.index(b'"file": "a.py"') < first.index(b'"file": "z.py"')
    canonical = json.dumps(json.loads(first), indent=2, sort_keys=True) + "\n"
    assert first.decode("utf-8").replace("\r\n", "\n") == canonical


@pytest.mark.parametrize(
    "contents",
    [
        "not json",
        "{}",
        '{"version": 9, "entries": []}',
        '{"version": 1, "entries": [{"rule": "r", "file": "f", "metric": "m", "function": null, "value": true}]}',
    ],
)
def test_invalid_baseline_raises_value_error_with_path(
    tmp_path: Path, contents: str
) -> None:
    path = tmp_path / "baseline.json"
    path.write_text(contents, encoding="utf-8")

    with pytest.raises(ValueError, match=re.escape(str(path))):
        ExceptionBaseline(path)


def test_unreadable_baseline_raises_value_error_with_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "baseline.json"
    path.write_text('{"version": 1, "entries": []}', encoding="utf-8")
    original_read_text = Path.read_text

    def read_text(candidate: Path, *args: object, **kwargs: object) -> str:
        if candidate == path:
            raise OSError("permission denied")
        return original_read_text(candidate, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read_text)

    with pytest.raises(ValueError, match=re.escape(str(path))):
        ExceptionBaseline(path)


@pytest.mark.parametrize(
    ("rules_file", "expected"),
    [
        ("/project/rules.json", "/project/rules.exception_baseline.json"),
        ("/project/custom.rules.json", "/project/custom.rules.exception_baseline.json"),
        ("/project/rules", "/project/rules.exception_baseline.json"),
    ],
)
def test_baseline_path_is_next_to_rules_file(rules_file: str, expected: str) -> None:
    assert baseline_path_for(rules_file) == Path(expected)
