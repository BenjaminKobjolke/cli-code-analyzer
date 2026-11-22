"""Regression tests for Kotlin-specific lizard function ranges."""

from pathlib import Path

import lizard

from kotlin_lizard import analyze_functions
from tests.unit.kotlin_complexity_fixtures import MAIN_ACTIVITY


def _by_name(functions: list[object], name: str) -> object:
    return next(function for function in functions if function.name == name)


def test_lambda_ends_before_following_override() -> None:
    functions = analyze_functions("MainActivity.kt", MAIN_ACTIVITY)

    anonymous = _by_name(functions, "(anonymous)")
    configure = _by_name(functions, "configureFlutterEngine")
    on_new_intent = _by_name(functions, "onNewIntent")

    assert (anonymous.start_line, anonymous.end_line) == (3, 7)
    assert (configure.start_line, configure.end_line) == (2, 9)
    assert (on_new_intent.start_line, on_new_intent.end_line) == (11, 17)
    assert on_new_intent.cyclomatic_complexity == 3


def test_when_arrows_remain_conditions() -> None:
    functions = analyze_functions(
        "When.kt",
        "fun choose(value: Int) = when (value) {\n"
        "    1 -> \"a\"\n"
        "    else -> \"b\"\n"
        "}\n",
    )

    assert [function.name for function in functions] == ["choose"]
    assert functions[0].cyclomatic_complexity == 2


def test_property_lambda_and_following_function_are_separate() -> None:
    functions = analyze_functions(
        "Callbacks.kt",
        "class Callbacks {\n"
        "    val cb: (Int) -> Unit = { x -> println(x) }\n"
        "    fun next() { println(1) }\n"
        "}\n",
    )

    anonymous = _by_name(functions, "(anonymous)")
    next_function = _by_name(functions, "next")
    assert (anonymous.start_line, anonymous.end_line) == (2, 2)
    assert (next_function.start_line, next_function.end_line) == (3, 3)


def test_destructured_lambda_is_a_function() -> None:
    functions = analyze_functions(
        "Destructured.kt",
        "fun visit(items: List<Pair<Int, Int>>) {\n"
        "    items.forEach { (k, v) -> use(k, v) }\n"
        "}\n",
    )

    anonymous = _by_name(functions, "(anonymous)")
    assert (anonymous.start_line, anonymous.end_line) == (2, 2)


def test_arrowless_lambda_is_not_a_separate_function() -> None:
    functions = analyze_functions("Map.kt", "fun map() = listOf(1).map { it + 1 }\n")

    assert [function.name for function in functions] == ["map"]


def test_non_kotlin_uses_plain_lizard() -> None:
    code = "def value():\n    return 1\n"
    expected = lizard.FileAnalyzer(lizard.analyze_file.processors).analyze_source_code(
        "sample.py", code
    ).function_list

    actual = analyze_functions("sample.py", code)

    assert [(item.name, item.start_line, item.end_line) for item in actual] == [
        (item.name, item.start_line, item.end_line) for item in expected
    ]
