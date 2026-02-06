"""
Dart import rules analyzer - enforces architecture layer boundaries via configurable forbidden import rules.
"""

from fnmatch import fnmatch
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


class DartImportRulesRule(BaseRule):
    """Enforce architecture layer boundaries via configurable forbidden import rules."""

    def __init__(self, config: dict, base_path: Path | None = None, output_folder: Path | None = None, log_level: LogLevel = LogLevel.ALL, max_errors: int | None = None, rules_file_path: str | None = None):
        super().__init__(config, base_path, log_level, max_errors, rules_file_path)
        self.output_folder = output_folder
        self._executed = False

    def check(self, _file_path: Path) -> list[Violation]:
        if self._executed:
            return []
        self._executed = True

        print("\nRunning dart import rules check...")

        project_root = self._find_pubspec()
        if not project_root:
            print("Warning: pubspec.yaml not found, skipping dart_import_rules")
            return []

        analyze_path = self.config.get('analyze_path', 'lib')
        analyze_dir = project_root / analyze_path
        if not analyze_dir.exists():
            print(f"Warning: analyze path '{analyze_dir}' does not exist")
            return []

        exclude_patterns = self.config.get('exclude_patterns', ['*.g.dart', '*.freezed.dart'])
        forbidden_imports = self.config.get('forbidden_imports', [])

        if not forbidden_imports:
            print("No forbidden import rules configured")
            return []

        package_name = get_package_name(project_root)
        all_dart_files = collect_dart_files(analyze_dir, exclude_patterns)

        if not all_dart_files:
            print("No Dart files found to analyze")
            return []

        violations = []

        for dart_file in all_dart_files:
            # Get relative path from analyze_dir for rule matching
            try:
                rel_path = str(dart_file.relative_to(analyze_dir)).replace('\\', '/')
            except ValueError:
                continue

            # Check which rules apply to this file
            for rule in forbidden_imports:
                from_pattern = rule.get('from', '')
                if not fnmatch(rel_path, from_pattern):
                    continue

                cannot_import = rule.get('cannot_import', [])
                rule_severity = self._map_severity(rule.get('severity', 'error'))
                rule_message = rule.get('message', 'Architecture violation')

                # Parse imports for this file
                imports = parse_imports(dart_file)
                for imp in imports:
                    if imp['type'] not in ('import', 'export'):
                        continue

                    uri = imp['uri']
                    import_rel_path = None

                    # Resolve the import to a relative path within analyze_dir
                    if uri.startswith('package:') and package_name:
                        prefix = f'package:{package_name}/'
                        if uri.startswith(prefix):
                            import_rel_path = uri[len(prefix):]
                    elif not uri.startswith('dart:') and not uri.startswith('package:'):
                        resolved = resolve_relative_import(uri, dart_file)
                        if resolved:
                            try:
                                import_rel_path = str(resolved.relative_to(analyze_dir.resolve())).replace('\\', '/')
                            except ValueError:
                                pass

                    # Check against forbidden patterns
                    for pattern in cannot_import:
                        matched = False
                        if import_rel_path and fnmatch(import_rel_path, pattern):
                            matched = True
                        elif uri.startswith('package:') and fnmatch(uri, pattern):
                            matched = True

                        if matched:
                            try:
                                file_rel = self._get_relative_path(dart_file)
                            except Exception:
                                file_rel = str(dart_file)

                            violations.append(Violation(
                                file_path=file_rel,
                                rule_name='dart_import_rules',
                                severity=rule_severity,
                                message=f"Architecture violation: {file_rel} imports '{uri}' - {rule_message} (line {imp['line']})"
                            ))

        violations = self._filter_violations_by_log_level(violations)

        if violations:
            print(f"\nDart import rules found {len(violations)} violation(s)")
        else:
            print("\nDart import rules: No violations found")

        if self.output_folder and violations:
            output_file = self.output_folder / 'dart_import_rules.csv'
            self._write_violations_csv(
                output_file, violations,
                ['file_path', 'line', 'import_statement', 'violated_rule', 'severity'],
                lambda v: [
                    v.file_path,
                    self._extract_line(v.message),
                    self._extract_import(v.message),
                    self._extract_rule_msg(v.message),
                    v.severity.name
                ]
            )

        return violations

    @staticmethod
    def _extract_line(message: str) -> str:
        if '(line ' in message:
            return message.split('(line ')[-1].rstrip(')')
        return ''

    @staticmethod
    def _extract_import(message: str) -> str:
        if "imports '" in message:
            part = message.split("imports '")[1]
            return part.split("'")[0]
        return ''

    @staticmethod
    def _extract_rule_msg(message: str) -> str:
        if ' - ' in message:
            parts = message.split(' - ')
            if len(parts) >= 2:
                return parts[-1].split(' (line')[0].strip()
        return ''
