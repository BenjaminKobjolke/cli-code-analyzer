# Dart Analyze

## Overview

The Dart Analyze analyzer performs static analysis on Dart and Flutter projects using the official Dart analyzer. It checks for type errors, style issues, best practice violations, and other problems in your Dart code.

## Supported Languages

- Dart
- Flutter (Dart-based projects)

## Dependencies

**Dart SDK** must be installed:

- Download from: https://dart.dev/get-dart
- Or install via Flutter SDK (includes Dart)

The project must have a `pubspec.yaml` file.

## Configuration

```json
{
  "dart_analyze": {
    "enabled": true
  }
}
```

### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enabled` | boolean | true | Enable/disable this analyzer |

Note: This analyzer uses Dart's built-in analysis options. Configure additional rules via `analysis_options.yaml` in your project.

## Output Format

### Console
```
Running dart analyze...
Dart analyze found 12 issue(s)
Dart analyze report saved to: code_analysis_results/dart_analyze.csv
```

### CSV Output (`dart_analyze.csv`)

| Column | Description |
|--------|-------------|
| file | Relative file path |
| line | Line number |
| column | Column number |
| severity | ERROR, WARNING, or INFO |
| code | Diagnostic code (e.g., unused_import, invalid_assignment) |
| message | Description of the issue |

## Severity Levels

Dart analyzer reports three severity levels:

| Severity | Description | Examples |
|----------|-------------|----------|
| ERROR | Compile-time errors, type errors | `invalid_assignment`, `undefined_identifier` |
| WARNING | Potential problems | `unused_local_variable`, `dead_code` |
| INFO | Style suggestions, hints | `prefer_const_constructors`, `unnecessary_this` |

## Example Usage

```bash
# Analyze Dart project
python main.py --language dart --path ./lib --rules rules.json

# Analyze Flutter project
python main.py --language flutter --path ./lib --rules rules.json

# Filter to errors only
python main.py --language dart --path ./lib --rules rules.json --verbosity error

# With output folder
python main.py --language dart --path ./lib --rules rules.json --output ./reports
```

## Project Configuration

Customize Dart analysis rules in your project's `analysis_options.yaml`:

```yaml
analyzer:
  errors:
    unused_import: warning
    dead_code: info
  exclude:
    - "**/*.g.dart"
    - "**/*.freezed.dart"

linter:
  rules:
    - prefer_const_constructors
    - avoid_print
    - prefer_single_quotes
```

## Notes

- Dart analyze executes once per analysis run (project-wide)
- Requires `pubspec.yaml` in the project root or parent directory
- Uses `dart analyze --fatal-infos --format=json` internally
- Combines stdout and stderr for complete diagnostic results
