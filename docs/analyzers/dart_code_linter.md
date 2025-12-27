# Dart Code Linter (Code Metrics)

## Overview

The Dart Code Linter analyzer measures code complexity metrics and maintainability indices for Dart/Flutter projects. It helps identify overly complex code, large classes, deeply nested functions, and other maintainability issues using the `dart_code_linter` package.

## Supported Languages

- Dart
- Flutter (Dart-based projects)

## Dependencies

1. **Dart SDK** must be installed
2. **dart_code_linter** package must be in `dev_dependencies`:

```yaml
dev_dependencies:
  dart_code_linter: ^1.0.0
```

Or enable `auto_install` in configuration.

## Configuration

```json
{
  "dart_code_linter": {
    "enabled": true,
    "auto_install": false,
    "analyze_path": "lib",
    "keep_report": false,
    "metrics": {
      "cyclomatic-complexity": {
        "warning": 10,
        "error": 15
      },
      "lines-of-code": {
        "warning": 0,
        "error": 0
      },
      "number-of-methods": {
        "warning": 10,
        "error": 20,
        "exceptions": [
          {
            "file": "services/preferences_service.dart",
            "warning": 70,
            "error": 80
          }
        ]
      },
      "technical-debt": {
        "warning": 10,
        "error": 50
      },
      "maintainability-index": {
        "warning": 40,
        "error": 20
      },
      "maximum-nesting-level": {
        "warning": 3,
        "error": 5
      },
      "halstead-volume": {
        "warning": 800,
        "error": 1200
      },
      "source-lines-of-code": {
        "warning": 0,
        "error": 0
      }
    }
  }
}
```

### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enabled` | boolean | true | Enable/disable this analyzer |
| `auto_install` | boolean | false | Auto-install dart_code_linter if missing |
| `analyze_path` | string | "lib" | Directory to analyze |
| `keep_report` | boolean | false | Keep intermediate JSON report |
| `metrics` | object | {} | Metric threshold configurations |

### Metric Configuration

Each metric supports:
- `warning`: Threshold for warning severity
- `error`: Threshold for error severity
- `exceptions`: File-specific threshold overrides

Set both `warning` and `error` to `0` to disable a metric.

## Supported Metrics

| Metric | Description | Default Behavior |
|--------|-------------|------------------|
| `cyclomatic-complexity` | Number of independent code paths | Higher = worse |
| `lines-of-code` | Total lines per function | Higher = worse |
| `number-of-methods` | Methods per class | Higher = worse |
| `technical-debt` | Estimated maintenance cost (minutes) | Higher = worse |
| `maintainability-index` | Code maintainability score (0-100) | **Lower = worse** |
| `maximum-nesting-level` | Deepest control structure nesting | Higher = worse |
| `halstead-volume` | Code volume based on operators/operands | Higher = worse |
| `source-lines-of-code` | Physical lines excluding comments | Higher = worse |
| `weight-of-class` | Class complexity weight | **Lower = worse** |

### Inverse Metrics

Some metrics are "inverse" - lower values are worse:
- `maintainability-index`: Score of 100 is best, 0 is worst
- `weight-of-class`: Higher cohesion is better

For inverse metrics, the error threshold should be **lower** than the warning threshold:
```json
{
  "maintainability-index": {
    "warning": 40,
    "error": 20
  }
}
```

### File-Specific Exceptions

Override thresholds for specific files:

```json
{
  "number-of-methods": {
    "warning": 10,
    "error": 20,
    "exceptions": [
      {
        "file": "services/large_service.dart",
        "warning": 50,
        "error": 60
      },
      {
        "file": "**/generated/*.dart",
        "warning": 100,
        "error": 150
      }
    ]
  }
}
```

## Output Format

### Console
```
Checking dart_code_linter metrics...
Running dart_code_linter analysis on 'lib'...
Metrics report saved to: code_analysis_results/code_analysis/report.json

Dart Code Linter found 8 metric violation(s)
Dart Code Linter report saved to: code_analysis_results/dart_code_linter.csv
Cleaned up: code_analysis_results/code_analysis
```

### CSV Output (`dart_code_linter.csv`)

| Column | Description |
|--------|-------------|
| file_path | Relative file path |
| metric | Metric name |
| value | Actual metric value |
| threshold | Threshold that was exceeded |
| severity | WARNING or ERROR |
| context | Scope (file, class name, function name) |

## Severity Levels

- **WARNING**: Metric exceeds warning threshold
- **ERROR**: Metric exceeds error threshold

## Example Usage

```bash
# Analyze Dart project metrics
python main.py --language dart --path ./lib --rules rules.json

# Auto-install dart_code_linter if missing
# (requires auto_install: true in config)
python main.py --language dart --path ./lib --rules rules.json

# Keep intermediate report for debugging
# (requires keep_report: true in config)
python main.py --language dart --path ./lib --rules rules.json --output ./reports
```

## Notes

- Analyzes metrics at file, class, and function levels
- Requires `pubspec.yaml` with dart_code_linter in dev_dependencies
- Generates intermediate `report.json` (cleaned up by default)
- Uses `dart run dart_code_linter:metrics analyze` internally
