"""Typed JSON models for the most-complex-function command."""

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class FunctionComplexity:
    """One function selected from the supplied source files."""

    file_path: str
    function_name: str
    language: str
    start_line: int
    end_line: int
    complexity: int

    def to_dict(self) -> dict[str, object]:
        """Return the stable JSON shape consumed by the watcher."""
        return asdict(self)


@dataclass(frozen=True)
class LanguageError:
    """A source file or language analyzer failure that did not stop the report."""

    language: str
    message: str

    def to_dict(self) -> dict[str, str]:
        """Return the stable JSON shape consumed by the watcher."""
        return asdict(self)


@dataclass(frozen=True)
class ComplexityReport:
    """The selected function and any per-language failures."""

    function: FunctionComplexity | None
    errors: list[LanguageError]

    def to_dict(self) -> dict[str, object]:
        """Return the complete machine-readable report."""
        return {
            "function": self.function.to_dict() if self.function else None,
            "errors": [error.to_dict() for error in self.errors],
        }
