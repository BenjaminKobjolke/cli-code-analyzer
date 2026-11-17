"""Find JavaScript, TypeScript, and Svelte packages never referenced by source."""

import json
import re
from pathlib import Path
from typing import Any

from models import RuleResult
from rules.project_wide_rule import ProjectWideRule
from rules.unused_dependencies import (
    DependencyDeclarations,
    UnusedDependencyOptions,
    build_unused_dependency_violations,
    find_unused_dependencies,
)

_DEFAULT_IGNORES = (
    "typescript", "svelte", "tslib", "@sveltejs/adapter-auto", "@sveltejs/adapter-node",
    "@sveltejs/adapter-static", "@sveltejs/adapter-vercel", "@sveltejs/adapter-netlify",
    "@sveltejs/adapter-cloudflare", "@sveltejs/vite-plugin-svelte",
)
_DEFAULT_PATHS = {"dependencies": (".",), "dev_dependencies": ("tests", "test")}
_EXCLUDED_DIRS = {"node_modules", "dist", "build", ".svelte-kit", "coverage"}
_SOURCE_SUFFIXES = {".js", ".mjs", ".cjs", ".jsx", ".ts", ".mts", ".cts", ".tsx", ".svelte", ".vue"}
_IMPORT_PATTERN = re.compile(
    r"\b(?:import|export)\s*(?:[^'\";]*?\s+from\s*)?['\"]([^'\"]+)['\"]"
    r"|\b(?:require|import)\s*\(\s*['\"]([^'\"]+)['\"]\s*\)"
)


class JavaScriptUnusedDependenciesRule(ProjectWideRule):
    """Compare package.json dependencies with package specifiers in project files."""

    rule_name = "javascript_unused_dependencies"

    def _run(self, file_path: Path) -> RuleResult:
        root = self.base_path or file_path.parent
        manifest = root / "package.json"
        if not manifest.is_file():
            self.logger.warning("Warning: package.json not found, skipping javascript_unused_dependencies")
            return self._skipped("package.json not found")
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("package.json must contain a JSON object")
            declarations = DependencyDeclarations(
                frozenset(_dependency_names(data.get("dependencies"), "dependencies")),
                frozenset(_dependency_names(data.get("devDependencies"), "devDependencies")),
            )
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
            return self._failed(f"error parsing package.json: {error}")

        options = UnusedDependencyOptions.from_config(
            self.config,
            default_ignore_packages=_DEFAULT_IGNORES,
            default_scan_paths=_DEFAULT_PATHS,
        )
        runtime_files = self._source_files(root, options.scan_paths["dependencies"])
        dev_files = (
            self._source_files(root, options.scan_paths["dev_dependencies"], include_tests=True)
            if options.check_dev_dependencies else []
        )
        used_runtime = _used_packages(runtime_files, declarations)
        used_dev = _used_packages(dev_files, declarations) if options.check_dev_dependencies else set()
        if options.check_dev_dependencies:
            used_runtime.update(_config_package_uses(root, declarations))

        if self.config.get("ignore_tool_packages", True):
            tools = _tool_packages(root, data, declarations)
            declarations = DependencyDeclarations(
                declarations.dependencies - tools,
                declarations.dev_dependencies - tools,
            )

        unused = find_unused_dependencies(declarations, used_runtime, used_dev, options)
        unused = [
            type(item)(item.package_name, "devDependencies", item.scan_paths)
            if item.group == "dev_dependencies" else item
            for item in unused
        ]
        violations = build_unused_dependency_violations(
            unused,
            manifest_name="package.json",
            manifest_path=self._get_relative_path(manifest),
            rule_name=self.rule_name,
            severity=self._map_severity(options.severity),
        )
        return self._ok(self._filter_violations_by_log_level(violations))

    def _source_files(
        self, root: Path, scan_paths: tuple[str, ...], *, include_tests: bool = False,
    ) -> list[Path]:
        files: set[Path] = set()
        for scan_path in scan_paths:
            scan_root = root / scan_path
            if not scan_root.exists():
                continue
            candidates = [scan_root] if scan_root.is_file() else scan_root.rglob("*")
            for candidate in candidates:
                if candidate.is_file() and candidate.suffix.casefold() in _SOURCE_SUFFIXES:
                    if not _excluded(candidate, root) and (include_tests or not _in_test_dir(candidate, root)):
                        files.add(candidate)
                elif candidate.is_file() and candidate.name == "tsconfig.json" and not _excluded(candidate, root):
                    files.add(candidate)
        return sorted(files)


