# Version
2

# Coding Rules (Pointer)

This project's rules live in two files in the project root:

- `CODING_RULES.md` — code quality and conventions. BINDING for all code work in
  this repository, always.
- `IMPLEMENTATION_FLOW.md` — the end-to-end flow to follow when planning and
  implementing a change (checks, gates, Definition of Done).

MANDATORY: Before writing or editing ANY code, you MUST Read BOTH files in full
**in the current session**. Do not rely on memory of a previous session, a
summary, or partial reads.

If you are about to make a code change and have not read both files in this
session: STOP, read them, then continue.

An external tool may orchestrate the implementation itself. When a skill or run
states that the implementation is orchestrated, ignore `IMPLEMENTATION_FLOW.md`
entirely — the orchestrator runs those steps as its own phases. `CODING_RULES.md`
stays binding either way.

Do not inline rules back into this file and do not use `@import` for either file —
they are intentionally referenced, not imported.


# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CLI Code Analyzer is a multi-language command-line tool that analyzes code quality using configurable rules. It supports Flutter/Dart, Python, JavaScript/TypeScript, Svelte, PHP, C#, AutoHotkey, and Arduino/C++. Optimized for ensuring quality of AI-generated code.

## Running the Tool

```bash
# Basic analysis
python main.py --language flutter --path ./lib --rules rules.json

# Multiple languages (space-separated or comma-separated)
python main.py --language python javascript --path ./src
python main.py --language python,javascript --path ./src

# With output to CSV files
python main.py --language python --path ./src --output ./reports --verbosity verbose

# List available analyzers
python main.py --list-analyzers flutter
python main.py --list-analyzers all

# Filter by severity
python main.py --language javascript --path ./src --loglevel error

# List all analyzed file paths
python main.py --language python --path ./src --list-files

# JSON output
python main.py --language python --path ./src --format json

# Build violation cache for fast --file queries
python main.py --language python --path ./src --output ./reports --build-cache

# Query single file (uses cache if available, auto-rebuilds if stale)
python main.py --language python --path ./src --output ./reports --file src/app.py

# Query single file with JSON output (clean, no progress noise)
python main.py --language python --path ./src --output ./reports --file src/app.py --format json

# Analyze only files new or modified vs git HEAD (includes untracked, skips deletes)
python main.py --language flutter --path ./lib --only-changed --rules rules.json

# Run only a single analyzer from rules.json (e.g. just line-count checks)
python main.py --language flutter --path ./lib --rules rules.json --only-analyzer max_lines_per_file

# Exit non-zero for any reported finding, including warnings and informational findings
python main.py --language flutter --path ./lib --only-changed --fail-on-findings

# Audit locked dependencies for advisories and outdated packages
python main.py --audit-dependencies --path D:\projects\my-checkout

# Report the most complex function from files changed by a todo
python main.py --most-complex-function --path D:\projects\my-checkout --files-from changed-files.txt --diff-base <commit>
```

**Arguments:** `-l`/`--language` (flutter|python|php|csharp|javascript|svelte|autohotkey|cpp; supports multiple), `-p`/`--path`, `--audit-dependencies` (audit root dependency lock files and print JSON; requires `--path`), `--most-complex-function` (print the most complex listed function as JSON), `--files-from` (UTF-8 file of relative source paths; requires `--most-complex-function`), `--diff-base` (only include functions touched since a Git commit; requires `--most-complex-function`), `-F`/`--file` (filter violations to single file; defaults max errors to 5; suppresses progress output), `--only-changed` (filter to files new/modified in git vs HEAD; includes untracked, skips deletes; mutually exclusive with `--file`; defaults max errors to 5), `-r`/`--rules` (default: rules.json), `-v`/`--verbosity` (minimal|normal|verbose), `-o`/`--output` (folder for CSV; previous reports are auto-cleaned), `-L`/`--loglevel` (error|warning|all), `-m`/`--maxamountoferrors`, `-f`/`--list-files` (show analyzed file paths), `-a`/`--list-analyzers`, `--format` (text|json; default: text), `--build-cache` (build violation cache in output folder; requires --output), `--cache-max-age` (cache staleness in minutes; default: 60), `--only-analyzer` (run only the named analyzer(s) from --rules, skipping every other enabled rule; space- or comma-separated; disables the cache; mutually exclusive with --build-cache), `--fail-on-findings` (exit 1 on any reported violation of any severity after --loglevel filtering; default off)

**Exit codes:** 0 = no errors, 1 = errors found or failure; with `--fail-on-findings`, 1 also for warnings/infos.

## Architecture

