"""Run Dart rules once per package in rootless multi-package workspaces."""

from collections.abc import Callable
from pathlib import Path

from models import RuleResult, RuleStatus
from rules.base import ProjectWideRule
from rules.context import RuleContext
from rules.dart_utils import find_dart_package_roots


class DartPackageRule(ProjectWideRule):
    """Adapt project-wide Dart rules to workspaces without a root pubspec."""

    def __init__(self, ctx: RuleContext):
        super().__init__(ctx)
        self._package_root: Path | None = None

    def _find_pubspec(self) -> Path | None:
        return self._package_root or super()._find_pubspec()

    def _is_fvm_project(self) -> bool:
        return (super()._is_fvm_project()
                or (self.base_path is not None and
                    ((self.base_path / '.fvmrc').exists() or (self.base_path / '.fvm').is_dir())))

    def _filtered_paths(self, extensions: tuple[str, ...] | None = None,
                        exclude: Callable[[Path], bool] | None = None) -> list[Path] | None:
        paths = super()._filtered_paths(extensions, exclude)
        if self._package_root is None or paths is None:
            return paths
        package_root = self._package_root.resolve()
        return [path for path in paths if path.resolve().is_relative_to(package_root)]

    def _workspace_relative(self, raw_path: str) -> str | None:
        if self._package_root is None:
            return None
        return self._get_relative_path(self._package_root / raw_path).replace('\\', '/')

    def _run(self, file_path: Path) -> RuleResult:
        if super()._find_pubspec():
            return self._run_package(file_path)

        package_roots = find_dart_package_roots(self.base_path)
        if not package_roots:
            return self._run_package(file_path)

        results = []
        for package_root in package_roots:
            relative_root = self._get_relative_path(package_root).replace('\\', '/')
            self.logger.info(f"Package {relative_root}:")
            self._package_root = package_root
            try:
                results.append((relative_root, self._run_package(file_path)))
            except Exception as error:
                results.append((relative_root, self._failed(f"unexpected error: {error}")))
            finally:
                self._package_root = None

        violations = [violation for _, result in results for violation in result.violations]
        failures = [(root, result.message) for root, result in results
                    if result.status == RuleStatus.FAILED]
        if failures:
            message = "; ".join(f"{root}: {reason or 'rule failed'}" for root, reason in failures)
            return RuleResult(self._result_name(), RuleStatus.FAILED, violations, message)

        if all(result.status == RuleStatus.SKIPPED for _, result in results):
            message = "; ".join(f"{root}: {result.message or 'skipped'}"
                                 for root, result in results)
            return RuleResult(self._result_name(), RuleStatus.SKIPPED, violations, message)

        return self._ok(violations)

    def _run_package(self, file_path: Path) -> RuleResult:
        """Execute the rule for one package."""
        raise NotImplementedError
