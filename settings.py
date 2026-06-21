"""Settings management for the code analyzer.

Storage + dispatch only. Tool catalog lives in `tool_descriptors.py`.
Three generic methods (`get_path`, `set_path`, `prompt_and_save`) handle every
tool. The named per-tool methods (`get_pmd_path`, etc.) are kept as thin shims
so existing callers do not need to change.
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

    # --- Backwards-compatible named accessors -----------------------------------
    def get_pmd_path(self) -> str | None: return self.get_path("pmd")
    def set_pmd_path(self, path: str) -> None: self.set_path("pmd", path)
    def prompt_and_save_pmd_path(self) -> str | None: return self.prompt_and_save("pmd")

    def get_dart_path(self) -> str | None: return self.get_path("dart")
    def set_dart_path(self, path: str) -> None: self.set_path("dart", path)
    def prompt_and_save_dart_path(self) -> str | None: return self.prompt_and_save("dart")

    def get_flutter_path(self) -> str | None: return self.get_path("flutter")
    def set_flutter_path(self, path: str) -> None: self.set_path("flutter", path)
    def prompt_and_save_flutter_path(self) -> str | None: return self.prompt_and_save("flutter")

    def get_ruff_path(self) -> str | None: return self.get_path("ruff")
    def set_ruff_path(self, path: str) -> None: self.set_path("ruff", path)
    def prompt_and_save_ruff_path(self) -> str | None: return self.prompt_and_save("ruff")

    def get_phpstan_path(self) -> str | None: return self.get_path("phpstan")
    def set_phpstan_path(self, path: str) -> None: self.set_path("phpstan", path)
    def prompt_and_save_phpstan_path(self) -> str | None: return self.prompt_and_save("phpstan")

    def get_php_cs_fixer_path(self) -> str | None: return self.get_path("php_cs_fixer")
    def set_php_cs_fixer_path(self, path: str) -> None: self.set_path("php_cs_fixer", path)
    def prompt_and_save_php_cs_fixer_path(self) -> str | None: return self.prompt_and_save("php_cs_fixer")

    def get_dotnet_path(self) -> str | None: return self.get_path("dotnet")
    def set_dotnet_path(self, path: str) -> None: self.set_path("dotnet", path)
    def prompt_and_save_dotnet_path(self) -> str | None: return self.prompt_and_save("dotnet")

    def get_eslint_path(self) -> str | None: return self.get_path("eslint")
    def set_eslint_path(self, path: str) -> None: self.set_path("eslint", path)
    def prompt_and_save_eslint_path(self) -> str | None: return self.prompt_and_save("eslint")

    def get_svelte_check_path(self) -> str | None: return self.get_path("svelte_check")
    def set_svelte_check_path(self, path: str) -> None: self.set_path("svelte_check", path)
    def prompt_and_save_svelte_check_path(self) -> str | None: return self.prompt_and_save("svelte_check")

    def get_tsc_path(self) -> str | None: return self.get_path("tsc")
    def set_tsc_path(self, path: str) -> None: self.set_path("tsc", path)
    def prompt_and_save_tsc_path(self) -> str | None: return self.prompt_and_save("tsc")

    def get_pyscn_path(self) -> str | None: return self.get_path("pyscn")
    def set_pyscn_path(self, path: str) -> None: self.set_path("pyscn", path)
    def prompt_and_save_pyscn_path(self) -> str | None: return self.prompt_and_save("pyscn")

    def get_dart_lsp_mcp_path(self) -> str | None: return self.get_path("dart_lsp_mcp")
    def set_dart_lsp_mcp_path(self, path: str) -> None: self.set_path("dart_lsp_mcp", path)
    def prompt_and_save_dart_lsp_mcp_path(self) -> str | None: return self.prompt_and_save("dart_lsp_mcp")
