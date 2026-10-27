"""Process-tree operations used by rules that invoke external analyzers."""

import os
import signal
import subprocess
import sys
from contextlib import suppress


def kill_process_tree(process: subprocess.Popen[str]) -> None:
    """Stop a subprocess and its children on the current platform."""
    if sys.platform == 'win32':
        subprocess.run(
            ['taskkill', '/T', '/F', '/PID', str(process.pid)],
            capture_output=True,
            check=False,
        )
    else:
        with suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
