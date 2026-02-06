# Dart Unused Code

## Overview

The Dart Unused Code analyzer finds unused classes, functions, enums, mixins, typedefs, and extensions across the project. It uses the dart-lsp-mcp Language Server Protocol integration for accurate, cross-file reference tracking.

## Supported Languages

- Dart
- Flutter (Dart-based projects)

## Dependencies

**dart-lsp-mcp** must be installed:

- Install from: https://github.com/BenjaminKobjolke/dart-lsp-mcp
- Provides LSP-based analysis via the Dart language server
- If not installed, the analyzer prints a warning and skips

The project must have a `pubspec.yaml` file.

## Configuration

```json
{
  "dart_unused_code": {
    "enabled": true,
    "analyze_path": "lib",
    "exclude_patterns": ["*.g.dart", "*.freezed.dart"],
    "ignore_names": ["main", "build"],
    "scan_test_references": true,
    "severity": "warning"
  }
}
```

### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enabled` | boolean | true | Enable/disable this analyzer |
| `analyze_path` | string | "lib" | Directory to scan (relative to project root) |
| `exclude_patterns` | list | ["*.g.dart", "*.freezed.dart"] | Glob patterns for files to exclude |
| `ignore_names` | list | ["main", "build"] | Symbol names to skip (entry points, framework methods) |
| `scan_test_references` | boolean | true | Include test files when checking for references |
| `severity` | string | "warning" | Severity level for violations |

## Output Format

### Console
```
Running dart unused code check...
Scanning 150 files for unused code...
Dart unused code found 8 unused declaration(s) (checked 245/250 symbols)
Report saved to: code_analysis_results/dart_unused_code.csv
```

### CSV Output (`dart_unused_code.csv`)

| Column | Description |
|--------|-------------|
| file_path | Relative path to the file |
| line | Line number of the declaration |
| declaration_type | Type: class, function, enum, mixin, typedef, extension |
| name | Name of the unused declaration |
| severity | WARNING (or configured severity) |

## Severity Levels

| Severity | Description |
|----------|-------------|
| WARNING | Declaration has no references anywhere in the project |

## Example Usage

```bash
# Basic usage
python main.py --language flutter --path ./lib --rules rules.json

# With output folder
python main.py --language flutter --path ./lib --rules rules.json --output ./reports
```

## Performance Notes

- The LSP server takes ~5-10s to start and analyze the project
- Each `find_references` call takes ~100-500ms
- For a 300-file project, this analyzer may take 5-15 minutes
- Best used for periodic deep scans, not on every commit
- Private symbols (starting with `_`) are automatically skipped

## Notes

- Executes once per analysis run (project-wide)
- Requires `pubspec.yaml` in the project root or parent directory
- Uses the real Dart language server for accurate cross-file reference tracking
- Private symbols (prefixed with `_`) are skipped since they are file-scoped
- Add framework methods (e.g., `build`, `initState`) to `ignore_names` to avoid false positives
- If dart-lsp-mcp is not installed, the analyzer gracefully skips with a warning
