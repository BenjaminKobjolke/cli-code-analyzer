# Arduino C++ Project Setup

This guide explains how to analyze Arduino sketches and C/C++ source files with cli-code-analyzer.

## Prerequisites

- Python and cli-code-analyzer installed.
- PMD is optional and required only for duplicate-code and similar-code analysis. Install PMD or configure its path in `settings.ini`.

No Arduino SDK or compiler is required: this guide configures source-level checks and does not compile firmware.

## Quick Start

```bash
python main.py --language cpp --path /path/to/your/project
# Arduino aliases:
python main.py --language arduino --path /path/to/your/project
python main.py --language ino --path /path/to/your/project
```

The analyzer discovers `.ino`, `.cpp`, `.h`, `.hpp`, `.c`, and `.cc` files. It excludes `.pio/`, `build/`, and `.git/` by default.

## Available Analyzers

| Analyzer | Description | Requirement |
|---|---|---|
| `max_lines_per_file` | Checks file length against warning and error thresholds | None |
| `pmd_duplicates` | Finds copied code blocks | PMD |
| `pmd_similar_code` | Finds structurally similar code | PMD |

## Example `code_analysis_rules.json`

```json
{
  "max_lines_per_file": {
    "enabled": true,
    "warning": 300,
    "error": 500
  },
  "pmd_duplicates": {
    "enabled": true,
    "minimum_tokens": 100
  },
  "pmd_similar_code": {
    "enabled": true,
    "minimum_tokens": 100
  }
}
```

Run with the configuration file:

```bash
python main.py --language cpp --path . --rules code_analysis_rules.json
```

## Changed Files and Exit Codes

Use `--only-changed` to analyze new or modified source files relative to Git `HEAD`. Untracked source files are included, and deleted files are skipped. This works with the project's `tools/analyze_changed_and_new_files.bat` once its config selects `--language cpp`.

```bash
python main.py --language cpp --path . --rules code_analysis_rules.json --only-changed
```

The command exits with code `1` when it finds an error or cannot complete analysis, and `0` when no errors are found. Duplicate and similar-code findings are warnings by default, so configure the analyzer's severity policy as needed for CI.
