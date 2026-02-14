# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CLI Code Analyzer is a multi-language command-line tool that analyzes code quality using configurable rules. It supports Flutter/Dart, Python, JavaScript/TypeScript, PHP, and C#. Optimized for ensuring quality of AI-generated code.

## Running the Tool

```bash
# Basic analysis
python main.py --language flutter --path ./lib --rules rules.json

# With output to CSV files
python main.py --language python --path ./src --output ./reports --verbosity verbose

# List available analyzers
python main.py --list-analyzers flutter
python main.py --list-analyzers all

# Filter by severity
python main.py --language javascript --path ./src --loglevel error
```

**Arguments:** `--language` (flutter|python|php|csharp|javascript), `--path`, `--rules` (default: rules.json), `--verbosity` (minimal|normal|verbose), `--output` (folder for CSV), `--loglevel` (error|warning|all), `--maxamountoferrors`

**Exit codes:** 0 = no errors, 1 = errors found or failure.

## Architecture

The pipeline flows: `main.py` (CLI parsing) -> `CodeAnalyzer` (orchestration) -> `FileDiscovery` (find files) -> `BaseRule` subclasses (analysis) -> `Reporter` (output).

### Two types of analyzers

- **Project-wide** (most analyzers): Run once via `analyzer.py:analyze()`. The rule's `check()` is called once, often using an `_executed` flag to prevent re-runs. Examples: `dart_analyze`, `pmd_duplicates`, `ruff_analyze`, `eslint_analyze`.
- **Per-file** (`max_lines_per_file`): Run in `analyzer.py:_check_file()` for every discovered file.

### Log level resolution

Precedence: CLI `--loglevel` flag > per-rule `log_level` in rules.json > global `log_level` in rules.json > default (`all`). Implemented in `CodeAnalyzer._resolve_log_level()`.

### Configuration layers

- `rules.json` - Rule definitions with enable/disable, thresholds, and per-file exceptions
- `settings.ini` - Persistent tool paths (PMD, Dart SDK, Ruff, etc.), managed by `settings.py`
- `analyzer_registry.py` - Metadata registry mapping languages to their available analyzers

### Key base class utilities (`rules/base.py`)

All rules inherit `BaseRule`. Important methods:
- `_get_threshold_for_file(file_path, config)` - Resolves thresholds respecting file-specific exceptions
- `_match_file_path(file_path, pattern)` - Matches paths via exact, glob, or ends-with strategies
- `_get_relative_path(file_path)` - Converts absolute to relative paths for output
- `_get_tool_path(tool_name, getter, prompter)` - Resolves external tool paths via settings
- `_filter_violations_by_log_level(violations)` - Filters violations by configured severity
- `_run_command(cmd)` - Subprocess execution helper

### Exception path matching order

When resolving per-file threshold overrides in rules.json `exceptions` arrays:
1. Relative to `--path` (base_path)
2. Relative to rules.json location
3. Filename only
4. Glob patterns (`**/`, `*`, `?`)

## Creating a New Analyzer

Full guide in `CREATING_NEW_ANALYZER.md`. Summary:

1. Create `rules/your_name.py` inheriting `BaseRule`, implement `check()` returning `list[Violation]`
2. Add import/export to `rules/__init__.py`
3. Register in `analyzer.py` — either in `analyze()` (project-wide) or `_check_file()` (per-file)
4. Add entry to `analyzer_registry.py` for the appropriate language
5. Add default config to `rules.json`
6. Add documentation to `docs/analyzers/your_name.md`

## Project Conventions

- Rules always return `Violation` objects with severity `ERROR`, `WARNING`, or `INFO`
- Use `_get_threshold_for_file()` instead of reading thresholds directly (supports exceptions)
- Project-wide rules use an `_executed` flag pattern to run only once despite being called per-file
- External tools are resolved lazily through `settings.py` which prompts on first use
- File paths in violations should always be relative (use `_get_relative_path()`)
- File exclusion patterns use forward slashes even on Windows

## Dependencies

Defined in `requirements.txt`. Core: `pyyaml`, `intelephense-mpc-windows` (git dependency).

External tools are optional per-analyzer: PMD (duplicate detection), Dart/Flutter SDK, Ruff, ESLint, PHPStan, PHP-CS-Fixer, Intelephense, .NET SDK, dart-lsp-mcp.

## Documentation

- `docs/analyzers/` - Per-analyzer documentation (configuration, output format, examples)
- `docs/setup/` - Per-language setup guides (FLUTTER.md, PYTHON.md, PHP.md, CSHARP.md, JAVASCRIPT_TYPESCRIPT.md)
- `CREATING_NEW_ANALYZER.md` - Step-by-step guide for adding new analyzers
