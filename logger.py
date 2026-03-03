"""
Logging abstraction for the code analyzer.

When quiet=True, all output is suppressed. This is used when --file is set
so that only the final report (text or JSON) is printed.
"""


class Logger:
    """Simple logger that can suppress output in quiet mode."""

    def __init__(self, quiet: bool = False):
        self.quiet = quiet

    def info(self, msg: str = ""):
        if not self.quiet:
            print(msg)

    def warning(self, msg: str = ""):
        if not self.quiet:
            print(msg)

    def error(self, msg: str = ""):
        if not self.quiet:
            print(msg)
