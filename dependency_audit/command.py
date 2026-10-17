"""Bounded, non-interactive subprocess helpers for dependency tools."""

import json
import os
import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path


class AuditToolError(RuntimeError):
    """A tool could not be resolved or returned unusable output."""


def resolve_tool(name: str) -> str:
    """Resolve an executable on PATH without prompting."""
    executable = shutil.which(name)
    if executable is None:
        raise AuditToolError(f"{name} not found")
    return executable


def run_tool(
    cmd: Sequence[str], cwd: Path, accepted: tuple[int, ...] = (0,)
) -> str:
    """Run a tool with a finite timeout and return stdout."""
    environment = os.environ.copy()
    environment["COMPOSER_NO_INTERACTION"] = "1"
    try:
        result = subprocess.run(
            list(cmd), cwd=cwd, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=180,
            stdin=subprocess.DEVNULL, env=environment, check=False,
        )
    except FileNotFoundError as error:
        raise AuditToolError(f"{cmd[0]} not found") from error
    except subprocess.TimeoutExpired as error:
        raise AuditToolError(f"{Path(cmd[0]).name} timed out after 180 seconds") from error
    if result.returncode not in accepted:
        detail = result.stderr.strip().splitlines()
        suffix = f": {detail[-1][:200]}" if detail else ""
        raise AuditToolError(f"{Path(cmd[0]).name} exited with code {result.returncode}{suffix}")
    return result.stdout


def parse_json(text: str, tool: str) -> object:
    """Parse JSON even when a tool prepends a banner."""
    start = text.find("{")
    if start < 0:
        raise AuditToolError(f"{tool} did not return JSON")
    try:
        return json.loads(text[start:])
    except json.JSONDecodeError as error:
        raise AuditToolError(f"{tool} returned invalid JSON") from error
