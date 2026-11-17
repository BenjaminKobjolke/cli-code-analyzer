"""Find Composer packages whose autoloaded namespaces are not used by project PHP files."""

import json
import re
from pathlib import Path
from typing import Any

from logger import Logger
from models import RuleResult
from rules.project_wide_rule import ProjectWideRule
from rules.unused_dependencies import (
    DependencyDeclarations,
    UnusedDependencyOptions,
    build_unused_dependency_violations,
    find_unused_dependencies,
)

_DEFAULT_IGNORE_PACKAGES: tuple[str, ...] = ()
_DEFAULT_SCAN_PATHS = {"dependencies": (".",), "dev_dependencies": ("tests", "test")}
_NAMESPACE_TOKEN = re.compile(r"(?<![A-Za-z0-9_])\\?([A-Za-z_][A-Za-z0-9_]*(?:\\[A-Za-z_][A-Za-z0-9_]*)+)")
_PSR0_TOKEN = re.compile(r"(?<![A-Za-z0-9_])([A-Za-z_][A-Za-z0-9_]*_[A-Za-z0-9_]+)")
_GROUPED_USE = re.compile(r"\buse\s+([^;{}]+)\\\{([^}]+)\}\s*;", re.IGNORECASE)
_PHP_STRING = re.compile(r"'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\"", re.DOTALL)
_PHP_COMMENT = re.compile(r"//[^\r\n]*|#(?!\[)[^\r\n]*|/\*.*?\*/", re.DOTALL)


class PHPUnusedDependenciesRule(ProjectWideRule):
    """Compare Composer requirements with namespaces used in application and test PHP."""

    rule_name = "php_unused_dependencies"

    def _run(self, file_path: Path) -> RuleResult:
        project_root = self.base_path or file_path.parent
        manifest_path = project_root / "composer.json"
        if not manifest_path.is_file():
            self.logger.warning("Warning: composer.json not found, skipping php_unused_dependencies")
            return self._skipped("composer.json not found")

        try:
            manifest = _read_json(manifest_path)
        except (OSError, json.JSONDecodeError) as error:
            return self._failed(f"error parsing composer.json: {error}")
        if not isinstance(manifest, dict):
            return self._failed("error parsing composer.json: expected an object")

        lock_path = project_root / "composer.lock"
        installed_path = project_root / "vendor" / "composer" / "installed.json"
        if lock_path.is_file():
            try:
                package_data = _read_json(lock_path)
            except (OSError, json.JSONDecodeError) as error:
                return self._failed(f"error parsing composer.lock: {error}")
            if not isinstance(package_data, dict):
                return self._failed("error parsing composer.lock: expected an object")
            runtime_packages = package_data.get("packages", [])
            dev_packages = package_data.get("packages-dev", [])
            if not isinstance(runtime_packages, list) or not isinstance(dev_packages, list):
                return self._failed("error parsing composer.lock: expected package lists")
            packages = [*runtime_packages, *dev_packages]
        elif installed_path.is_file():
            try:
                package_data = _read_json(installed_path)
            except (OSError, json.JSONDecodeError) as error:
                return self._failed(f"error parsing vendor/composer/installed.json: {error}")
            if isinstance(package_data, list):
                packages = package_data
            elif isinstance(package_data, dict) and isinstance(package_data.get("packages"), list):
                packages = package_data["packages"]
            else:
                return self._failed("error parsing vendor/composer/installed.json: expected package list")
        else:
            self.logger.warning("Warning: Composer lock/install data not found, skipping php_unused_dependencies")
            return self._skipped("composer.lock and vendor/composer/installed.json not found")

        package_metadata = {
            package["name"].casefold(): package
            for package in packages
            if isinstance(package, dict) and isinstance(package.get("name"), str)
        }
        options = UnusedDependencyOptions.from_config(
            self.config,
            default_ignore_packages=_DEFAULT_IGNORE_PACKAGES,
            default_scan_paths=_DEFAULT_SCAN_PATHS,
        )
        declarations = DependencyDeclarations(
            frozenset(_requirements(manifest.get("require"))),
            frozenset(_requirements(manifest.get("require-dev"))),
        )
        namespace_map = _namespace_map(
            declarations.dependencies | declarations.dev_dependencies,
            package_metadata,
            ignore_tool_packages=self.config.get("ignore_tool_packages", True),
            logger=self.logger,
        )
        declarations = DependencyDeclarations(
            declarations.dependencies.intersection(namespace_map),
            declarations.dev_dependencies.intersection(namespace_map),
        )

        used_in_dependencies = self._used_packages(project_root, options.scan_paths["dependencies"],
                                                   namespace_map, development=False)
        used_in_dev_dependencies = (
            self._used_packages(project_root, options.scan_paths["dev_dependencies"], namespace_map,
                                development=True)
            if options.check_dev_dependencies else set()
        )
        unused = find_unused_dependencies(
            declarations, used_in_dependencies, used_in_dev_dependencies, options)
        violations = build_unused_dependency_violations(
            unused,
            manifest_name="composer.json",
            manifest_path=self._get_relative_path(manifest_path),
            rule_name=self.rule_name,
            severity=self._map_severity(options.severity),
        )
        return self._ok(self._filter_violations_by_log_level(violations))

    def _used_packages(
        self,
        root: Path,
        scan_paths: tuple[str, ...],
        namespace_map: dict[str, set[str]],
        *,
        development: bool,
    ) -> set[str]:
        prefixes = sorted(
            ((prefix, package) for package, values in namespace_map.items() for prefix in values),
            key=lambda item: len(item[0]),
            reverse=True,
        )
        used: set[str] = set()
        for scan_path in scan_paths:
            scan_root = root / scan_path
            if not scan_root.exists():
                continue
            files = [scan_root] if scan_root.is_file() else scan_root.rglob("*.php")
            for php_file in files:
                if not php_file.is_file() or _excluded(php_file, root, development=development):
                    continue
                source = php_file.read_text(encoding="utf-8", errors="replace")
                tokens = {token.casefold() for token in _namespace_tokens(source)}
                for token in tokens:
                    for prefix, package in prefixes:
                        if (token == prefix or token.startswith(prefix + "\\")
                                or (prefix.endswith("_") and token.startswith(prefix))):
                            used.add(package)
                            break
        return used


