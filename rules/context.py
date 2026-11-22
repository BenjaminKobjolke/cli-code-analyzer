"""Shared rule context and external tool path resolution."""

import shutil
import sysconfig
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from exception_baseline import ExceptionBaseline
from logger import Logger
from models import LogLevel


class ToolSettings(Protocol):
    """Settings operations required by tool path resolution."""

    def get_path(self, name: str) -> str | None: ...

    def prompt_and_save(self, name: str) -> str | None: ...


class ToolPathResolver:
    """Resolve external tools from the standard project and user locations."""

    def __init__(
        self,
        base_path: Path | None,
        language: str | None,
        logger: Logger,
        settings_getter: Callable[[], ToolSettings],
        project_root: Path,
    ) -> None:
        self.base_path = base_path
        self.language = language
        self.logger = logger
        self.settings_getter = settings_getter
        self.project_root = project_root

    def resolve(self, tool_name: str, settings_name: str | None = None) -> str | None:
        settings_name = settings_name or tool_name
        tool_in_path = shutil.which(tool_name)
        if tool_in_path:
            return tool_in_path

        scripts = sysconfig.get_path('scripts')
        if scripts:
            scripts_dir = Path(scripts)
            for suffix in ['.exe', '.cmd', '.bat', '']:
                venv_bin = scripts_dir / (tool_name + suffix)
                if venv_bin.is_file():
                    return str(venv_bin)

        if self.base_path:
            for suffix in ['.cmd', '.bat', '']:
                local_bin = self.base_path / 'node_modules' / '.bin' / (tool_name + suffix)
                if local_bin.exists():
                    return str(local_bin)

            if self.language == 'php':
                for suffix in ['.bat', '.cmd', '']:
                    local_bin = self.base_path / 'vendor' / 'bin' / (tool_name + suffix)
                    if local_bin.exists():
                        return str(local_bin)

        settings = self.settings_getter()
        tool_path = settings.get_path(settings_name)
        if not tool_path:
            tool_path = settings.prompt_and_save(settings_name)
            if not tool_path:
                return None

        tool_path_obj = Path(tool_path)
        if not tool_path_obj.is_absolute():
            tool_path_obj = self.project_root / tool_path
            tool_path = str(tool_path_obj)

        if not tool_path_obj.exists():
            self.logger.error(f"Error: {tool_name} executable not found at: {tool_path}")
            return None
        return tool_path


@dataclass(frozen=True)
class RuleContext:
    config: dict
    base_path: Path | None = None
    output_folder: Path | None = None
    log_level: LogLevel = LogLevel.ALL
    max_errors: int | None = None
    rules_file_path: str | None = None
    logger: Logger | None = None
    language: str | None = None
    filter_files: set[str] | None = None  # base-relative posix paths, or None for whole-project
    filter_mode: str | None = None  # "file", "only_changed", or None
    exception_baseline: ExceptionBaseline | None = None
