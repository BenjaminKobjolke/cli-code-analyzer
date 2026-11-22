"""Parse complexity diagnostics hidden by noqa comments."""

import re
from collections.abc import Callable
from dataclasses import dataclass

COMPLEXITY_CODES = ("C901", "PLR0911", "PLR0912", "PLR0915")

_VALUE_PATTERN = re.compile(r"\((\d+(?:\.\d+)?)\s*>\s*\d+(?:\.\d+)?\)")
_FUNCTION_PATTERN = re.compile(r"^\s*(?:async\s+)?def\s+([A-Za-z_]\w*)\b")
_NOQA_PATTERN = re.compile(r"#\s*noqa\b(?:\s*:\s*([A-Z0-9,\s]+))?", re.IGNORECASE)


@dataclass(frozen=True)
class SuppressedValue:
    """One complexity value suppressed on a function definition line."""

    file_path: str
    line: int
    function: str
    metric: str
    value: int | float


def parse_suppressed_complexity(
    diagnostics: list[dict[str, object]],
    read_line: Callable[[str, int], str | None],
) -> list[SuppressedValue]:
    """Return approved complexity findings whose definition line has matching noqa."""
    suppressed: list[SuppressedValue] = []
    for diagnostic in diagnostics:
        code = diagnostic.get("code")
        if not isinstance(code, str) or code not in COMPLEXITY_CODES:
            continue

        filename = diagnostic.get("filename")
        location = diagnostic.get("location")
        message = diagnostic.get("message")
        if not isinstance(filename, str) or not isinstance(location, dict):
            continue
        row = location.get("row")
        if not isinstance(row, int) or isinstance(row, bool) or row < 1:
            continue
        if not isinstance(message, str):
            continue

        line = read_line(filename, row)
        if not isinstance(line, str):
            continue
        noqa = _NOQA_PATTERN.search(line)
        if noqa is None or not _matches_noqa(noqa.group(1), code):
            continue

        function_match = _FUNCTION_PATTERN.match(line)
        value_match = _VALUE_PATTERN.search(message)
        if function_match is None or value_match is None:
            continue

        raw_value = value_match.group(1)
        value: int | float = float(raw_value) if "." in raw_value else int(raw_value)
        suppressed.append(
            SuppressedValue(
                file_path=filename,
                line=row,
                function=function_match.group(1),
                metric=code,
                value=value,
            )
        )
    return suppressed


def _matches_noqa(codes: str | None, diagnostic_code: str) -> bool:
    """A blanket noqa matches all findings; code lists also allow Ruff prefixes."""
    if codes is None:
        return True
    return any(
        diagnostic_code.startswith(token.strip().upper())
        for token in codes.split(",")
        if token.strip()
    )
