# Dart Test Coverage

## Overview

The Dart Test Coverage analyzer runs Flutter tests with coverage enabled and checks the results against configurable thresholds. It supports both overall project coverage and per-file coverage thresholds.

## Supported Languages

- Flutter (Dart-based projects)

## Dependencies

**Flutter SDK** must be installed:

- Download from: https://docs.flutter.dev/get-started/install
- Uses `flutter test --coverage` internally

The project must have a `pubspec.yaml` file and a `test/` directory.

## Configuration

```json
{
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

### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enabled` | boolean | false | Enable/disable this analyzer (disabled by default) |
| `run_tests` | boolean | true | Run `flutter test --coverage` before checking |
| `lcov_path` | string | "coverage/lcov.info" | Path to LCOV coverage file (relative to project root) |
| `test_timeout` | integer | 600 | Timeout in seconds for running tests |
| `overall_coverage` | object | {warning: 60, error: 40} | Overall project coverage thresholds (%) |
| `per_file_coverage` | object | {warning: 50, error: 20} | Per-file coverage thresholds (%) |
| `exclude_patterns` | list | ["*.g.dart", "*.freezed.dart"] | Glob patterns for files to exclude from coverage |

## Output Format

### Console
```
Running dart test coverage check...
Running flutter test --coverage (this may take a while)...
Dart test coverage found 5 issue(s) (overall: 45.2%)
Report saved to: code_analysis_results/dart_test_coverage.csv
```

### CSV Output (`dart_test_coverage.csv`)

| Column | Description |
|--------|-------------|
| file_path | Relative path to the file (or "project" for overall) |
| total_lines | Total instrumentable lines |
| covered_lines | Number of lines covered by tests |
| coverage_pct | Coverage percentage |
| threshold | The threshold that was violated |
| severity | ERROR or WARNING |

## Severity Levels

| Severity | Description | Default Threshold |
|----------|-------------|-------------------|
| ERROR | Coverage below error threshold | Overall: 40%, Per-file: 20% |
| WARNING | Coverage below warning threshold | Overall: 60%, Per-file: 50% |

## Example Usage

```bash
# Run with test coverage (opt-in, disabled by default)
python main.py --language flutter --path ./lib --rules rules.json

# With output folder
python main.py --language flutter --path ./lib --rules rules.json --output ./reports

# Skip running tests, use existing coverage data
# Set "run_tests": false in rules.json
```

## Notes

- Disabled by default since running tests can be slow
- Set `run_tests: false` to skip test execution and use an existing `lcov.info` file
- Parses standard LCOV format coverage data
- Executes once per analysis run (project-wide)
- Requires `pubspec.yaml` in the project root or parent directory
- The `test_timeout` setting prevents indefinite hanging on large test suites
- Generated files are excluded from coverage checks by default