def _dependency_names(value: Any, key: str) -> set[str]:
    if value is None:
        return set()
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be an object")
    if not all(isinstance(name, str) for name in value):
        raise ValueError(f"{key} package names must be strings")
    return set(value)


def _used_packages(files: list[Path], declarations: DependencyDeclarations) -> set[str]:
    known = declarations.dependencies | declarations.dev_dependencies
    imported: set[str] = set()
    has_typescript = False
    for path in files:
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        has_typescript |= path.suffix.casefold() in {".ts", ".mts", ".cts", ".tsx"}
        for match in _IMPORT_PATTERN.finditer(source):
            package = _package_name(match.group(1) or match.group(2))
            if package:
                imported.add(package)
        if path.name == "tsconfig.json":
            try:
                config = json.loads(source)
            except json.JSONDecodeError:
                continue
            if isinstance(config, dict):
                imported.update(_tsconfig_packages(config, known))

    used = imported & known
    for package in known:
        if package.startswith("@types/"):
            type_name = package[len("@types/"):]
            actual = f"@{type_name.replace('__', '/')}" if "__" in type_name else type_name
            if actual in imported or (actual == "node" and has_typescript):
                used.add(package)
    return used


def _package_name(specifier: str) -> str | None:
    if not specifier or specifier.startswith((".", "/", "#")) or ":" in specifier.split("/", 1)[0]:
        return None
    parts = specifier.split("/")
    if specifier.startswith("@"):
        return "/".join(parts[:2]) if len(parts) >= 2 else None
    return parts[0]


def _tsconfig_packages(config: dict[str, Any], known: set[str]) -> set[str]:
    used: set[str] = set()
    extends = config.get("extends", [])
    if isinstance(extends, str):
        extends = [extends]
    if isinstance(extends, list):
        used.update(name for value in extends if isinstance(value, str)
                    if (name := _package_name(value)) in known)
    compiler = config.get("compilerOptions", {})
    types = compiler.get("types", []) if isinstance(compiler, dict) else []
    if isinstance(types, list):
        for value in types:
            if not isinstance(value, str):
                continue
            package = value if value.startswith("@types/") else f"@types/{value}"
            if package in known:
                used.add(package)
    return used


def _config_package_uses(root: Path, declarations: DependencyDeclarations) -> set[str]:
    configs = [root / "tsconfig.json"]
    for pattern in ("*.config.js", "*.config.mjs", "*.config.cjs", "*.config.ts", "*.config.mts"):
        configs.extend(root.glob(pattern))
    return _used_packages([path for path in configs if path.is_file()], declarations)


def _tool_packages(root: Path, data: dict[str, Any], declarations: DependencyDeclarations) -> set[str]:
    tools: set[str] = set()
    for package in declarations.dependencies | declarations.dev_dependencies:
        package_manifest = root / "node_modules" / package / "package.json"
        try:
            package_data = json.loads(package_manifest.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue
        if isinstance(package_data, dict) and package_data.get("bin"):
            tools.add(package)
    scripts = data.get("scripts", {})
    script_text = " ".join(value for value in scripts.values() if isinstance(value, str)) if isinstance(scripts, dict) else ""
    tools.update(
        package for package in declarations.dependencies | declarations.dev_dependencies
        if re.search(rf"(?<![\w@./-]){re.escape(package)}(?![\w./-])", script_text)
    )
    return tools


def _excluded(path: Path, root: Path) -> bool:
    try:
        parts = path.relative_to(root).parts[:-1]
    except ValueError:
        return True
    return any(part.casefold() in _EXCLUDED_DIRS for part in parts)


def _in_test_dir(path: Path, root: Path) -> bool:
    return any(part.casefold() in {"test", "tests"} for part in path.relative_to(root).parts[:-1])
