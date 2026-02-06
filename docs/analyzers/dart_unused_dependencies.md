# Dart Unused Dependencies

## Overview

The Dart Unused Dependencies analyzer finds packages listed in `pubspec.yaml` that are never imported anywhere in the codebase. This helps keep dependencies lean and reduces build times and binary size.

## Supported Languages

- Dart
- Flutter (Dart-based projects)

## Dependencies

No external tools required. This analyzer uses pure Python analysis of `pubspec.yaml` and import statements.

The project must have a `pubspec.yaml` file.

## Configuration

```json
{
  "dart_unused_dependencies": {
    "enabled": true,
    "check_dev_dependencies": true,
    "severity": "warning",
    "ignore_packages": ["flutter", "flutter_localizations", "flutter_test", "flutter_lints", "dart_code_linter", "build_runner", "json_serializable", "freezed", "freezed_annotation"],
    "scan_paths": {
      "dependencies": ["lib"],
      "dev_dependencies": ["test", "integration_test"]
    }
  }
}
```

### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enabled` | boolean | true | Enable/disable this analyzer |
| `check_dev_dependencies` | boolean | true | Also check dev_dependencies for usage |
| `severity` | string | "warning" | Severity level for violations |
| `ignore_packages` | list | (see above) | Packages to skip (framework packages, build tools, etc.) |
| `scan_paths` | object | (see above) | Which directories to scan for each dependency type |

## Output Format

### Console
```
Running dart unused dependencies check...
Dart unused dependencies found 2 unused package(s)
Report saved to: code_analysis_results/dart_unused_dependencies.csv
```

### CSV Output (`dart_unused_dependencies.csv`)

| Column | Description |
|--------|-------------|
| package_name | Name of the unused package |
| dependency_type | "dependencies" or "dev_dependencies" |
| severity | WARNING (or configured severity) |
| message | Description of the issue |

## Severity Levels

| Severity | Description |
|----------|-------------|
| WARNING | Package is listed in pubspec.yaml but never imported |

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
- Scans for `package:<name>/` import patterns in all `.dart` files
- The default `ignore_packages` list covers common framework and build-tool packages that may not have direct imports
- Add any packages used via reflection, platform channels, or build scripts to `ignore_packages`
- Dev dependencies are checked against `test/` and `integration_test/` directories by default
