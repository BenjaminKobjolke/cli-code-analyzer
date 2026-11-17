"""Shared configuration and comparison for unused dependency rules."""

from collections.abc import Mapping
from dataclasses import dataclass

from models import Severity, Violation


@dataclass(frozen=True)
class DependencyDeclarations:
    """Direct runtime and development dependencies from one package manifest."""

    dependencies: frozenset[str]
    dev_dependencies: frozenset[str]


@dataclass(frozen=True)
class UnusedDependencyOptions:
    """Options shared by the ecosystem-specific unused dependency checks."""

    ignore_packages: frozenset[str]
    check_dev_dependencies: bool
    severity: str
    scan_paths: Mapping[str, tuple[str, ...]]

    @classmethod
    def from_config(
        cls,
        config: Mapping[str, object],
        *,
        default_ignore_packages: tuple[str, ...],
        default_scan_paths: Mapping[str, tuple[str, ...]],
    ) -> "UnusedDependencyOptions":
        """Read common rule options while allowing each ecosystem to define defaults."""
        ignore_packages = config.get("ignore_packages", default_ignore_packages)
        configured_scan_paths = config.get("scan_paths", default_scan_paths)
        scan_paths = {
            group: tuple(configured_scan_paths.get(group, defaults))
            for group, defaults in default_scan_paths.items()
        }
        return cls(
            ignore_packages=frozenset(ignore_packages),
            check_dev_dependencies=config.get("check_dev_dependencies", True),
            severity=config.get("severity", "warning"),
            scan_paths=scan_paths,
        )


@dataclass(frozen=True)
class UnusedDependency:
    """One declared package with no matching source import."""

    package_name: str
    group: str
    scan_paths: tuple[str, ...]


def find_unused_dependencies(
    declarations: DependencyDeclarations,
    used_in_dependencies: set[str],
    used_in_dev_dependencies: set[str],
    options: UnusedDependencyOptions,
) -> list[UnusedDependency]:
    """Compare declarations with imports, preserving runtime/dev scan semantics."""
    unused = [
        UnusedDependency(package, "dependencies", options.scan_paths["dependencies"])
        for package in sorted(declarations.dependencies - options.ignore_packages)
        if package not in used_in_dependencies
    ]
    if options.check_dev_dependencies:
        unused.extend(
            UnusedDependency(package, "dev_dependencies", options.scan_paths["dev_dependencies"])
            for package in sorted(declarations.dev_dependencies - options.ignore_packages)
            if package not in used_in_dev_dependencies and package not in used_in_dependencies
        )
    return unused


def build_unused_dependency_violations(
    unused_dependencies: list[UnusedDependency],
    *,
    manifest_name: str,
    manifest_path: str,
    rule_name: str,
    severity: Severity,
) -> list[Violation]:
    """Build consistent warnings for unused packages at their manifest location."""
    return [
        Violation(
            file_path=manifest_path,
            rule_name=rule_name,
            severity=severity,
            message=(
                f"Package '{dependency.package_name}' is listed in {manifest_name} "
                f"{dependency.group} but never imported in {', '.join(dependency.scan_paths)}"
            ),
        )
        for dependency in unused_dependencies
    ]
