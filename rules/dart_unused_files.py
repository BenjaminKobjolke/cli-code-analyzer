"""
Dart unused files analyzer - finds .dart files never imported by any other file.
"""

import csv
from collections import deque
from pathlib import Path

from models import LogLevel, Severity, Violation
from rules.base import BaseRule
from rules.dart_utils import (
    collect_dart_files,
    get_package_name,
    parse_imports,
    resolve_package_import,
    resolve_relative_import,
)


class DartUnusedFilesRule(BaseRule):
    """Find .dart files that are never imported/exported by any other file in the project."""

    def __init__(self, config: dict, base_path: Path | None = None, output_folder: Path | None = None, log_level: LogLevel = LogLevel.ALL, max_errors: int | None = None, rules_file_path: str | None = None):
        super().__init__(config, base_path, log_level, max_errors, rules_file_path)
        self.output_folder = output_folder
        self._executed = False

    def check(self, _file_path: Path) -> list[Violation]:
        if self._executed:
            return []
        self._executed = True

        print("\nRunning dart unused files check...")

        project_root = self._find_pubspec()
        if not project_root:
            print("Warning: pubspec.yaml not found, skipping dart_unused_files")
            return []

        analyze_path = self.config.get('analyze_path', 'lib')
        analyze_dir = project_root / analyze_path
        if not analyze_dir.exists():
            print(f"Warning: analyze path '{analyze_dir}' does not exist")
            return []

        exclude_patterns = self.config.get('exclude_patterns', ['*.g.dart', '*.freezed.dart'])
        entry_points_cfg = self.config.get('entry_points', ['lib/main.dart'])
        include_test_imports = self.config.get('include_test_imports', False)

        package_name = get_package_name(project_root)
        all_dart_files = collect_dart_files(analyze_dir, exclude_patterns)

        if not all_dart_files:
            print("No Dart files found to analyze")
            return []

        # Build import graph: file -> set of files it imports
        import_graph: dict[Path, set[Path]] = {}
        for dart_file in all_dart_files:
            resolved = dart_file.resolve()
            import_graph[resolved] = set()
            for imp in parse_imports(dart_file):
                if imp['type'] in ('import', 'export', 'part'):
                    target = None
                    if imp['uri'].startswith('package:') and package_name:
                        target = resolve_package_import(imp['uri'], package_name, project_root)
                    elif not imp['uri'].startswith('dart:') and not imp['uri'].startswith('package:'):
                        target = resolve_relative_import(imp['uri'], dart_file)
                    if target:
                        import_graph[resolved].add(target.resolve())

        # Optionally scan test/ directory for imports
        if include_test_imports:
            test_dir = project_root / 'test'
            if test_dir.exists():
                test_files = collect_dart_files(test_dir, exclude_patterns)
                for dart_file in test_files:
                    for imp in parse_imports(dart_file):
                        target = None
                        if imp['uri'].startswith('package:') and package_name:
                            target = resolve_package_import(imp['uri'], package_name, project_root)
                        elif not imp['uri'].startswith('dart:') and not imp['uri'].startswith('package:'):
                            target = resolve_relative_import(imp['uri'], dart_file)
                        if target:
                            resolved_target = target.resolve()
                            if resolved_target in import_graph:
                                # Mark as imported by adding a synthetic entry
                                if dart_file.resolve() not in import_graph:
                                    import_graph[dart_file.resolve()] = set()
                                import_graph[dart_file.resolve()].add(resolved_target)

        # BFS from entry points to find reachable files
        entry_files = set()
        for ep in entry_points_cfg:
            ep_path = (project_root / ep).resolve()
            if ep_path.exists():
                entry_files.add(ep_path)

        # If no entry points exist, skip analysis
        if not entry_files:
            print("Warning: No entry points found, skipping unused files check")
            return []

        reachable = set()
        queue = deque(entry_files)
        while queue:
            current = queue.popleft()
            if current in reachable:
                continue
            reachable.add(current)
            for target in import_graph.get(current, set()):
                if target not in reachable:
                    queue.append(target)

        # Also consider reverse: files imported by test files are reachable
        if include_test_imports:
            test_dir = project_root / 'test'
            if test_dir.exists():
                for dart_file in collect_dart_files(test_dir, exclude_patterns):
                    for target in import_graph.get(dart_file.resolve(), set()):
                        reachable.add(target)

        # Find unreachable files within analyze_dir
        all_resolved = {f.resolve() for f in all_dart_files}
        unreachable = all_resolved - reachable

        violations = []
        for unreachable_file in sorted(unreachable):
            try:
                rel_path = self._get_relative_path(unreachable_file)
            except Exception:
                rel_path = str(unreachable_file)

            violations.append(Violation(
                file_path=rel_path,
                rule_name='dart_unused_files',
                severity=Severity.WARNING,
                message=f"File '{rel_path}' is never imported by any other file in the project"
            ))

        violations = self._filter_violations_by_log_level(violations)

        if violations:
            print(f"Dart unused files found {len(violations)} unused file(s)")
        else:
            print("Dart unused files: No unused files found")

        if self.output_folder and violations:
            output_file = self.output_folder / 'dart_unused_files.csv'
            self._write_violations_csv(
                output_file, violations,
                ['file_path', 'severity', 'message'],
                lambda v: [v.file_path, v.severity.name, v.message]
            )

        return violations
