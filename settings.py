"""Settings management for the code analyzer.

Storage + dispatch only. Tool catalog lives in `tool_descriptors.py`.
Three generic methods (`get_path`, `set_path`, `prompt_and_save`) handle every
tool; callers pass the tool name (e.g. `get_path("pmd")`).
"""
import configparser
from pathlib import Path

from logger import Logger
from tool_descriptors import TOOLS_BY_NAME, ToolDescriptor


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
        d = self._descriptor(name)
        for line in d.install_msgs:
            self.logger.info(line)
        user_input = input(d.prompt_msg).strip()

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