def _read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def _requirements(value: object) -> set[str]:
    if not isinstance(value, dict):
        return set()
    return {
        name for name in value
        if isinstance(name, str) and not _is_platform_requirement(name)
    }


def _is_platform_requirement(name: str) -> bool:
    normalized = name.casefold()
    return normalized in {"php", "hhvm"} or normalized.startswith(("php-", "ext-", "lib-"))


def _namespace_map(
    package_names: frozenset[str],
    package_metadata: dict[str, dict[str, Any]],
    *,
    ignore_tool_packages: bool,
    logger: Logger,
) -> dict[str, set[str]]:
    namespace_map: dict[str, set[str]] = {}
    for name in package_names:
        package = package_metadata.get(name.casefold())
        if package is None:
            logger.info(f"Skipping Composer package '{name}': no lock/install metadata")
            continue
        if ignore_tool_packages and (package.get("bin") or package.get("type") == "composer-plugin"):
            continue
        autoload = package.get("autoload", {})
        if not isinstance(autoload, dict):
            autoload = {}
        prefixes = {
            prefix.strip("\\").casefold()
            for kind in ("psr-4", "psr-0")
            for prefix in autoload.get(kind, {})
            if isinstance(prefix, str) and prefix.strip("\\")
        }
        if not prefixes:
            logger.info(f"Skipping Composer package '{name}': autoload namespaces cannot be established")
            continue
        namespace_map[name] = prefixes
    return namespace_map


def _namespace_tokens(source: str) -> set[str]:
    source = _PHP_COMMENT.sub(" ", _PHP_STRING.sub(" ", source))
    tokens = {match.group(1) for pattern in (_NAMESPACE_TOKEN, _PSR0_TOKEN) for match in pattern.finditer(source)}
    for match in _GROUPED_USE.finditer(source):
        prefix = match.group(1).strip().strip("\\")
        tokens.add(prefix)
        for item in match.group(2).split(","):
            name = item.strip().split(" as ", 1)[0].strip().strip("\\")
            if name:
                tokens.add(f"{prefix}\\{name}")
    return tokens


def _excluded(path: Path, root: Path, *, development: bool) -> bool:
    try:
        parts = path.relative_to(root).parts[:-1]
    except ValueError:
        return True
    excluded = {"vendor"} if development else {"vendor", "test", "tests"}
    return any(part.casefold() in excluded for part in parts)
