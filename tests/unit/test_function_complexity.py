"""Tests for the standalone per-function complexity report."""

import json
import sys
from pathlib import Path

import pytest

from function_complexity import run_most_complex_function
from logger import Logger

LANGUAGE_SAMPLES = [
    pytest.param(
        "sample.py",
        "def simple():\n    return 1\n\ndef complex_fn(x):\n    if x:\n        if x > 1:\n            return 1\n    return 0\n",
        "complex_fn",
        "python",
        4,
        8,
        3,
        id="python",
    ),
    pytest.param(
        "sample.dart",
        "class Foo {\n int simple() { return 1; }\n int complexFn(int x) {\n  if (x > 0) {\n   if (x > 1) { return 1; }\n  }\n  return 0;\n }\n}\n",
        "Foo::complexFn",
        "dart",
        3,
        8,
        3,
        id="dart",
    ),
    pytest.param(
        "sample.php",
        "<?php\nfunction simple() { return 1; }\nfunction complexFn($x) {\n if ($x) {\n  if ($x > 1) { return 1; }\n }\n return 0;\n}\n",
        "complexFn",
        "php",
        3,
        8,
        3,
        id="php",
    ),
    pytest.param(
        "sample.js",
        "function simple() { return 1; }\nfunction complexFn(x) {\n if (x) {\n  if (x > 1) { return 1; }\n }\n return 0;\n}\n",
        "complexFn",
        "javascript",
        2,
        7,
        3,
        id="javascript",
    ),
    pytest.param(
        "sample.ts",
        "function simple(): number { return 1; }\nfunction complexFn(x: number): number {\n if (x) {\n  if (x > 1) { return 1; }\n }\n return 0;\n}\n",
        "complexFn",
        "typescript",
        2,
        7,
        3,
        id="typescript",
    ),
    pytest.param(
        "sample.cs",
        "class Foo {\n int Simple() { return 1; }\n int ComplexFn(int x) {\n if (x > 0) {\n  if (x > 1) { return 1; }\n }\n return 0;\n }\n}\n",
        "Foo::ComplexFn",
        "csharp",
        3,
        8,
        3,
        id="csharp",
    ),
    pytest.param(
        "sample.svelte",
        "<style>\n.card { color: red; }\n</style>\n<script>\nfunction simple() { return 1; }\nfunction complexFn(x) {\n if (x) {\n  if (x > 1) { return 1; }\n }\n return 0;\n}\n</script>\n",
        "complexFn",
        "svelte",
        6,
        11,
        3,
        id="svelte",
    ),
    pytest.param(
        "sample.ahk",
        "Simple() {\n    return 1\n}\n\nCheck(x) {\n    if x {\n        if x > 1\n            return 1\n    }\n    return 0\n}\n",
        "Check",
        "autohotkey",
        5,
        11,
        3,
        id="autohotkey",
    ),
    pytest.param(
        "sample.ino",
        "void setup() {\n  if (ready) {\n    for (int i = 0; i < 3; ++i) {\n      blink(i);\n    }\n  }\n}\n",
        "setup",
        "cpp",
        1,
        7,
        3,
        id="arduino-cpp",
    ),
    pytest.param(
        "sample.kt",
        "fun simple(): Int = 1\nfun complexFn(x: Int): Int {\n if (x > 0) {\n  if (x > 1) { return 1 }\n }\n return 0\n}\n",
        "complexFn",
        "kotlin",
        2,
        7,
        3,
        id="kotlin",
    ),
]


@pytest.mark.parametrize(
    "filename,source,function_name,language,start_line,end_line,complexity",
    LANGUAGE_SAMPLES,
)
def test_reports_most_complex_function_for_supported_language(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    filename: str,
    source: str,
    function_name: str,
    language: str,
    start_line: int,
    end_line: int,
    complexity: int,
) -> None:
    (tmp_path / filename).write_text(source, encoding="utf-8")
    files_from = tmp_path / "files.txt"
    files_from.write_text(filename, encoding="utf-8")

    result = run_most_complex_function(str(tmp_path), str(files_from), Logger(quiet=True))

    report = json.loads(capsys.readouterr().out)
    assert result == 0
    assert report["function"] == {
        "file_path": filename,
        "function_name": function_name,
        "language": language,
        "start_line": start_line,
        "end_line": end_line,
        "complexity": complexity,
    }
    assert report["errors"] == []


