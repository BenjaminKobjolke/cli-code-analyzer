"""Logging abstraction for the code analyzer.

When quiet=True, all output is suppressed. This is used when --file is set
so that only the final report (text or JSON) is printed.
"""

from typing import TextIO


class Logger:
    """Simple logger that can suppress output in quiet mode."""

    def __init__(self, quiet: bool = False, stream: TextIO | None = None):
        self.quiet = quiet
        self.stream = stream

    def info(self, msg: str = ""):
        if not self.quiet:
            print(msg, file=self.stream)

    def warning(self, msg: str = ""):
        if not self.quiet:
            print(msg, file=self.stream)

    def error(self, msg: str = ""):
        if not self.quiet:
            print(msg, file=self.stream)
