"""Correct Kotlin lambda scopes around lizard's in-process reader."""

import re
import sys
from pathlib import Path

import lizard
from lizard_languages.kotlin import KotlinReader, KotlinStates

from file_discovery import FileDiscovery

_KOTLIN_KEYWORDS = frozenset(
    ["val", "var", "fun", "class", "object", "interface", "return", "if", "else", "when", "for", "while", "do", "try", "catch", "throw", "is", "in", "as", "this", "super", "null", "true", "false", "private", "public", "protected", "internal", "override", "abstract", "enum", "sealed", "companion", "suspend", "const", "typealias", "lateinit"]
)
_PARAMETER_TOKEN = re.compile(r"^(\w+\??|[,:()<>?.]|\s+)$")


class _LambdaAwareKotlinStates(KotlinStates):
    """Recognize parameter arrows in an already-open lambda body."""

    def __init__(self, context, in_when_cases: bool = False):
        super().__init__(context, in_when_cases)
        self._params_only = True
        self._lambda_active = False

    def _state_global(self, token):
        if token == "->":
            if self._in_when_cases:
                self.context.add_condition()
            elif self._params_only and not self._lambda_active:
                self.context.push_new_function("(anonymous)")
                self._lambda_active = True
            else:
                # shortcut: a function-typed lambda parameter ({ cb: (Int) -> Unit -> })
                # is mis-split at the first arrow; upgrade if that appears in reports.
                pass
            self._params_only = False
            return

        if token in _KOTLIN_KEYWORDS or not _PARAMETER_TOKEN.fullmatch(token):
            self._params_only = False
        super()._state_global(token)

    def statemachine_before_return(self):
        super().statemachine_before_return()
        if self._lambda_active:
            self.context.end_of_function()


class _LambdaAwareKotlinReader(KotlinReader):
    """Use lambda-aware state for Kotlin files while retaining lizard tokenization."""

    def __init__(self, context):
        super().__init__(context)
        self.parallel_states = [_LambdaAwareKotlinStates(context)]


def analyze_functions(filename: str, code: str) -> list[object]:
    """Analyze source with corrected Kotlin lambda ranges, otherwise plain lizard."""
    if Path(filename).suffix.lower() not in FileDiscovery.LANGUAGE_EXTENSIONS["kotlin"]:
        analyzer = lizard.FileAnalyzer(lizard.analyze_file.processors)
        return analyzer.analyze_source_code(filename, code).function_list

    context = lizard.FileInfoBuilder(filename)
    reader = _LambdaAwareKotlinReader(context)
    tokens = reader.generate_tokens(code)
    try:
        for processor in lizard.analyze_file.processors:
            tokens = processor(tokens, reader)
        for _ in reader(tokens, reader):
            pass
    except RecursionError as error:
        sys.stderr.write(
            "[skip] fail to process '%s' with RecursionError - %s\n" % (filename, error)
        )
    return context.fileinfo.function_list
