"""
Dart missing dispose analyzer - detects controllers/subscriptions/timers created but never disposed.
Uses dart-lsp-mcp for accurate type analysis.
"""

from pathlib import Path

from models import LogLevel, Severity, Violation
from rules.base import BaseRule
from rules.dart_utils import collect_dart_files

# Optional dependency: dart-lsp-mcp
try:
    from dart_lsp_watcher.api import find_references, get_document_symbols, get_hover
    HAS_DART_LSP = True
except ImportError:
    HAS_DART_LSP = False


# Default disposable types and their required cleanup method
DEFAULT_DISPOSABLE_TYPES = {
    'AnimationController': 'dispose',
    'TextEditingController': 'dispose',
    'ScrollController': 'dispose',
    'TabController': 'dispose',
    'PageController': 'dispose',
    'FocusNode': 'dispose',
    'StreamSubscription': 'cancel',
    'StreamController': 'close',
    'Timer': 'cancel',
}


class DartMissingDisposeRule(BaseRule):
    """Detect controllers/subscriptions/timers created as fields but never disposed."""

    def __init__(self, config: dict, base_path: Path | None = None, output_folder: Path | None = None, log_level: LogLevel = LogLevel.ALL, max_errors: int | None = None, rules_file_path: str | None = None):
        super().__init__(config, base_path, log_level, max_errors, rules_file_path)
        self.output_folder = output_folder
        self._executed = False

    def check(self, _file_path: Path) -> list[Violation]:
        if self._executed:
            return []
        self._executed = True

        print("\nRunning dart missing dispose check...")

        if not HAS_DART_LSP:
            print("Warning: dart-lsp-mcp not installed. Skipping dart_missing_dispose analyzer.")
            print("Install from: D:\\GIT\\BenjaminKobjolke\\dart-lsp-mcp")
            return []

        project_root = self._find_pubspec()
        if not project_root:
            print("Warning: pubspec.yaml not found, skipping dart_missing_dispose")
            return []

        analyze_path = self.config.get('analyze_path', 'lib')
        analyze_dir = project_root / analyze_path
        if not analyze_dir.exists():
            print(f"Warning: analyze path '{analyze_dir}' does not exist")
            return []

        exclude_patterns = self.config.get('exclude_patterns', ['*.g.dart', '*.freezed.dart'])
        severity_str = self.config.get('severity', 'warning')
        severity = self._map_severity(severity_str)

        # Build disposable types map from config
        disposable_types = dict(DEFAULT_DISPOSABLE_TYPES)
        config_types = self.config.get('disposable_types', {})
        if config_types:
            disposable_types.update(config_types)
        custom_types = self.config.get('custom_disposable_types', {})
        if custom_types:
            disposable_types.update(custom_types)

        all_dart_files = collect_dart_files(analyze_dir, exclude_patterns)
        if not all_dart_files:
            print("No Dart files found to analyze")
            return []

        violations = []
        print(f"Scanning {len(all_dart_files)} files for missing dispose calls...")

        for dart_file in all_dart_files:
            file_violations = self._check_file_dispose(dart_file, disposable_types, severity)
            violations.extend(file_violations)

        violations = self._filter_violations_by_log_level(violations)

        if violations:
            print(f"\nDart missing dispose found {len(violations)} issue(s)")
        else:
            print("\nDart missing dispose: No issues found")

        if self.output_folder and violations:
            output_file = self.output_folder / 'dart_missing_dispose.csv'
            self._write_violations_csv(
                output_file, violations,
                ['file_path', 'line', 'class_name', 'field_name', 'field_type', 'required_cleanup_method', 'severity'],
                lambda v: self._parse_violation_data(v)
            )

        return violations

    def _check_file_dispose(self, dart_file: Path, disposable_types: dict, severity) -> list[Violation]:
        """Check a single file for fields that need disposal."""
        violations = []

        try:
            symbols = get_document_symbols(str(dart_file))
        except Exception as e:
            print(f"Warning: Could not get symbols for {dart_file}: {e}")
            return []

        if not symbols:
            return []

        # Find classes and their fields
        for symbol in symbols:
            if symbol.get('kind') != 'class':
                continue

            class_name = symbol.get('name', '')
            children = symbol.get('children', [])

            for child in children:
                if child.get('kind') != 'field':
                    continue

                field_name = child.get('name', '')
                field_line = child.get('line', 0)
                field_col = child.get('col', child.get('column', 0))

                # Get the actual type via hover
                try:
                    hover_info = get_hover(str(dart_file), field_line, field_col)
                except Exception:
                    continue

                if not hover_info:
                    continue

                hover_text = hover_info if isinstance(hover_info, str) else str(hover_info)

                # Check if the type matches any disposable type
                matched_type = None
                cleanup_method = None
                for type_name, method in disposable_types.items():
                    if type_name in hover_text:
                        matched_type = type_name
                        cleanup_method = method
                        break

                if not matched_type:
                    continue

                # Check if the field is properly disposed
                disposed = self._is_field_disposed(dart_file, field_name, field_line, field_col, cleanup_method)

                if not disposed:
                    try:
                        rel_path = self._get_relative_path(dart_file)
                    except Exception:
                        rel_path = str(dart_file)

                    violations.append(Violation(
                        file_path=rel_path,
                        rule_name='dart_missing_dispose',
                        severity=severity,
                        message=f"Field '{field_name}' of type {matched_type} in class {class_name} (line {field_line}) is never disposed"
                    ))

        return violations

    def _is_field_disposed(self, dart_file: Path, field_name: str, field_line: int, field_col: int, cleanup_method: str) -> bool:
        """Check if a field has its cleanup method called somewhere."""
        try:
            refs = find_references(str(dart_file), field_line, field_col)
        except Exception:
            return True  # If we can't check, assume it's ok

        if not refs:
            return False

        # Read file content to check if any reference includes .dispose()/.cancel()/.close()
        try:
            content = dart_file.read_text(encoding='utf-8', errors='replace')
            lines = content.split('\n')
        except Exception:
            return True

        for ref in refs:
            ref_line = ref.get('line', 0)
            if ref_line <= 0 or ref_line > len(lines):
                continue
            line_text = lines[ref_line - 1]
            # Check if this line contains field.dispose() or field.cancel() etc.
            if f'{field_name}.{cleanup_method}' in line_text:
                return True
            # Also check patterns like: field?.dispose(), field!.dispose()
            if f'{field_name}?.{cleanup_method}' in line_text or f'{field_name}!.{cleanup_method}' in line_text:
                return True

        return False

    def _parse_violation_data(self, v: Violation) -> list:
        """Parse violation message back into CSV columns."""
        msg = v.message
        field_name = ''
        field_type = ''
        class_name = ''
        line = ''
        cleanup = ''

        if "Field '" in msg:
            field_name = msg.split("'")[1]
        if 'of type ' in msg:
            field_type = msg.split('of type ')[1].split(' in ')[0]
        if 'in class ' in msg:
            class_name = msg.split('in class ')[1].split(' (')[0]
        if '(line ' in msg:
            line = msg.split('(line ')[1].rstrip(')')
            line = line.split(')')[0]

        # Determine cleanup method from type
        all_types = dict(DEFAULT_DISPOSABLE_TYPES)
        config_types = self.config.get('disposable_types', {})
        if config_types:
            all_types.update(config_types)
        custom_types = self.config.get('custom_disposable_types', {})
        if custom_types:
            all_types.update(custom_types)
        cleanup = all_types.get(field_type, 'dispose')

        return [v.file_path, line, class_name, field_name, field_type, cleanup, v.severity.name]
