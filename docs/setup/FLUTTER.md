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
| `dart_unused_files` | Finds .dart files never imported by any other file |
| `dart_unused_dependencies` | Finds packages in pubspec.yaml never imported in code |
| `dart_import_rules` | Enforces architecture layer boundaries |
| `dart_unused_code` | Finds unused classes, functions, enums (requires dart-lsp-mcp) |
| `dart_missing_dispose` | Detects controllers/subscriptions never disposed (requires dart-lsp-mcp) |
| `dart_test_coverage` | Checks test coverage against thresholds (disabled by default) |

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
  },
  "dart_unused_files": {
    "enabled": true,
    "analyze_path": "lib",
    "entry_points": ["lib/main.dart"],
    "exclude_patterns": ["*.g.dart", "*.freezed.dart"],
    "include_test_imports": false
  },
  "dart_unused_dependencies": {
    "enabled": true,
    "check_dev_dependencies": true,
    "severity": "warning",
    "ignore_packages": ["flutter", "flutter_localizations", "flutter_test", "flutter_lints", "dart_code_linter", "build_runner", "json_serializable", "freezed", "freezed_annotation"]
  },
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
  },
  "dart_unused_code": {
    "enabled": true,
    "analyze_path": "lib",
    "exclude_patterns": ["*.g.dart", "*.freezed.dart"],
    "ignore_names": ["main", "build"],
    "scan_test_references": true,
    "severity": "warning"
  },
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
  },
  "dart_test_coverage": {
    "enabled": false,
    "run_tests": true,
    "lcov_path": "coverage/lcov.info",
    "test_timeout": 600,
    "overall_coverage": {
      "warning": 60,
      "error": 40
    },
    "per_file_coverage": {
      "warning": 50,
      "error": 20
    },
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

Create a `tools` subfolder in your project and place the batch files there.

> **Note:** Do not add `pause` at the end of batch files. These scripts are designed to be called by other tools and `pause` would block execution.

Create `tools/analyze_code.bat`:

```batch
@echo off
d:
cd "d:\path\to\cli-code-analyzer"

call venv\Scripts\python.exe main.py --language flutter --path "D:\path\to\your\project\lib" --verbosity minimal --output "D:\path\to\your\project\code_analysis_results" --maxamountoferrors 50 --rules "D:\path\to\your\project\code_analysis_rules.json"

cd %~dp0..
```

## CLI Options

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--language` | `-l` | Set to `flutter` | Required |
| `--path` | `-p` | Path to `lib` folder or file | Required |
| `--rules` | `-r` | Path to rules JSON file | `rules.json` |
| `--verbosity` | `-v` | Output level: `minimal`, `normal`, `verbose` | `normal` |
| `--output` | `-o` | Folder for CSV/TXT reports | None (console) |
| `--loglevel` | `-L` | Filter: `error`, `warning`, `all` | `all` |
| `--maxamountoferrors` | `-m` | Limit violations in CSV | Unlimited |
| `--list-files` | `-f` | List all analyzed file paths after analysis | Off |

## Output Files

When using `--output`, these files are generated:

| File | Content |
|------|---------|
| `line_count_report.csv` | File line counts |
| `duplicate_code.csv` | PMD duplicate code results |
| `dart_analyze.csv` | Dart analyzer results |
| `dart_code_linter.csv` | Code metrics violations |
| `flutter_analyze.csv` | Flutter analyzer results |
| `dart_unused_files.csv` | Unused file detection results |
| `dart_unused_dependencies.csv` | Unused dependency detection results |
| `dart_import_rules.csv` | Architecture violation results |
| `dart_unused_code.csv` | Unused code detection results |
| `dart_missing_dispose.csv` | Missing dispose detection results |
| `dart_test_coverage.csv` | Test coverage results |

## Architecture & Maintainability Analyzers

In addition to the core syntax and metrics analyzers, cli-code-analyzer provides analyzers focused on structural quality:

| Analyzer | Category | External Tool |
|----------|----------|--------------|
| `dart_unused_files` | Dead code | None |
| `dart_unused_dependencies` | Dependency hygiene | None |
| `dart_import_rules` | Architecture enforcement | None |
| `dart_unused_code` | Dead code (symbol-level) | dart-lsp-mcp |
| `dart_missing_dispose` | Resource management | dart-lsp-mcp |
| `dart_test_coverage` | Test coverage | Flutter SDK |

**Pure Python analyzers** (`dart_unused_files`, `dart_unused_dependencies`, `dart_import_rules`) require no external tools and run quickly. Enable these for every analysis run.

**LSP-based analyzers** (`dart_unused_code`, `dart_missing_dispose`) require [dart-lsp-mcp](https://github.com/BenjaminKobjolke/dart-lsp-mcp) and use the Dart Language Server for accurate cross-file analysis. These are more thorough but slower (5-15 minutes for large projects). Best used for periodic deep scans.

**Test coverage** (`dart_test_coverage`) is disabled by default since it runs your test suite. Enable it when you want to enforce coverage thresholds.

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
