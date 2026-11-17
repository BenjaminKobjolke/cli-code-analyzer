"""
Dart unused dependencies analyzer - finds packages in pubspec.yaml never imported in code.
"""

from pathlib import Path

import yaml

from models import RuleResult
from rules.dart_package_rule import DartPackageRule
from rules.dart_utils import collect_dart_files, parse_imports
from rules.unused_dependencies import (
    DependencyDeclarations,
    UnusedDependencyOptions,
    build_unused_dependency_violations,
    find_unused_dependencies,
)


class DartUnusedDependenciesRule(DartPackageRule):
    """Find packages listed in pubspec.yaml that are never imported in code."""

    rule_name = 'dart_unused_dependencies'

    def _run_package(self, _file_path: Path) -> RuleResult:
        self.logger.info("\nRunning dart unused dependencies check...")

        project_root = self._find_pubspec()
        if not project_root:
            self.logger.warning("Warning: pubspec.yaml not found, skipping dart_unused_dependencies")
            return self._skipped("pubspec.yaml not found")

        pubspec_path = project_root / 'pubspec.yaml'
        try:
            with open(pubspec_path, encoding='utf-8') as f:
                pubspec_data = yaml.safe_load(f)
        except Exception as e:
            self.logger.error(f"Error reading pubspec.yaml: {e}")
            return self._failed(f"error parsing pubspec.yaml: {e}")

        if not pubspec_data:
            return self._skipped("pubspec.yaml is empty")

        default_ignore_packages = (
            'flutter', 'flutter_localizations', 'flutter_test', 'flutter_lints',
            'dart_code_linter', 'build_runner', 'json_serializable', 'freezed', 'freezed_annotation'
        )
        default_scan_paths = {
            'dependencies': ('lib',),
            'dev_dependencies': ('test', 'integration_test'),
        }
        options = UnusedDependencyOptions.from_config(
            self.config,
            default_ignore_packages=default_ignore_packages,
            default_scan_paths=default_scan_paths,
        )

        # Collect dependencies from pubspec.yaml
        deps = pubspec_data.get('dependencies', {}) or {}
        dev_deps = pubspec_data.get('dev_dependencies', {}) or {}
        declarations = DependencyDeclarations(frozenset(deps), frozenset(dev_deps))

        # Scan source files for package imports
        def collect_used_packages(paths: tuple[str, ...]) -> set[str]:
            used = set()
            for scan_path in paths:
                scan_dir = project_root / scan_path
                if not scan_dir.exists():
                    continue
                for dart_file in collect_dart_files(scan_dir):
                    for imp in parse_imports(dart_file):
                        uri = imp['uri']
                        if uri.startswith('package:'):
                            # Extract package name: package:foo/bar.dart -> foo
                            pkg_name = uri.split(':')[1].split('/')[0]
                            used.add(pkg_name)
            return used

        dependency_paths = options.scan_paths['dependencies']
        dev_dependency_paths = options.scan_paths['dev_dependencies']
        used_in_dependencies = collect_used_packages(dependency_paths)
        used_in_dev_dependencies = (
            collect_used_packages(dev_dependency_paths) if options.check_dev_dependencies else set()
        )
        unused_dependencies = find_unused_dependencies(
            declarations, used_in_dependencies, used_in_dev_dependencies, options)
        violations = build_unused_dependency_violations(
            unused_dependencies,
            manifest_name='pubspec.yaml',
            manifest_path=self._workspace_relative('pubspec.yaml') or 'pubspec.yaml',
            rule_name=self.rule_name,
            severity=self._map_severity(options.severity),
        )

        violations = self._filter_violations_by_log_level(violations)

        if violations:
            self.logger.info(f"Dart unused dependencies found {len(violations)} unused package(s)")
        else:
            self.logger.info("Dart unused dependencies: No unused packages found")

        return self._ok(violations)
