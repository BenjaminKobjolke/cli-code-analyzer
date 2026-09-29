"""Settings management for the code analyzer.

Storage + dispatch only. Tool catalog lives in `tool_descriptors.py`.
Three generic methods (`get_path`, `set_path`, `prompt_and_save`) handle every
tool; callers pass the tool name (e.g. `get_path("pmd")`). Prompts support
Tickets Watcher and fail fast when no interactive input is available.
"""
import configparser
import os
import sys
from pathlib import Path

from logger import Logger
from tool_descriptors import TOOLS_BY_NAME, ToolDescriptor

INPUT_LINE_MARKER = "::tw-input-line::"
COMMAND_RUN_ENV = "TICKETS_WATCHER_COMMAND_RUN"


class Settings:
    """Manages application settings stored in settings.ini"""

    def __init__(self, settings_file: str | None = None, logger=None):
        self.logger = logger or Logger()
        if settings_file is None:
            self.settings_file = Path(__file__).parent / "settings.ini"
        else:
            self.settings_file = Path(settings_file)
        self.config = configparser.ConfigParser()
        if self.settings_file.exists():
            self.config.read(self.settings_file)

    def _save(self):
        with open(self.settings_file, 'w') as f:
            self.config.write(f)

    def _descriptor(self, name: str) -> ToolDescriptor:
        try:
            return TOOLS_BY_NAME[name]
        except KeyError:
            raise KeyError(f"Unknown tool: {name!r}. Add a ToolDescriptor to TOOLS.") from None

    def get_path(self, name: str) -> str | None:
        d = self._descriptor(name)
        if d.section in self.config and d.key in self.config[d.section]:
            return self.config[d.section][d.key]
        return None

    def set_path(self, name: str, path: str) -> None:
        d = self._descriptor(name)
        if d.section not in self.config:
            self.config[d.section] = {}
        self.config[d.section][d.key] = path
        self._save()

    def prompt_and_save(self, name: str) -> str | None:
        """Ask for a missing tool path in a terminal or Tickets Watcher run."""
        d = self._descriptor(name)
        for line in d.install_msgs:
            self.logger.info(line)
        missing_path = (
            f"Error: {d.error_label} path not configured and no interactive terminal to ask. "
            f"Set [{d.section}] {d.key} in {self.settings_file}."
        )
        # See tools/TICKETS_WATCHER_COMMANDS.md for the phone input protocol.
        try:
            if os.environ.get(COMMAND_RUN_ENV) == "1":
                print(d.prompt_msg, flush=True)
                print(INPUT_LINE_MARKER, flush=True)
                user_input = input().strip()
            elif sys.stdin is not None and sys.stdin.isatty():
                user_input = input(d.prompt_msg).strip()
            else:
                self.logger.error(missing_path)
                return None
        except EOFError:
            self.logger.error(missing_path)
            return None

        if not user_input:
            if d.downloader is not None:
                downloaded = d.downloader(self.logger)
                if not downloaded:
                    return None
                self.set_path(name, str(downloaded))
                self.logger.info(f"{d.saved_label} path saved to {self.settings_file}")
                return str(downloaded)
            if d.skip_msg:
                self.logger.info(d.skip_msg)
            return None

        candidate = Path(user_input)
        if not candidate.exists():
            self.logger.error(f"Error: {d.error_label} executable not found at: {user_input}")
            return None

        self.set_path(name, str(candidate))
        self.logger.info(f"{d.saved_label} path saved to {self.settings_file}")
        return str(candidate)
