"""
Dart unused code analyzer - finds unused classes, functions, enums, etc. using dart-lsp-mcp.
"""

from pathlib import Path

from models import LogLevel, Severity, Violation
from rules.base import BaseRule
from rules.dart_utils import collect_dart_files

# Optional dependency: dart-lsp-mcp
try:
    from dart_lsp_watcher.api import find_references, get_document_symbols
    HAS_DART_LSP = True
except ImportError:
    HAS_DART_LSP = False


class DartUnusedCodeRule(BaseRule):
    """Find unused classes, functions, enums, mixins, typedefs, extensions across the project using LSP."""

    def __init__(self, config: dict, base_path: Path | None = None, output_folder: Path | None = None, log_level: LogLevel = LogLevel.ALL, max_errors: int | None = None, rules_file_path: str | None = None):
        super().__init__(config, base_path, log_level, max_errors, rules_file_path)
        self.output_folder = output_folder
        self._executed = False

    def check(self, _file_path: Path) -> list[Violation]:
        if self._executed:
            return []
        self._executed = True

        print("\nRunning dart unused code check...")

        if not HAS_DART_LSP:
            print("Warning: dart-lsp-mcp not installed. Skipping dart_unused_code analyzer.")
            print("Install from: D:\\GIT\\BenjaminKobjolke\\dart-lsp-mcp")
            return []

        project_root = self._find_pubspec()
        if not project_root:
            print("Warning: pubspec.yaml not found, skipping dart_unused_code")
            return []

        analyze_path = self.config.get('analyze_path', 'lib')
        analyze_dir = project_root / analyze_path
        if not analyze_dir.exists():
            print(f"Warning: analyze path '{analyze_dir}' does not exist")
            return []

        exclude_patterns = self.config.get('exclude_patterns', ['*.g.dart', '*.freezed.dart'])
        ignore_names = set(self.config.get('ignore_names', ['main', 'build']))
        scan_test_refs = self.config.get('scan_test_references', True)
        severity_str = self.config.get('severity', 'warning')
        severity = self._map_severity(severity_str)

        all_dart_files = collect_dart_files(analyze_dir, exclude_patterns)
        if not all_dart_files:
            print("No Dart files found to analyze")
            return []

        violations = []
        total_symbols = 0
        checked_symbols = 0

        print(f"Scanning {len(all_dart_files)} files for unused code...")

        for dart_file in all_dart_files:
            try:
                symbols = get_document_symbols(str(dart_file))
            except Exception as e:
                print(f"Warning: Could not get symbols for {dart_file}: {e}")
                continue

            if not symbols:
                continue

            for symbol in symbols:
                name = symbol.get('name', '')
                kind = symbol.get('kind', '')
                line = symbol.get('line', 0)
                col = symbol.get('col', symbol.get('column', 0))

                # Skip private symbols (start with _), ignored names, and constructors
                if name.startswith('_') or name in ignore_names:
                    continue

                # Only check top-level declarations
                if kind not in ('class', 'function', 'enum', 'mixin', 'typedef', 'extension', 'topLevelVariable'):
                    continue

                total_symbols += 1

                try:
                    refs = find_references(str(dart_file), line, col)
                except Exception:
                    continue

                checked_symbols += 1

                # Filter out the declaration itself - only count usages
                usage_count = 0
                if refs:
                    for ref in refs:
                        ref_file = ref.get('file', '')
                        ref_line = ref.get('line', 0)
                        # Skip the declaration itself
                        if ref_file == str(dart_file) and ref_line == line:
                            continue
                        usage_count += 1

                if usage_count == 0:
                    try:
                        rel_path = self._get_relative_path(dart_file)
                    except Exception:
                        rel_path = str(dart_file)

                    violations.append(Violation(
                        file_path=rel_path,
                        rule_name='dart_unused_code',
                        severity=severity,
                        message=f"Unused {kind} '{name}' declared at line {line} - no references found in project"
                    ))

        violations = self._filter_violations_by_log_level(violations)

        if violations:
            print(f"\nDart unused code found {len(violations)} unused declaration(s) (checked {checked_symbols}/{total_symbols} symbols)")
        else:
            print(f"\nDart unused code: No unused declarations found (checked {checked_symbols}/{total_symbols} symbols)")

        if self.output_folder and violations:
            output_file = self.output_folder / 'dart_unused_code.csv'
            self._write_violations_csv(
                output_file, violations,
                ['file_path', 'line', 'declaration_type', 'name', 'severity'],
                lambda v: [
                    v.file_path,
                    self._extract_line(v.message),
                    self._extract_type(v.message),
                    self._extract_name(v.message),
                    v.severity.name
                ]
            )

        return violations

    @staticmethod
    def _extract_line(message: str) -> str:
        if 'at line ' in message:
            return message.split('at line ')[1].split(' ')[0]
        return ''

    @staticmethod
    def _extract_type(message: str) -> str:
        if message.startswith('Unused '):
            return message.split("'")[0].replace('Unused ', '').strip()
        return ''

    @staticmethod
    def _extract_name(message: str) -> str:
        if "'" in message:
            return message.split("'")[1]
        return ''