The pipeline flows: `main.py` (CLI parsing) -> `CodeAnalyzer` (orchestration) -> `FileDiscovery` (find files) -> `BaseRule` subclasses (analysis) -> `Reporter` (output). A `Logger` instance is created in `main.py` and propagated to all components. When `--file` is used, the logger is set to quiet mode, suppressing all progress output. `ViolationCache` provides SQLite-based caching of violations for fast `--file` queries; the cache self-invalidates when analyzed source files are added, removed, or modified (file-set + newest-mtime check), when `rules.json` changes (hash), or after `--cache-max-age` minutes.

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
- `_get_tool_path(tool_name, getter, prompter)` - Resolves external tool paths via PATH, project-local `node_modules/.bin/`, settings, or user prompt
- `_filter_violations_by_log_level(violations)` - Filters violations by configured severity
- `_run_command(cmd)` - Subprocess execution helper
- `_scoped_commands(cmd, extensions, whole_project)` - Complete commands for a scoped tool, split below the Windows command-line limit
- `_run_json(tool, commands, cwd)` - Runs scoped commands and returns parsed JSON; raises `ToolOutputError` on untrusted output

### Exception path matching order

When resolving per-file threshold overrides in rules.json `exceptions` arrays:
1. Relative to `--path` (base_path)
2. Relative to rules.json location
3. Filename only
4. Glob patterns (`**/`, `*`, `?`)

## Knowledge graph

This project's code directory for graphify is `.` (the repo root); `.graphifyignore` keeps docs, tests, examples, tools and other non-code files out of the graph. Refresh with `tools/graphify_update.bat`.

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
- External tools are resolved lazily: PATH -> project-local `node_modules/.bin/` -> `settings.py` -> user prompt. The prompt emits `::tw-input-line::` when `TICKETS_WATCHER_COMMAND_RUN=1`; without a terminal, it logs the missing `[section] key` and skips instead of blocking.
- File paths in violations should always be relative (use `_get_relative_path()`)
- File exclusion patterns use forward slashes even on Windows
- A tool that could not start or produced unparseable output returns `_failed(...)`, never an empty `_ok([])`

## Dependencies

Defined in `requirements.txt`. Core: `pyyaml`, `intelephense-mpc-windows` (git dependency).

External tools are optional per-analyzer: PMD (duplicate detection), Dart/Flutter SDK, Ruff, ESLint, PHPStan, PHP-CS-Fixer, Intelephense, .NET SDK, dart-lsp-mcp.

## Documentation

- `docs/analyzers/` - Per-analyzer documentation (configuration, output format, examples)
- `docs/setup/` - Per-language setup guides (FLUTTER.md, PYTHON.md, PHP.md, CSHARP.md, JAVASCRIPT_TYPESCRIPT.md, SVELTE.md, ARDUINO_CPP.md)
- `CREATING_NEW_ANALYZER.md` - Step-by-step guide for adding new analyzers

## Post-Implementation Code Analysis

After **any** of the following events, you MUST run the changed-file analyzer and fix every reported issue before considering the work complete:

- A new feature has been implemented
- A plan from `claude-plans/` has been finished
- A bug has been fixed

### How to run

```bash
powershell -Command "cd 'D:\GIT\BenjaminKobjolke\cli-code-analyzer'; cmd /c '.\tools\analyze_changed_and_new_files.bat'"
```

This invokes cli-code-analyzer with `--only-changed`, so it reports only on files new or modified vs git `HEAD` (including untracked, excluding deletes).

### Workflow

1. Run the bat above.
2. Read the report under `code_analysis_results/`.
3. Fix every error and warning that applies to your changes.
4. Re-run until clean. Only then mark the feature / plan / bugfix as done.

If the bat does not exist, run `/analyze:enforce-post-feature-workflow` to install it.

## Code Analysis

For full-project analysis (all files, not just changed):

```bash
powershell -Command "cd 'D:\GIT\BenjaminKobjolke\cli-code-analyzer'; cmd /c '.\tools\analyze_code.bat'"
```

Fix any reported issues before committing. Auto-fix what Ruff can fix:

```bash
powershell -Command "cd 'D:\GIT\BenjaminKobjolke\cli-code-analyzer'; cmd /c '.\tools\fix_ruff_issues.bat'"
```

Preview Ruff fixes without applying:

```bash
powershell -Command "cd 'D:\GIT\BenjaminKobjolke\cli-code-analyzer'; cmd /c '.\tools\fix_ruff_issues_dry_run.bat'"
```

Reports land in `code_analysis_results/`. Self-analysis: this project IS cli-code-analyzer, so `CLI_ANALYZER_PATH` in `tools/analyze_code_config.bat` points at the project root.
