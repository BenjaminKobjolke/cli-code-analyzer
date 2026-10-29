"""Function-level PHP metrics based on Lizard locations and metrics."""

import re
from pathlib import Path

import lizard

from file_discovery import FileDiscovery
from models import RuleResult, Severity, Violation
from rules.base import BaseRule

_DEFAULT_THRESHOLDS = {
    "function_length": {"warning": 50},
    "cyclomatic_complexity": {"warning": 10},
    "cognitive_complexity": {"warning": 15},
    "nesting_depth": {"warning": 4},
}
_METRICS = (
    ("function_length", "function length", "lines"),
    ("cyclomatic_complexity", "cyclomatic complexity", "count"),
    ("parameter_count", "parameters", "count"),
)
_RECOMMENDATIONS = {
    "function_length": "Split the function into focused steps with clear responsibilities.",
    "cyclomatic_complexity": "Reduce branching by extracting focused helpers or simplifying conditions.",
    "parameter_count": "Group related inputs behind a focused collaborator or value object.",
    "cognitive_complexity": "Simplify nested control flow and extract focused decisions.",
    "nesting_depth": "Use guard clauses or extract nested blocks into focused helpers.",
}
_CONTROL_KEYWORDS = {"if", "elseif", "for", "foreach", "while", "do", "switch", "catch", "else"}
_TOKEN_PATTERN = re.compile(
    r"\b(?:if|elseif|for|foreach|while|do|switch|catch|else|case)\b|&&|\|\||\?(?!\?|>)|[{};]"
)


class PHPFunctionQualityRule(BaseRule):
    """Report configured maintainability thresholds for PHP functions."""

    rule_name = "php_function_quality"

    def check(self, file_path: Path) -> RuleResult:
        """Analyze PHP functions and return threshold violations."""
        if file_path.suffix.lower() not in FileDiscovery.LANGUAGE_EXTENSIONS["php"]:
            return self._ok([])

        relative_path = self._get_relative_path(file_path)
        relative_path = relative_path.replace("\\", "/")
        if any(
            self._match_file_path(relative_path, pattern.replace("\\", "/"))
            or self._match_file_path(file_path.name, pattern.replace("\\", "/"))
            for pattern in self.config.get("exclude_patterns", [])
        ):
            return self._ok([])
        try:
            source = file_path.read_text(encoding="utf-8", errors="replace")
            functions = lizard.analyze_file.analyze_source_code(str(file_path), source).function_list
        except Exception as error:
            return self._failed(f"could not analyze {relative_path}: {error}")

        violations: list[Violation] = []
        source_lines = source.splitlines(keepends=True)
        for function in functions:
            function_source = "".join(source_lines[function.start_line - 1:function.end_line])
            measured = {
                "function_length": function.nloc,
                "cyclomatic_complexity": function.cyclomatic_complexity,
                "cognitive_complexity": _cognitive_complexity(function_source),
                "nesting_depth": _nesting_depth(function_source),
                # Lizard groups PHP parameters inconsistently in some signatures.
                "parameter_count": max(function.parameter_count, _parameter_count(function_source)),
            }
            for metric, label, unit in _METRICS:
                if metric == "parameter_count" and metric not in self.config:
                    continue
                measured_value = measured[metric]
                violations.extend(self._threshold_violations(
                    file_path, relative_path, function, metric, measured_value, label, unit
                ))
            for metric in ("cognitive_complexity", "nesting_depth"):
                measured_value = measured[metric]
                violations.extend(self._threshold_violations(
                    file_path, relative_path, function, metric, measured_value,
                    metric.replace("_", " "), "count"
                ))

        violations = self._filter_violations_by_log_level(violations)
        if self.max_errors and len(violations) > self.max_errors:
            violations = violations[:self.max_errors]
        return self._ok(violations)

    def _threshold_violations(
        self,
        file_path: Path,
        relative_path: str,
        function: object,
        metric: str,
        value: int,
        label: str,
        unit: str,
    ) -> list[Violation]:
        """Build a finding when a configured warning or error threshold is reached."""
        configured = self.config.get(metric)
        if configured is None:
            defaults = _DEFAULT_THRESHOLDS.get(metric)
            if defaults is None:
                return []
            configured = defaults
        elif metric in _DEFAULT_THRESHOLDS:
            configured = {**_DEFAULT_THRESHOLDS[metric], **configured}

        thresholds = self._get_threshold_for_file(file_path, configured, metric)
        error_limit = thresholds.get("error")
        warning_limit = thresholds.get("warning")
        if error_limit is not None and value >= error_limit:
            severity, limit = Severity.ERROR, error_limit
        elif warning_limit is not None and value >= warning_limit:
            severity, limit = Severity.WARNING, warning_limit
        else:
            return []

        return [Violation(
            file_path=relative_path,
            rule_name=self.rule_name,
            severity=severity,
            message=f"{function.name}: {label} {value} {unit} (limit: {limit:g})",
            line=function.start_line,
            function_name=function.name,
            confidence="high",
            evidence=f"{label}: {value} {unit}; configured limit: {limit:g}",
            recommendation=_RECOMMENDATIONS[metric],
        )]


