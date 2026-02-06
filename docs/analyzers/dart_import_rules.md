# Dart Import Rules

## Overview

The Dart Import Rules analyzer enforces architecture layer boundaries via configurable forbidden import rules. This helps maintain clean architecture by preventing, for example, domain layer code from depending on presentation or data layers.

## Supported Languages

- Dart
- Flutter (Dart-based projects)

## Dependencies

No external tools required. This analyzer uses pure Python import analysis.

The project must have a `pubspec.yaml` file.

## Configuration

```json
{
  "dart_import_rules": {
    "enabled": true,
    "analyze_path": "lib",
    "exclude_patterns": ["*.g.dart", "*.freezed.dart"],
    "forbidden_imports": [
      {
        "from": "domain/**",
        "cannot_import": ["presentation/**", "data/**", "package:flutter/**"],
        "severity": "error",
        "message": "Domain layer must not depend on presentation or data layers"
      },
      {
        "from": "data/**",
        "cannot_import": ["presentation/**"],
        "severity": "warning",
        "message": "Data layer should not depend on presentation layer"
      }
    ]
  }
}
```

### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enabled` | boolean | true | Enable/disable this analyzer |
| `analyze_path` | string | "lib" | Directory to scan (relative to project root) |
| `exclude_patterns` | list | ["*.g.dart", "*.freezed.dart"] | Glob patterns for files to exclude |
| `forbidden_imports` | list | [] | List of import rules to enforce |

### Forbidden Import Rule Format

| Field | Type | Description |
|-------|------|-------------|
| `from` | string | Glob pattern matching source files (relative to analyze_path) |
| `cannot_import` | list | Glob patterns for forbidden import targets (relative paths or `package:` URIs) |
| `severity` | string | "error" or "warning" |
| `message` | string | Custom message explaining the rule |

## Output Format

### Console
```
Running dart import rules check...
Dart import rules found 5 violation(s)
Report saved to: code_analysis_results/dart_import_rules.csv
```

### CSV Output (`dart_import_rules.csv`)

| Column | Description |
|--------|-------------|
| file_path | Relative path to the file with the violation |
| line | Line number of the import statement |
| import_statement | The forbidden import URI |
| violated_rule | The rule message that was violated |
| severity | ERROR or WARNING |

## Severity Levels

| Severity | Description |
|----------|-------------|
| ERROR | Critical architecture violation (e.g., domain importing presentation) |
| WARNING | Non-critical architecture concern (e.g., data importing presentation) |

## Example Usage

```bash
# Basic usage
python main.py --language flutter --path ./lib --rules rules.json

# Filter to errors only
python main.py --language flutter --path ./lib --rules rules.json --loglevel error
```

## Common Architecture Patterns

### Clean Architecture
```json
"forbidden_imports": [
  {"from": "domain/**", "cannot_import": ["presentation/**", "data/**", "package:flutter/**"], "severity": "error", "message": "Domain layer must be independent"},
  {"from": "data/**", "cannot_import": ["presentation/**"], "severity": "warning", "message": "Data layer should not depend on presentation"}
]
```

### Feature-First Architecture
```json
"forbidden_imports": [
  {"from": "features/auth/**", "cannot_import": ["features/settings/**"], "severity": "warning", "message": "Auth feature should not depend on settings feature"},
  {"from": "core/**", "cannot_import": ["features/**"], "severity": "error", "message": "Core must not depend on features"}
]
```

## Notes

- Executes once per analysis run (project-wide)
- Requires `pubspec.yaml` in the project root or parent directory
- Patterns use glob syntax relative to the `analyze_path` directory
- Both `package:` URIs and relative imports are checked
- Configure rules to match your project's architecture pattern
