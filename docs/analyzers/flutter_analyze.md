# Flutter Analyze

## Overview

The Flutter Analyze analyzer performs static analysis on Flutter projects using the Flutter SDK's analyze command. It checks for Flutter-specific issues, widget best practices, and Dart code problems in your Flutter application.

## Supported Languages

Flutter (Dart-based Flutter projects only).

## Dependencies

**Flutter SDK** must be installed:

- Download from: https://docs.flutter.dev/get-started/install
- The project must have Flutter as a dependency in `pubspec.yaml`

## Configuration

```json
{
  "flutter_analyze": {
    "enabled": true,
    "exclude_patterns": [
      "*.g.dart",
      "*.freezed.dart"
    ]
  }
}
```

### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enabled` | boolean | false | Enable/disable this analyzer |
| `exclude_patterns` | array | [] | File patterns to exclude |

Note: This analyzer is disabled by default. Enable it explicitly for Flutter projects.

## Output Format

### Console
```
Running flutter analyze...
Flutter analyze found 7 issue(s)
Flutter analyze report saved to: code_analysis_results/flutter_analyze.csv
```

### CSV Output (`flutter_analyze.csv`)

| Column | Description |
|--------|-------------|
| file | Relative file path |
| line | Line number |
| column | Column number |
| severity | ERROR, WARNING, or INFO |
| code | Diagnostic code (e.g., unused_import, prefer_const_constructors) |
| message | Description of the issue |

## Severity Levels

| Severity | Description | Examples |
|----------|-------------|----------|
| ERROR | Compile-time errors | Type mismatches, undefined widgets |
| WARNING | Potential problems | Unused variables, deprecated APIs |
| INFO | Style and best practices | Const suggestions, naming conventions |

## Example Usage

```bash
# Analyze Flutter project
python main.py --language flutter --path ./lib --rules rules.json

# Filter to warnings and errors only
python main.py --language flutter --path ./lib --rules rules.json --verbosity warning

# With output folder
python main.py --language flutter --path ./lib --rules rules.json --output ./reports
```

## Project Configuration

Customize Flutter analysis in your project's `analysis_options.yaml`:

```yaml
include: package:flutter_lints/flutter.yaml

analyzer:
  exclude:
    - "**/*.g.dart"
    - "**/*.freezed.dart"
  errors:
    invalid_annotation_target: ignore

linter:
  rules:
    - prefer_const_constructors
    - prefer_const_literals_to_create_immutables
    - avoid_print
    - use_key_in_widget_constructors
```

## Flutter vs Dart Analyze

| Feature | Flutter Analyze | Dart Analyze |
|---------|-----------------|--------------|
| SDK Required | Flutter SDK | Dart SDK |
| Project Type | Flutter only | Any Dart project |
| Widget Rules | Yes | No |
| Platform Checks | Yes | No |

Use **Flutter Analyze** for Flutter projects to get Flutter-specific checks and widget best practices.

## Notes

- Executes once per analysis run (project-wide)
- Verifies Flutter dependency exists in pubspec.yaml before running
- Uses `flutter analyze` command internally
- Handles multi-line diagnostic messages
- Requires Flutter SDK in PATH or configured path
