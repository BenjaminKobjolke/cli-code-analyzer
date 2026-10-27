"""
Base rule class for all code analysis rules
"""

import shutil
import subprocess
import sys
from abc import ABC, abstractmethod
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

from logger import Logger
from models import LogLevel, RuleResult, RuleStatus, Severity, Violation
from rules.context import RuleContext
from rules.filter_scope import FilterScopeMixin
from rules.process_utils import kill_process_tree
from rules.reporting import ViolationReportMixin


class BaseRule(FilterScopeMixin, ViolationReportMixin, ABC):
    """Abstract base class for all rules"""

    # Subclasses set this so RuleResults are stamped with a stable name. Falls
    # back to the class name if a subclass forgets.
    rule_name: str = ""

    def __init__(self, ctx: RuleContext):
        self.ctx = ctx
        self.config = ctx.config
        self.base_path = ctx.base_path
        self.output_folder = ctx.output_folder
        self.log_level = ctx.log_level
        self.max_errors = ctx.max_errors
        self.rules_file_path = ctx.rules_file_path
        self.logger = ctx.logger or Logger()
        self.language = ctx.language
        self.filter_files = ctx.filter_files
        self.filter_mode = ctx.filter_mode
        self._settings = None

    @property
    def settings(self):
        if self._settings is None:
            from settings import Settings
            self._settings = Settings()
        return self._settings

    @abstractmethod
    def check(self, file_path: Path) -> RuleResult:
        """Check the file against this rule and return a typed RuleResult."""

    def _result_name(self) -> str:
        return self.rule_name or self.__class__.__name__

    def _ok(self, violations: list[Violation]) -> RuleResult:
        """Rule ran successfully; violations may be empty (genuinely clean)."""
        return RuleResult(rule_name=self._result_name(), status=RuleStatus.OK, violations=violations)

    def _failed(self, message: str) -> RuleResult:
        """Rule could not run or its output could not be trusted."""
        return RuleResult(rule_name=self._result_name(), status=RuleStatus.FAILED, message=message)

    def _skipped(self, message: str) -> RuleResult:
        """Rule is not applicable in this context (not a failure)."""
        return RuleResult(rule_name=self._result_name(), status=RuleStatus.SKIPPED, message=message)

    def _get_relative_path(self, file_path: Path) -> str:
        """Get relative path from base path, or absolute path if not relative."""
        if self.base_path:
            try:
                return str(file_path.resolve().relative_to(self.base_path))
            except ValueError:
                return str(file_path)
        return str(file_path)

    def _count_lines(self, file_path: Path) -> int:
        """Count lines in a file, returning 0 on error."""
        try:
            with open(file_path, encoding='utf-8') as f:
                return sum(1 for _ in f)
        except Exception as e:
            self.logger.warning(f"Warning: Could not read {file_path}: {e}")
            return 0

    def _build_threshold_dict(self, exception: dict | None, base: dict) -> dict[str, float | None]:
        """Build threshold dict from exception overrides or base config."""
        def to_num(val):
            if val is None:
                return None
            try:
                return float(val)
            except (ValueError, TypeError):
                return None

        if exception:
            return {'error': to_num(exception.get('error', base.get('error'))),
                    'warning': to_num(exception.get('warning', base.get('warning'))),
                    'info': to_num(exception.get('info', base.get('info')))}
        return {'error': to_num(base.get('error')), 'warning': to_num(base.get('warning')),
                'info': to_num(base.get('info'))}

    def _get_threshold_for_file(
        self, file_path: Path, threshold_config: dict[str, Any],
        metric_id: str | None = None,  # noqa: ARG002
    ) -> dict[str, float | None]:
        """Get thresholds for a file, checking for exceptions first."""
        exceptions = threshold_config.get('exceptions', [])
        if not exceptions:
            return self._build_threshold_dict(None, threshold_config)

        # Convert dict format to list format if needed
        # Dict format: {"path": "description"} or {"path": {"warning": 600}}
        if isinstance(exceptions, dict):
            exceptions = [{'file': k, **(v if isinstance(v, dict) else {})} for k, v in exceptions.items()]

        try:
            rel_path_to_base = self._get_relative_path(file_path)
        except Exception:
            rel_path_to_base = str(file_path)

        rel_path_to_rules = None
        if self.rules_file_path:
            try:
                rules_dir = Path(self.rules_file_path).parent
                rel_path_to_rules = str(Path(file_path).resolve().relative_to(rules_dir))
            except Exception:
                pass

        rel_path_base = rel_path_to_base.replace('\\', '/')
        rel_path_rules = rel_path_to_rules.replace('\\', '/') if rel_path_to_rules else None
        filename_only = Path(file_path).name

        for exception in exceptions:
            pattern = exception.get('file', '').replace('\\', '/')
            matches_exception = any((
                self._match_file_path(rel_path_base, pattern),
                bool(rel_path_rules) and self._match_file_path(rel_path_rules, pattern),
                self._match_file_path(filename_only, pattern),
            ))
            if matches_exception:
                return self._build_threshold_dict(exception, threshold_config)

        return self._build_threshold_dict(None, threshold_config)

    def _match_file_path(self, file_path: str, pattern: str) -> bool:
        """Check if path matches pattern (exact, glob, or ends-with)."""
        if file_path == pattern:
            return True
        if fnmatch(file_path, pattern):
            return True
        return file_path.endswith((pattern, '/' + pattern))

    def _map_severity(self, severity_str: str) -> Severity:
        """Map severity string (INFO/WARNING/ERROR) to Severity enum."""
        severity_map = {
            'INFO': Severity.INFO,
            'WARNING': Severity.WARNING,
            'ERROR': Severity.ERROR,
        }
        return severity_map.get(severity_str.upper(), Severity.WARNING)

    def _filter_violations_by_log_level(self, violations: list[Violation]) -> list[Violation]:
        """Filter violations based on configured log level."""
        if self.log_level == LogLevel.ALL:
            return violations

        filtered = []
        for violation in violations:
            if (
                (self.log_level == LogLevel.ERROR and violation.severity != Severity.ERROR)
                or (self.log_level == LogLevel.WARNING and violation.severity not in (Severity.ERROR, Severity.WARNING))
            ):
                continue
            filtered.append(violation)

        return filtered

    def _run_subprocess(self, cmd: list[str], cwd: Path | None = None, timeout: int = 300) -> subprocess.CompletedProcess:
        """Run subprocess with timeout and no stdin to prevent interactive prompts."""
        process = subprocess.Popen(
            cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            encoding='utf-8', errors='replace', stdin=subprocess.DEVNULL,
            start_new_session=sys.platform != 'win32',
        )
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired as error:
            kill_process_tree(process)
            process.communicate()
            raise error
        return subprocess.CompletedProcess(cmd, process.returncode, stdout, stderr)

    def _get_tool_path(self, tool_name: str, settings_name: str | None = None) -> str | None:
        """Get tool path from PATH, local node_modules, settings, or prompt user.

        `tool_name` is the executable name (PATH/node_modules lookup). `settings_name`
        is the Settings key; defaults to `tool_name` when they match (most tools).
        """
        settings_name = settings_name or tool_name
        tool_in_path = shutil.which(tool_name)
        if tool_in_path:
            return tool_in_path

        # Check project-local node_modules/.bin/ for Node-based tools
        if self.base_path:
            for suffix in ['.cmd', '.bat', '']:
                local_bin = self.base_path / 'node_modules' / '.bin' / (tool_name + suffix)
                if local_bin.exists():
                    return str(local_bin)

        tool_path = self.settings.get_path(settings_name)
        if not tool_path:
            tool_path = self.settings.prompt_and_save(settings_name)
            if not tool_path:
                return None

        tool_path_obj = Path(tool_path)
        if not tool_path_obj.is_absolute():
            # Resolve relative paths relative to cli-code-analyzer directory
            script_dir = Path(__file__).parent.parent
            tool_path_obj = script_dir / tool_path
            tool_path = str(tool_path_obj)

        if not tool_path_obj.exists():
            self.logger.error(f"Error: {tool_name} executable not found at: {tool_path}")
            return None

        return tool_path

    def _find_pubspec(self) -> Path | None:
        """Find pubspec.yaml in base_path or parent, return containing dir."""
        pubspec_path = self.base_path / 'pubspec.yaml'
        if not pubspec_path.exists():
            pubspec_path = self.base_path.parent / 'pubspec.yaml'
        if not pubspec_path.exists():
            return None
        return pubspec_path.parent

    def _is_fvm_project(self) -> bool:
        """Check if project uses FVM (Flutter Version Management)."""
        project_root = self._find_pubspec() or self.base_path
        if not project_root:
            return False
        return (project_root / '.fvmrc').exists() or (project_root / '.fvm').is_dir()

    def _get_flutter_command(self) -> list[str]:
        """Get flutter command, using FVM prefix if detected."""
        if self._is_fvm_project() and shutil.which('fvm'):
            return ['fvm', 'flutter']
        path = self._get_tool_path('flutter')
        return [path] if path else []

    def _get_dart_command(self) -> list[str]:
        """Get dart command, using FVM prefix if detected."""
        if self._is_fvm_project() and shutil.which('fvm'):
            return ['fvm', 'dart']
        path = self._get_tool_path('dart')
        return [path] if path else []

class ProjectWideRule(BaseRule):
    """Base for rules that run once per project regardless of file count.

    Subclasses implement `_run(file_path)`; this class handles the once-only
    guard. The first call to `check()` runs the body and caches; subsequent
    calls return an empty list.
    """

    def __init__(self, ctx: RuleContext):
        super().__init__(ctx)
        self._executed = False

    def check(self, file_path: Path) -> RuleResult:
        if self._executed:
            return self._ok([])
        self._executed = True
        try:
            return self._run(file_path)
        except Exception as e:
            # Safety net: a rule that forgets to catch an error fails loudly
            # rather than crashing the run or silently returning nothing.
            self.logger.error(f"Error running {self._result_name()}: {e}")
            return self._failed(f"unexpected error: {e}")

    @abstractmethod
    def _run(self, file_path: Path) -> RuleResult:
        """Execute the project-wide analysis exactly once."""
