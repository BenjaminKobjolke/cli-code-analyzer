"""Tests for parsing complexity findings hidden by Ruff noqa comments."""

from rules.ruff_suppressions import COMPLEXITY_CODES, parse_suppressed_complexity


def _diagnostic(code: str, filename: str, row: int, message: str) -> dict:
    return {
        "code": code,
        "filename": filename,
        "location": {"row": row},
        "message": message,
    }


def test_parse_coded_noqa_and_extract_function_name() -> None:
    diagnostic = _diagnostic(
        "C901", "/src/example.py", 12, "'complicated' is too complex (15 > 10)"
    )
    source = {("/src/example.py", 12): "def complicated():  # noqa: C901"}

    [value] = parse_suppressed_complexity(
        [diagnostic], lambda filename, row: source.get((filename, row))
    )

    assert value.file_path == "/src/example.py"
    assert value.line == 12
    assert value.function == "complicated"
    assert value.metric == "C901"
    assert value.value == 15


def test_parse_blanket_noqa() -> None:
    diagnostic = _diagnostic("PLR0912", "example.py", 4, "Too many branches (14 > 12)")

    [value] = parse_suppressed_complexity(
        [diagnostic], lambda _filename, _row: "async def process():  # noqa"
    )

    assert value.function == "process"
    assert value.metric == "PLR0912"
    assert value.value == 14


def test_parse_all_approved_complexity_codes() -> None:
    assert COMPLEXITY_CODES == ("C901", "PLR0911", "PLR0912", "PLR0915")


def test_missing_noqa_is_not_suppressed() -> None:
    diagnostic = _diagnostic("C901", "example.py", 3, "'f' is too complex (11 > 10)")

    assert parse_suppressed_complexity(
        [diagnostic], lambda _filename, _row: "def f():"
    ) == []


def test_unrelated_coded_noqa_is_not_suppressed() -> None:
    diagnostic = _diagnostic("C901", "example.py", 3, "'f' is too complex (11 > 10)")

    assert parse_suppressed_complexity(
        [diagnostic], lambda _filename, _row: "def f():  # noqa: PLR0912"
    ) == []


def test_unparseable_complexity_message_is_ignored() -> None:
    diagnostic = _diagnostic("C901", "example.py", 3, "function is too complex")

    assert parse_suppressed_complexity(
        [diagnostic], lambda _filename, _row: "def f():  # noqa"
    ) == []


def test_non_complexity_diagnostic_is_ignored() -> None:
    diagnostic = _diagnostic("F401", "example.py", 1, "unused import")

    assert parse_suppressed_complexity(
        [diagnostic], lambda _filename, _row: "import os  # noqa"
    ) == []
