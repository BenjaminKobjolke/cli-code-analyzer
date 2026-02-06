"""
Dart unused dependencies analyzer - finds packages in pubspec.yaml never imported in code.
"""

import csv
from pathlib import Path

import yaml

from models import LogLevel, Severity, Violation
from rules.base import BaseRule
from rules.dart_utils import collect_dart_files, parse_imports


class DartUnusedDependenciesRule(BaseRule):
    """Find packages listed in pubspec.yaml that are never imported in code."""

    def __init__(self, config: dict, base_path: Path | None = None, output_folder: Path | None = None, log_level: LogLevel = LogLevel.ALL, max_errors: int | None = None, rules_file_path: str | None = None):
        super().__init__(config, base_path, log_level, max_errors, rules_file_path)
        self.output_folder = output_folder
        self._executed = False

    def check(self, _file_path: Path) -> list[Violation]:
        if self._executed:
            return []
        self._executed = True

        print("\nRunning dart unused dependencies check...")

        project_root = self._find_pubspec()
        if not project_root:
            print("Warning: pubspec.yaml not found, skipping dart_unused_dependencies")
            return []

        pubspec_path = project_root / 'pubspec.yaml'
        try:
            with open(pubspec_path, encoding='utf-8') as f:
                pubspec_data = yaml.safe_load(f)
        except Exception as e:
            print(f"Error reading pubspec.yaml: {e}")
            return []

        if not pubspec_data:
            return []

        ignore_packages = set(self.config.get('ignore_packages', [
            'flutter', 'flutter_localizations', 'flutter_test', 'flutter_lints',
            'dart_code_linter', 'build_runner', 'json_serializable', 'freezed', 'freezed_annotation'
        ]))
        check_dev = self.config.get('check_dev_dependencies', True)
        severity_str = self.config.get('severity', 'warning')
        scan_paths = self.config.get('scan_paths', {
            'dependencies': ['lib'],
            'dev_dependencies': ['test', 'integration_test']
        })

        # Collect dependencies from pubspec.yaml
        deps = pubspec_data.get('dependencies', {}) or {}
        dev_deps = pubspec_data.get('dev_dependencies', {}) or {}

        # Remove ignored packages
        deps_to_check = {name for name in deps if name not in ignore_packages}
        dev_deps_to_check = {name for name in dev_deps if name not in ignore_packages} if check_dev else set()

        # Scan source files for package imports
        def collect_used_packages(paths: list[str]) -> set[str]:
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

        dep_scan_paths = scan_paths.get('dependencies', ['lib'])
        dev_scan_paths = scan_paths.get('dev_dependencies', ['test', 'integration_test'])

        used_in_lib = collect_used_packages(dep_scan_paths)
        used_in_test = collect_used_packages(dev_scan_paths) if check_dev else set()

        violations = []
        severity = self._map_severity(severity_str)

        # Check regular dependencies
        for pkg in sorted(deps_to_check):
            if pkg not in used_in_lib:
                rel_scan = ', '.join(dep_scan_paths)
                violations.append(Violation(
                    file_path='pubspec.yaml',
                    rule_name='dart_unused_dependencies',
                    severity=severity,
                    message=f"Package '{pkg}' is listed in pubspec.yaml dependencies but never imported in {rel_scan}"
                ))

        # Check dev dependencies
        for pkg in sorted(dev_deps_to_check):
            if pkg not in used_in_test and pkg not in used_in_lib:
                rel_scan = ', '.join(dev_scan_paths)
                violations.append(Violation(
                    file_path='pubspec.yaml',
                    rule_name='dart_unused_dependencies',
                    severity=severity,
                    message=f"Package '{pkg}' is listed in pubspec.yaml dev_dependencies but never imported in {rel_scan}"
                ))

        violations = self._filter_violations_by_log_level(violations)

        if violations:
            print(f"\nDart unused dependencies found {len(violations)} unused package(s)")
        else:
            print("\nDart unused dependencies: No unused packages found")

        if self.output_folder and violations:
            output_file = self.output_folder / 'dart_unused_dependencies.csv'
            self._write_violations_csv(
                output_file, violations,
                ['package_name', 'dependency_type', 'severity', 'message'],
                lambda v: [
                    v.message.split("'")[1] if "'" in v.message else '',
                    'dev_dependencies' if 'dev_dependencies' in v.message else 'dependencies',
                    v.severity.name,
                    v.message
                ]
            )

        return violations
