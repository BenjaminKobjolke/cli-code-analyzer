"""Find Python distributions declared but never imported by project source files."""

import ast
from pathlib import Path

from models import RuleResult
from rules.project_wide_rule import ProjectWideRule
from rules.python_dependency_metadata import (
    ALIASES,
    configured_imports,
    dev_manifest,
    normalize_requirement,
    package_imports,
    read_declarations,
)
from rules.unused_dependencies import (
    DependencyDeclarations,
    UnusedDependencyOptions,
    build_unused_dependency_violations,
    find_unused_dependencies,
)

_DEFAULT_IGNORES = (
    "pytest", "ruff", "mypy", "black", "coverage", "pytest-cov", "pre-commit",
    "setuptools", "wheel", "hatchling", "pip",
)
_DEFAULT_PATHS = {"dependencies": (".",), "dev_dependencies": ("tests", "test")}
_EXCLUDED_DIRS = {"test", "tests", ".venv", "venv", "site-packages", "__pycache__"}


class PythonUnusedDependenciesRule(ProjectWideRule):
    """Compare declared Python distributions with absolute source import names."""

    rule_name = "python_unused_dependencies"

    def _run(self, file_path: Path) -> RuleResult:
        root = self.base_path or file_path.parent
        manifest, declarations = read_declarations(root)
        if manifest is None:
            self.logger.warning("Warning: Python dependency manifest not found, skipping python_unused_dependencies")
            return self._skipped("Python dependency manifest not found")
        if isinstance(declarations, str):
            return self._failed(declarations)

        rule_config = dict(self.config)
        if isinstance(rule_config.get("ignore_packages"), (list, tuple, set)):
            rule_config["ignore_packages"] = [
                normalized for name in rule_config["ignore_packages"]
                if isinstance(name, str) and (normalized := normalize_requirement(name))
            ]
        options = UnusedDependencyOptions.from_config(
            rule_config,
            default_ignore_packages=_DEFAULT_IGNORES,
            default_scan_paths=_DEFAULT_PATHS,
        )
        imports, tool_packages = package_imports(root)
        for package in declarations.dependencies | declarations.dev_dependencies:
            imports.setdefault(package, set()).add(package.replace("-", "_"))
            imports[package].update(ALIASES.get(package, set()))
        imports.update(configured_imports(self.config.get("import_names")))
        if self.config.get("ignore_tool_packages", True):
            declarations = DependencyDeclarations(
                declarations.dependencies - tool_packages,
                declarations.dev_dependencies - tool_packages,
            )

        used_runtime = self._used_packages(root, options.scan_paths["dependencies"], imports)
        used_dev = (
            self._used_packages(root, options.scan_paths["dev_dependencies"], imports, development=True)
            if options.check_dev_dependencies else set()
        )
        unused = find_unused_dependencies(declarations, used_runtime, used_dev, options)
        runtime = [item for item in unused if item.group == "dependencies"]
        development = [item for item in unused if item.group == "dev_dependencies"]
        violations = build_unused_dependency_violations(
            runtime,
            manifest_name=manifest.name,
            manifest_path=self._get_relative_path(manifest),
            rule_name=self.rule_name,
            severity=self._map_severity(options.severity),
        )
        if development:
            dev_path = dev_manifest(manifest, root)
            violations.extend(build_unused_dependency_violations(
                development,
                manifest_name=dev_path.name,
                manifest_path=self._get_relative_path(dev_path),
                rule_name=self.rule_name,
                severity=self._map_severity(options.severity),
            ))
        return self._ok(self._filter_violations_by_log_level(violations))

    def _used_packages(
        self,
        root: Path,
        scan_paths: tuple[str, ...],
        import_map: dict[str, set[str]],
        *,
        development: bool = False,
    ) -> set[str]:
        package_by_import = {
            name: package for package, names in import_map.items() for name in names
        }
        used: set[str] = set()
        for scan_path in scan_paths:
            scan_root = root / scan_path
            if not scan_root.exists():
                continue
            files = [scan_root] if scan_root.is_file() else scan_root.rglob("*.py")
            for source_file in files:
                if not source_file.is_file() or _excluded(source_file, root, development=development):
                    continue
                try:
                    tree = ast.parse(source_file.read_text(encoding="utf-8"), filename=str(source_file))
                except (OSError, UnicodeError, SyntaxError) as error:
                    self.logger.info(f"Skipping Python source '{source_file}': {error}")
                    continue
                for node in ast.walk(tree):
                    for imported in _import_roots(node):
                        if imported in package_by_import:
                            used.add(package_by_import[imported])
        return used


def _import_roots(node: ast.AST) -> set[str]:
    if isinstance(node, ast.Import):
        return {alias.name.split(".", 1)[0] for alias in node.names}
    if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
        return {node.module.split(".", 1)[0]}
    return set()


def _excluded(path: Path, root: Path, *, development: bool) -> bool:
    try:
        parts = path.relative_to(root).parts[:-1]
    except ValueError:
        return True
    excluded = _EXCLUDED_DIRS - ({"test", "tests"} if development else set())
    return any(part.casefold() in excluded for part in parts)
