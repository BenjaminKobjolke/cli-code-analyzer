"""Base class for analyzers that run once per project."""

from abc import abstractmethod
from pathlib import Path

from models import RuleResult
from rules.base import BaseRule
from rules.context import RuleContext


class ProjectWideRule(BaseRule):
    """Run a rule once and report unexpected errors as failed results."""

    def __init__(self, ctx: RuleContext) -> None:
        super().__init__(ctx)
        self._executed = False

    def check(self, file_path: Path) -> RuleResult:
        if self._executed:
            return self._ok([])
        self._executed = True
        try:
            return self._run(file_path)
        except Exception as error:
            self.logger.error(f"Error running {self._result_name()}: {error}")
            return self._failed(f"unexpected error: {error}")

    @abstractmethod
    def _run(self, file_path: Path) -> RuleResult:
        """Execute project-wide analysis exactly once."""