def test_selects_highest_complexity_across_files_in_input_order(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "first.py").write_text("def first():\n    if True: pass\n", encoding="utf-8")
    (tmp_path / "second.py").write_text(
        "def winner(x):\n    if x:\n        if x > 1: pass\n    return x\n", encoding="utf-8"
    )
    files_from = tmp_path / "files.txt"
    files_from.write_text("first.py\nsecond.py", encoding="utf-8")

    assert run_most_complex_function(str(tmp_path), str(files_from), Logger(quiet=True)) == 0

    report = json.loads(capsys.readouterr().out)
    assert report["function"]["file_path"] == "second.py"
    assert report["function"]["function_name"] == "winner"


def test_ties_keep_first_file_and_lowest_start_line(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "first.py").write_text(
        "def first():\n    if True: pass\n\ndef second():\n    if True: pass\n", encoding="utf-8"
    )
    (tmp_path / "later.py").write_text("def later():\n    if True: pass\n", encoding="utf-8")
    files_from = tmp_path / "files.txt"
    files_from.write_text("first.py\nlater.py", encoding="utf-8")

    run_most_complex_function(str(tmp_path), str(files_from), Logger(quiet=True))

    report = json.loads(capsys.readouterr().out)
    assert report["function"]["function_name"] == "first"
    assert report["function"]["file_path"] == "first.py"


def test_no_functions_returns_null_function(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "empty.py").write_text("value = 1\n", encoding="utf-8")
    files_from = tmp_path / "files.txt"
    files_from.write_text("empty.py", encoding="utf-8")

    assert run_most_complex_function(str(tmp_path), str(files_from), Logger(quiet=True)) == 0

    assert json.loads(capsys.readouterr().out)["function"] is None


def test_filters_missing_outside_unsupported_and_blank_inputs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "inside.py").write_text("def inside():\n    return 1\n", encoding="utf-8")
    outside = tmp_path.parent / "outside.py"
    outside.write_text("def outside():\n    return 1\n", encoding="utf-8")
    files_from = tmp_path / "files.txt"
    files_from.write_text(
        f"\nmissing.py\n{outside}\nnotes.txt\ninside.py\n", encoding="utf-8"
    )

    assert run_most_complex_function(str(tmp_path), str(files_from), Logger(quiet=True)) == 0

    report = json.loads(capsys.readouterr().out)
    assert report["function"]["file_path"] == "inside.py"
    assert report["errors"] == []


def test_read_paths_normalizes_backslashes_and_deduplicates(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "app.py").write_text("def app():\n    return 1\n", encoding="utf-8")
    files_from = tmp_path / "files.txt"
    files_from.write_text("nested\\app.py\nnested/app.py", encoding="utf-8")

    run_most_complex_function(str(tmp_path), str(files_from), Logger(quiet=True))

    report = json.loads(capsys.readouterr().out)
    assert report["function"]["file_path"] == "nested/app.py"


def test_lizard_import_failure_reports_one_error_per_language(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "one.py").write_text("def one():\n    return 1\n", encoding="utf-8")
    (tmp_path / "two.py").write_text("def two():\n    return 2\n", encoding="utf-8")
    (tmp_path / "three.js").write_text("function three() { return 3; }", encoding="utf-8")
    files_from = tmp_path / "files.txt"
    files_from.write_text("one.py\ntwo.py\nthree.js", encoding="utf-8")

    monkeypatch.setitem(sys.modules, "lizard", None)
    assert run_most_complex_function(str(tmp_path), str(files_from), Logger(quiet=True)) == 0

    report = json.loads(capsys.readouterr().out)
    assert report["function"] is None
    assert [error["language"] for error in report["errors"]] == ["python", "javascript"]


def test_report_has_exact_json_keys(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    files_from = tmp_path / "files.txt"
    files_from.write_text("", encoding="utf-8")

    run_most_complex_function(str(tmp_path), str(files_from), Logger(quiet=True))

    report = json.loads(capsys.readouterr().out)
    assert set(report) == {"function", "errors"}
