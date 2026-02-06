# Dart Unused Files

## Overview

The Dart Unused Files analyzer detects `.dart` files that are never imported or exported by any other file in the project. It builds an import graph starting from configured entry points (e.g., `main.dart`) and reports files that are unreachable, indicating dead code at the file level.

## Supported Languages

- Dart
- Flutter (Dart-based projects)

## Dependencies

No external tools required. This analyzer uses pure Python import-graph analysis.

The project must have a `pubspec.yaml` file.

## Configuration

```json
{
  "dart_unused_files": {
    "enabled": true,
    "analyze_path": "lib",
    "entry_points": ["lib/main.dart"],
    "exclude_patterns": ["*.g.dart", "*.freezed.dart"],
    "include_test_imports": false
  }
}
```

### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enabled` | boolean | true | Enable/disable this analyzer |
| `analyze_path` | string | "lib" | Directory to scan for unused files (relative to project root) |
| `entry_points` | list | ["lib/main.dart"] | Entry point files to start the import graph traversal |
| `exclude_patterns` | list | ["*.g.dart", "*.freezed.dart"] | Glob patterns for files to exclude |
| `include_test_imports` | boolean | false | Also scan test/ directory for imports (marks files used by tests as reachable) |

## Output Format

### Console
```
Running dart unused files check...
Dart unused files found 3 unused file(s)
Report saved to: code_analysis_results/dart_unused_files.csv
```

### CSV Output (`dart_unused_files.csv`)

| Column | Description |
|--------|-------------|
| file_path | Relative path to the unused file |
| severity | WARNING |
| message | Description of the issue |

## Severity Levels

| Severity | Description |
|----------|-------------|
| WARNING | File is never imported by any other file in the project |

## Example Usage

```bash
# Basic usage
python main.py --language flutter --path ./lib --rules rules.json

# With output folder
python main.py --language flutter --path ./lib --rules rules.json --output ./reports
```

## Notes

- Executes once per analysis run (project-wide)
- Requires `pubspec.yaml` in the project root or parent directory
- Builds a complete import graph using BFS from entry points
- Resolves both `package:` imports and relative imports
- Generated files (`.g.dart`, `.freezed.dart`) are excluded by default
- Use `include_test_imports: true` if you want files only used in tests to not be flagged
