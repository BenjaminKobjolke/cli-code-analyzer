"""
Base rule class for all code analysis rules
"""

import csv
import shutil
import subprocess
from abc import ABC, abstractmethod
from collections.abc import Callable
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

from models import LogLevel, Severity, Violation


class BaseRule(ABC):
    """Abstract base class for all rules"""

    def __init__(self, config: dict, base_path: Path | None = None, log_level: LogLevel = LogLevel.ALL, max_errors: int | None = None, rules_file_path: str | None = None):
        self.config = config
        self.base_path = base_path
        self.log_level = log_level
        self.max_errors = max_errors
        self.rules_file_path = rules_file_path

    @abstractmethod
    def check(self, file_path: Path) -> list[Violation]:
        """Check the file against this rule and return list of violations."""

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
            print(f"Warning: Could not read {file_path}: {e}")
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
                    'warning': to_num(exception.get('warning', base.get('warning')))}
        return {'error': to_num(base.get('error')), 'warning': to_num(base.get('warning'))}

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
            if (self._match_file_path(rel_path_base, pattern) or
                (rel_path_rules and self._match_file_path(rel_path_rules, pattern)) or
                self._match_file_path(filename_only, pattern)):
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
        return subprocess.run(
            cmd, cwd=cwd, capture_output=True,
            encoding='utf-8', errors='replace', check=False,
            stdin=subprocess.DEVNULL, timeout=timeout
        )

    def _get_tool_path(self, tool_name: str, get_method: Callable, prompt_method: Callable) -> str | None:
        """Get tool path from PATH, local node_modules, settings, or prompt user."""
        tool_in_path = shutil.which(tool_name)
        if tool_in_path:
            return tool_in_path

        # Check project-local node_modules/.bin/ for Node-based tools
        if self.base_path:
            for suffix in ['.cmd', '.bat', '']:
                local_bin = self.base_path / 'node_modules' / '.bin' / (tool_name + suffix)
                if local_bin.exists():
                    return str(local_bin)

        tool_path = get_method()
        if not tool_path:
            tool_path = prompt_method()
            if not tool_path:
                return None

        tool_path_obj = Path(tool_path)
        if not tool_path_obj.is_absolute():
            # Resolve relative paths relative to cli-code-analyzer directory
            script_dir = Path(__file__).parent.parent
            tool_path_obj = script_dir / tool_path
            tool_path = str(tool_path_obj)

        if not tool_path_obj.exists():
            print(f"Error: {tool_name} executable not found at: {tool_path}")
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

    def _get_flutter_command(self, settings_getter: Callable, settings_prompter: Callable) -> list[str]:
        """Get flutter command, using FVM prefix if detected."""
        if self._is_fvm_project() and shutil.which('fvm'):
            return ['fvm', 'flutter']
        path = self._get_tool_path('flutter', settings_getter, settings_prompter)
        return [path] if path else []

    def _get_dart_command(self, settings_getter: Callable, settings_prompter: Callable) -> list[str]:
        """Get dart command, using FVM prefix if detected."""
        if self._is_fvm_project() and shutil.which('fvm'):
            return ['fvm', 'dart']
        path = self._get_tool_path('dart', settings_getter, settings_prompter)
        return [path] if path else []

    def _write_violations_csv(self, output_file: Path, violations: list[Violation],
                               headers: list[str], row_mapper: Callable[[Violation], list]) -> None:
        """Write violations to CSV, sorted by severity, limited by max_errors."""
        if not violations:
            return

        severity_order = {Severity.ERROR: 0, Severity.WARNING: 1, Severity.INFO: 2}
        sorted_violations = sorted(violations, key=lambda v: severity_order.get(v.severity, 3))

        if self.max_errors and len(sorted_violations) > self.max_errors:
            sorted_violations = sorted_violations[:self.max_errors]

        try:
            with open(output_file, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                for v in sorted_violations:
                    writer.writerow(row_mapper(v))
            print(f"Report saved to: {output_file}")
        except Exception as e:
            print(f"Error writing CSV: {e}")