def _mask_php_comments_and_strings(source: str) -> str:
    """Replace comments and string contents while retaining offsets and newlines."""
    output = list(source)
    state = "code"
    quote = ""
    index = 0
    while index < len(source):
        char = source[index]
        following = source[index + 1] if index + 1 < len(source) else ""
        if state == "code":
            if char in ("'", '"', "`"):
                state, quote = "string", char
                output[index] = " "
            elif char == "/" and following == "*":
                state = "block_comment"
                output[index:index + 2] = [" ", " "]
                index += 1
            elif (char == "/" and following == "/") or char == "#":
                state = "line_comment"
                output[index] = " "
                if following == "/":
                    output[index + 1] = " "
                    index += 1
        elif state == "string":
            output[index] = " " if char != "\n" else "\n"
            if char == "\\" and index + 1 < len(source):
                if source[index + 1] != "\n":
                    output[index + 1] = " "
                index += 1
            elif char == quote:
                state = "code"
        elif state == "line_comment":
            output[index] = " " if char != "\n" else "\n"
            if char == "\n":
                state = "code"
        elif state == "block_comment":
            output[index] = " " if char != "\n" else "\n"
            if char == "*" and following == "/":
                output[index + 1] = " "
                index += 1
                state = "code"
        index += 1
    return "".join(output)


def _cognitive_complexity(source: str) -> int:
    """Approximate cognitive complexity from PHP control-flow tokens."""
    score = 0
    brace_depth = 0
    control_braces: list[int] = []
    pending_control = False
    logical_operator: str | None = None
    for match in _TOKEN_PATTERN.finditer(_mask_php_comments_and_strings(source)):
        token = match.group(0)
        if token in _CONTROL_KEYWORDS or token == "case" or token == "?":
            score += 1 + len(control_braces)
            if token in _CONTROL_KEYWORDS:
                pending_control = True
            logical_operator = None
        elif token in ("&&", "||"):
            if logical_operator != token:
                score += 1
            logical_operator = token
        elif token == "{":
            brace_depth += 1
            if pending_control:
                control_braces.append(brace_depth)
            pending_control = False
            logical_operator = None
        elif token == "}":
            if control_braces and control_braces[-1] == brace_depth:
                control_braces.pop()
            brace_depth = max(0, brace_depth - 1)
            pending_control = False
            logical_operator = None
        elif token == ";":
            pending_control = False
            logical_operator = None
    return score


def _parameter_count(source: str) -> int:
    """Count top-level parameters from the PHP function signature."""
    masked = _mask_php_comments_and_strings(source)
    declaration = re.search(r"\bfunction\s*&?\s*(?:[A-Za-z_]\w*\s*)?\(", masked)
    if declaration is None:
        return 0
    opening = masked.find("(", declaration.start())
    depth = 0
    commas = 0
    has_value = False
    for char in masked[opening + 1:]:
        if char == "(":
            depth += 1
        elif char == ")":
            if depth == 0:
                return commas + int(has_value)
            depth -= 1
        elif char in "[{":
            depth += 1
        elif char in "]}":
            depth = max(0, depth - 1)
        elif char == "," and depth == 0:
            commas += 1
        elif not char.isspace():
            has_value = True
    return 0


def _nesting_depth(source: str) -> int:
    """Return the deepest nesting of braced control-flow constructs."""
    depth = 0
    brace_depth = 0
    control_braces: list[int] = []
    pending_control = False
    maximum = 0
    for match in _TOKEN_PATTERN.finditer(_mask_php_comments_and_strings(source)):
        token = match.group(0)
        if token in _CONTROL_KEYWORDS:
            pending_control = True
        elif token == "{":
            brace_depth += 1
            if pending_control:
                depth += 1
                control_braces.append(brace_depth)
                maximum = max(maximum, depth)
            pending_control = False
        elif token == "}":
            if control_braces and control_braces[-1] == brace_depth:
                control_braces.pop()
                depth -= 1
            brace_depth = max(0, brace_depth - 1)
            pending_control = False
        elif token == ";":
            pending_control = False
    return maximum
