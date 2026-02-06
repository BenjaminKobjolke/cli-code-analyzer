# Dart Missing Dispose

## Overview

The Dart Missing Dispose analyzer detects controllers, subscriptions, and timers that are created as class fields but never have their cleanup method called (`.dispose()`, `.cancel()`, or `.close()`). Missing cleanup calls are a common source of memory leaks in Flutter applications.

## Supported Languages

- Dart
- Flutter (Dart-based projects)

## Dependencies

**dart-lsp-mcp** must be installed:

- Install from: https://github.com/BenjaminKobjolke/dart-lsp-mcp
- Provides LSP-based type analysis and reference tracking
- If not installed, the analyzer prints a warning and skips

The project must have a `pubspec.yaml` file.

## Configuration

```json
{
  "dart_missing_dispose": {
    "enabled": true,
    "analyze_path": "lib",
    "exclude_patterns": ["*.g.dart", "*.freezed.dart"],
    "severity": "warning",
    "disposable_types": {
      "AnimationController": "dispose",
      "TextEditingController": "dispose",
      "ScrollController": "dispose",
      "TabController": "dispose",
      "PageController": "dispose",
      "FocusNode": "dispose",
      "StreamSubscription": "cancel",
      "StreamController": "close",
      "Timer": "cancel"
    },
    "custom_disposable_types": {}
  }
}
```

### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enabled` | boolean | true | Enable/disable this analyzer |
| `analyze_path` | string | "lib" | Directory to scan (relative to project root) |
| `exclude_patterns` | list | ["*.g.dart", "*.freezed.dart"] | Glob patterns for files to exclude |
| `severity` | string | "warning" | Severity level for violations |
| `disposable_types` | object | (see above) | Map of type name to required cleanup method |
| `custom_disposable_types` | object | {} | Additional custom types to check |

### Disposable Types

| Type | Cleanup Method |
|------|---------------|
| AnimationController | dispose() |
| TextEditingController | dispose() |
| ScrollController | dispose() |
| TabController | dispose() |
| PageController | dispose() |
| FocusNode | dispose() |
| StreamSubscription | cancel() |
| StreamController | close() |
| Timer | cancel() |

## Output Format

### Console
```
Running dart missing dispose check...
Scanning 150 files for missing dispose calls...
Dart missing dispose found 3 issue(s)
Report saved to: code_analysis_results/dart_missing_dispose.csv
```

### CSV Output (`dart_missing_dispose.csv`)

| Column | Description |
|--------|-------------|
| file_path | Relative path to the file |
| line | Line number of the field declaration |
| class_name | Name of the class containing the field |
| field_name | Name of the undisposed field |
| field_type | Type of the field (e.g., TextEditingController) |
| required_cleanup_method | The method that should be called (dispose/cancel/close) |
| severity | WARNING (or configured severity) |

## Severity Levels

| Severity | Description |
|----------|-------------|
| WARNING | Field of disposable type is never cleaned up |

## Example Usage

```bash
# Basic usage
python main.py --language flutter --path ./lib --rules rules.json

# With output folder
python main.py --language flutter --path ./lib --rules rules.json --output ./reports
```

## Adding Custom Disposable Types

Add your own types via `custom_disposable_types`:

```json
{
  "dart_missing_dispose": {
    "enabled": true,
    "custom_disposable_types": {
      "MyCustomController": "dispose",
      "DatabaseConnection": "close"
    }
  }
}
```

## Performance Notes

- Uses dart-lsp-mcp for accurate type information via hover
- Each file requires multiple LSP calls (symbols, hover, references)
- For large projects, this may take several minutes
- Best used for periodic deep scans

## Notes

- Executes once per analysis run (project-wide)
- Requires `pubspec.yaml` in the project root or parent directory
- Uses LSP hover to determine actual field types (handles generics, late fields, etc.)
- Checks for `.dispose()`, `.cancel()`, and `.close()` patterns including null-safe variants (`?.dispose()`, `!.dispose()`)
- If dart-lsp-mcp is not installed, the analyzer gracefully skips with a warning
