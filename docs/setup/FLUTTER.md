# Flutter Project Setup

This guide explains how to set up cli-code-analyzer for Flutter/Dart projects.

## Prerequisites

- Flutter SDK (https://docs.flutter.dev/get-started/install)
- Dart SDK (included with Flutter)
- PMD (optional, for duplicate code detection)
- dart_code_linter package (optional, for code metrics)

## Quick Start

```bash
python main.py --language flutter --path /path/to/your/project/lib
```

## Available Rules

| Rule | Description |
|------|-------------|
| `max_lines_per_file` | Checks file length against warning/error thresholds |
| `pmd_duplicates` | Detects duplicate code blocks (requires PMD) |
| `dart_analyze` | Runs `dart analyze` for static analysis |
| `dart_code_linter` | Advanced code metrics (complexity, maintainability, etc.) |
| `flutter_analyze` | Runs `flutter analyze` for Flutter-specific issues |

## Example Configuration

Create a `code_analysis_rules.json` file in your project:

```json
{
  "log_level": "all",
  "max_lines_per_file": {
    "enabled": true,
    "warning": 300,
    "error": 500
  },
  "pmd_duplicates": {
    "enabled": true,
    "minimum_tokens": 100,
    "exclude_patterns": {
      "dart": ["*.g.dart", "*.freezed.dart"]
    }
  },
  "dart_analyze": {
    "enabled": true
  },
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
      "number-of-methods": {
        "warning": 10,
        "error": 20
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
      }
    }
  },
  "flutter_analyze": {
    "enabled": false,
    "exclude_patterns": ["*.g.dart", "*.freezed.dart"]
  }
}
```

## Exclusion Patterns

Common patterns to exclude from analysis:

| Pattern | Purpose |
|---------|---------|
| `*.g.dart` | Generated code (json_serializable, etc.) |
| `*.freezed.dart` | Freezed generated code |
| `*.mocks.dart` | Mockito generated mocks |
| `*.gr.dart` | Auto_route generated code |

## Dart Code Linter Metrics

| Metric | Description | Recommended Warning/Error |
|--------|-------------|---------------------------|
| `cyclomatic-complexity` | Code path complexity | 10 / 15 |
| `lines-of-code` | Total lines (0 = disabled) | 0 / 0 |
| `source-lines-of-code` | Non-comment lines (0 = disabled) | 0 / 0 |
| `number-of-methods` | Methods per class | 10 / 20 |
| `technical-debt` | Estimated debt in minutes | 10 / 50 |
| `maintainability-index` | Lower = worse (inverted!) | 40 / 20 |
| `maximum-nesting-level` | Nested blocks depth | 3 / 5 |
| `halstead-volume` | Code complexity measure | 800 / 1200 |

### File-Specific Exceptions

Override thresholds for specific files:

```json
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
}
```

## Example Batch File (Windows)

Create `analyze_code.bat` in your project root:

```batch
@echo off
d:
cd "d:\path\to\cli-code-analyzer"

call venv\Scripts\python.exe main.py --language flutter --path "D:\path\to\your\project\lib" --verbosity minimal --output "D:\path\to\your\project\code_analysis_results" --maxamountoferrors 50 --rules "D:\path\to\your\project\code_analysis_rules.json"

cd %~dp0
pause
```

## CLI Options

| Option | Description | Default |
|--------|-------------|---------|
| `--language` | Set to `flutter` | Required |
| `--path` | Path to `lib` folder or file | Required |
| `--rules` | Path to rules JSON file | `rules.json` |
| `--verbosity` | Output level: `minimal`, `normal`, `verbose` | `normal` |
| `--output` | Folder for CSV/TXT reports | None (console) |
| `--loglevel` | Filter: `error`, `warning`, `all` | `all` |
| `--maxamountoferrors` | Limit violations in CSV | Unlimited |

## Output Files

When using `--output`, these files are generated:

| File | Content |
|------|---------|
| `line_count_report.csv` | File line counts |
| `duplicate_code.csv` | PMD duplicate code results |
| `dart_analyze.csv` | Dart analyzer results |
| `dart_code_linter.csv` | Code metrics violations |
| `flutter_analyze.csv` | Flutter analyzer results |

## Troubleshooting

### Dart/Flutter not found
If you get a path error:
1. Ensure Flutter/Dart is in your PATH
2. Or edit `settings.ini` to set `dart_path` and `flutter_path`

### dart_code_linter not installed
Set `"auto_install": true` in the config, or manually install:
```bash
dart pub global activate dart_code_linter
```

### Generated files causing issues
Add exclusion patterns for generated files:
```json
"exclude_patterns": {
  "dart": ["*.g.dart", "*.freezed.dart", "*.mocks.dart"]
}
```
