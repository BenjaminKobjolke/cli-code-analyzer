# CRAP Score

## Overview

The CRAP (Change Risk Anti-Pattern) score combines cyclomatic complexity with test coverage into a single per-function metric:

```
CRAP(m) = complexity(m)^2 * (1 - coverage(m))^3 + complexity(m)
```

The score punishes complex code that lacks tests — exactly the code most likely to break on change. Two ways to lower CRAP for a function:

1. Reduce its cyclomatic complexity (split it up).
2. Add tests that cover its lines.

This analyzer is available in two languages:

- `dart_crap_score` — Flutter/Dart, using `dart_code_linter` complexity + `flutter test --coverage` LCOV.
- `python_crap_score` — Python, using `pyscn` complexity + `coverage.py` JSON output.

A companion `python_test_coverage` analyzer is also provided so Python projects get LCOV-equivalent coverage thresholds (Dart already has `dart_test_coverage`).

## Interpretation

| CRAP range | Risk level | Action |
|-----------:|------------|--------|
| `< 15` | Healthy | None required |
| `15 – 30` | Warning | Add tests or simplify when convenient |
| `> 30` | Critical | Refactor and/or test now |

## Dependencies

### Dart / Flutter
- Flutter SDK (`flutter test --coverage`)
- `dart_code_linter` in `dev_dependencies` of `pubspec.yaml`

### Python
- `pyscn` in `PATH` (install with `pipx install pyscn`)
- `coverage` and `pytest` in PATH (install with `pip install coverage pytest`)

## Configuration

### Dart

```json
{
  "dart_crap_score": {
    "enabled": false,
    "run_tests": true,
    "reuse_existing_coverage": true,
    "lcov_path": "coverage/lcov.info",
    "analyze_path": "lib",
    "test_timeout": 600,
    "warning": 15,
    "error": 30,
    "keep_report": false,
    "exclude_patterns": ["*.g.dart", "*.freezed.dart"],
    "exceptions": []
  }
}
```

### Python

```json
{
  "python_crap_score": {
    "enabled": false,
    "run_tests": true,
    "reuse_existing_coverage": true,
    "coverage_json_path": "coverage.json",
    "test_timeout": 600,
    "warning": 15,
    "error": 30,
    "exclude_patterns": ["**/__pycache__/**", "*.pyc", "**/.venv/**", "**/venv/**"],
    "exceptions": []
  },
  "python_test_coverage": {
    "enabled": false,
    "run_tests": true,
    "reuse_existing_coverage": true,
    "coverage_json_path": "coverage.json",
    "test_timeout": 600,
    "overall_coverage": {"warning": 60, "error": 40},
    "per_file_coverage": {"warning": 50, "error": 20},
    "exclude_patterns": ["**/__pycache__/**", "*.pyc", "**/.venv/**", "**/venv/**"]
  }
}
```

### Options (CRAP)

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enabled` | boolean | false | Enable/disable analyzer |
| `run_tests` | boolean | true | Run tests with coverage when no existing data |
| `reuse_existing_coverage` | boolean | true | Skip test run if coverage file already exists |
| `lcov_path` / `coverage_json_path` | string | `coverage/lcov.info` / `coverage.json` | Coverage file location |
| `analyze_path` (Dart) | string | `lib` | Dart source path passed to dart_code_linter |
| `test_timeout` | integer | 600 | Subprocess timeout in seconds |
| `warning` | number | 15 | CRAP warning threshold |
| `error` | number | 30 | CRAP error threshold |
| `keep_report` (Dart) | boolean | false | Keep temporary DCL report dir |
| `exclude_patterns` | list | language defaults | Glob patterns to skip |
| `exceptions` | list | `[]` | Per-file threshold overrides |

### Per-file exceptions

Matches the existing rule pattern (see `pyscn_analyze`, `dart_code_linter`):

```json
"exceptions": [
  {"file": "lib/legacy/old_engine.dart", "warning": 30, "error": 60},
  {"file": "**/generated_*.py", "warning": 0, "error": 0}
]
```

## Output Format

### Console

```
Running dart_crap_score check...
Using existing coverage: /proj/coverage/lcov.info
dart_crap_score found 7 issue(s)
Report saved to: reports/dart_crap_score.csv
```

### CSV (`dart_crap_score.csv` / `python_crap_score.csv`)

| Column | Description |
|--------|-------------|
| file | Relative path |
| line | First line of the function (1-based) |
| function | Function name |
| complexity | Cyclomatic complexity |
| coverage | Coverage percentage of executable lines in the function |
| crap | CRAP score |
| severity | `ERROR` or `WARNING` |

## How coverage is mapped to functions

1. Run the complexity tool to get per-function `(file, name, first_line, last_line, complexity)`.
2. Parse the coverage report into `{file: {line_no: hits}}`.
3. For each function, count executable lines (lines present in the coverage report) inside its line range, and how many were hit.
4. Compute CRAP from `complexity` and `covered / total`.

Functions whose line range contains no executable lines (abstract methods, getters that compile away, generated code) are skipped.

## Fallback (Dart only)

If the installed `dart_code_linter` version does not expose `firstLine`/`lastLine` (or `location.start.line` / `location.end.line`) for functions, the analyzer falls back to a **file-level** CRAP using the file's cyclomatic-complexity metric and whole-file coverage. The console logs this once.

## Example Usage

```bash
# Dart / Flutter — opt-in
python main.py --language flutter --path ./lib --rules rules.json --output ./reports

# Python — opt-in, needs coverage + pytest installed
python main.py --language python --path ./src --rules rules.json --output ./reports
```

To isolate the CRAP analyzer while debugging, disable other analyzers for the same language in your local `rules.json` copy.

## Notes

- Disabled by default — running tests for coverage can be slow.
- Set `reuse_existing_coverage: true` (default) and run `flutter test --coverage` / `coverage run -m pytest && coverage json` once; then re-run the analyzer cheaply.
- Functions with no executable lines are silently skipped.
- See also: [`dart_code_linter.md`](dart_code_linter.md), [`dart_test_coverage.md`](dart_test_coverage.md), [`pyscn_analyze.md`](pyscn_analyze.md).
