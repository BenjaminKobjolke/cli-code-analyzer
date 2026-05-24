# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CLI Code Analyzer is a multi-language command-line tool that analyzes code quality using configurable rules. It supports Flutter/Dart, Python, JavaScript/TypeScript, Svelte, PHP, and C#. Optimized for ensuring quality of AI-generated code.

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
```

**Arguments:** `-l`/`--language` (flutter|python|php|csharp|javascript|svelte; supports multiple), `-p`/`--path`, `-F`/`--file` (filter violations to single file; defaults max errors to 5; suppresses progress output), `--only-changed` (filter to files new/modified in git vs HEAD; includes untracked, skips deletes; mutually exclusive with `--file`; defaults max errors to 5), `-r`/`--rules` (default: rules.json), `-v`/`--verbosity` (minimal|normal|verbose), `-o`/`--output` (folder for CSV; previous reports are auto-cleaned), `-L`/`--loglevel` (error|warning|all), `-m`/`--maxamountoferrors`, `-f`/`--list-files` (show analyzed file paths), `-a`/`--list-analyzers`, `--format` (text|json; default: text), `--build-cache` (build violation cache in output folder; requires --output), `--cache-max-age` (cache staleness in minutes; default: 60)

**Exit codes:** 0 = no errors, 1 = errors found or failure.

## Architecture

The pipeline flows: `main.py` (CLI parsing) -> `CodeAnalyzer` (orchestration) -> `FileDiscovery` (find files) -> `BaseRule` subclasses (analysis) -> `Reporter` (output). A `Logger` instance is created in `main.py` and propagated to all components. When `--file` is used, the logger is set to quiet mode, suppressing all progress output. `ViolationCache` provides SQLite-based caching of violations for fast `--file` queries.

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
- External tools are resolved lazily: PATH -> project-local `node_modules/.bin/` -> `settings.py` -> user prompt
- File paths in violations should always be relative (use `_get_relative_path()`)
- File exclusion patterns use forward slashes even on Windows

## Dependencies

Defined in `requirements.txt`. Core: `pyyaml`, `intelephense-mpc-windows` (git dependency).

External tools are optional per-analyzer: PMD (duplicate detection), Dart/Flutter SDK, Ruff, ESLint, PHPStan, PHP-CS-Fixer, Intelephense, .NET SDK, dart-lsp-mcp.

## Documentation

- `docs/analyzers/` - Per-analyzer documentation (configuration, output format, examples)
- `docs/setup/` - Per-language setup guides (FLUTTER.md, PYTHON.md, PHP.md, CSHARP.md, JAVASCRIPT_TYPESCRIPT.md, SVELTE.md)
- `CREATING_NEW_ANALYZER.md` - Step-by-step guide for adding new analyzers

## Code Analysis

After implementing new features or making significant changes, run the code analysis:

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

## Coding Rules

Source folder: `D:\GIT\BenjaminKobjolke\claude-code\coding-rules`
- Common: `COMMON_RULES.md`
- Python: `PYTHON_RULES.md`

The rules below are extracted and filtered for this project (Python CLI tool — no web layer, no DB, no i18n). Web/Jinja2, localization, Pydantic/API-validation, SQLAlchemy, and `start.bat` rules from the source files do not apply here and are intentionally omitted.

### Common Rules (all languages)

- **Use Objects for Related Values**: Bundle related parameters into DTO/Settings/Config objects instead of long parameter lists.
- **No Bag-of-Keys Returns at Module Boundaries**: Public methods on managers/repositories/services that cross a module boundary must return typed objects (DTO, value object, domain model) — never raw dicts/arrays indexed by string keys. Lists vs single must be obvious from the type/name. Distinguish absent (`None`) from empty (empty collection). JSON-decoded blobs that cross a boundary must be wrapped in a value object. Internal private helpers may stay as dicts.
- **Reuse Existing Models Before Inventing Array Shapes**: Grep the codebase for an existing domain class that owns the same data before creating a new DTO.
- **Tests Pin the Shape Before the Refactor**: When converting a bag-of-keys return to a typed object, write a characterization test against the existing API first, run it green, then refactor.
- **Test-Driven Development**: For features and bug fixes: write tests first → confirm fail → implement → confirm pass.
- **Integration Tests**: Every project must include integration tests in addition to unit tests.
- **Test Runner Scripts**: Provide `tools/run_tests.bat` (unit) and `tools/run_integration_tests.bat` (integration).
- **Prefer Type-Safe Values**: Use typed DTOs, enums, generics — not loosely typed strings/dicts.
- **String Constants**: Centralize string constants in a dedicated module. Do not scatter raw strings.
- **README.md is Mandatory**: Root `README.md` with name, description, install/setup, usage, dependencies.
- **DRY**: Extract duplicated logic into helpers/base abstractions; use constants for repeated values.
- **Confirm Dependency Versions**: Ask the user to verify latest stable version before adding any new package.
- **Error Handling & Logging Strategy**: Centralized error handler; structured logging (not `print`); log levels (debug/info/warning/error); include context (module, operation, IDs).
- **Input Validation at Boundaries**: Validate API inputs, user input, file uploads, external service responses. Fail fast with clear errors.
- **Maximum File Length — 300 Lines**: Split files when they exceed 300 lines. Exceptions: generated files, config files, test files with many similar cases.
- **Naming Conventions**: Python = `snake_case` files/functions/variables, `PascalCase` classes, `UPPER_SNAKE_CASE` constants.
- **Security Baseline**: Never commit secrets; escape output; parameterized queries only; validate/sanitize all input; keep dependencies updated.
- **No God Classes**: Warning signs = >5 public methods, >4 constructor deps, methods spanning unrelated domains. Split by responsibility. Avoid catch-all names like "Manager", "Handler", "Service", "Helper".
- **Self-Describing Classes**: When behavior depends on which fields a class has (search, serialization, display, validation, auditing), the class itself declares those fields via a contract (Protocol, abstract method, attribute/annotation). Never hardcode field lists in consumers.

### Python Rules (uv)

- **`pyproject.toml` as single source of truth**: Pin Python version (`>=3.11,<3.13` baseline). Manage deps via `uv add`. Commit `uv.lock`. (Note: this project currently uses `requirements.txt` — migrating to `uv` is a known future task.)
- **Formatting + linting + type checking in CI**: `uv add --dev ruff mypy`. CI runs `ruff check`, `ruff format --check`, `mypy`. Ruff replaces black/isort/flake8.
- **Type hints on public APIs**: All public functions/classes/methods have typed params + return types. Use `Sequence`, `Mapping`, `Protocol`, `TypedDict`, `Literal` where helpful. Avoid `Any` except at I/O / third-party boundaries.
- **Centralize configuration with env-driven settings**: One settings module reading `os.getenv`. No scattered `os.getenv` calls or magic values. Example: frozen `@dataclass Settings`.
- **Tests are mandatory, fast, and isolated**: `uv add --dev pytest`. Unit tests for core logic. No network in unit tests. Use tmp dirs / fixtures; no reliance on developer machine state. CI runs tests on every push.
- **Use `spec=` with MagicMock**: `MagicMock(spec=RealClass)` to validate against the real interface — without `spec`, typos and missing methods pass silently. If the real class exposes a method, mock the method (`mock.get_body.return_value = "x"`), not a fake attribute (`mock.body = "x"`).
- **Required Batch Files**: `tools/run_tests.bat` for tests. (`start.bat` does not apply — this is a CLI tool invoked as `python main.py …`.)
- **Async Patterns**: Use `asyncio` for I/O-bound work. Never block the event loop with `time.sleep` or sync HTTP inside `async` code.
- **Structured Logging**: Use `structlog` or `logging` with a JSON formatter — never `print()`. Centralized logging config used by all modules. (Project already has a `Logger` propagated from `main.py` — extend that, do not introduce ad-hoc loggers.)
- **Self-Describing Classes (Python implementation)**:
  - **Option A — Protocol with abstract method**: define a `Protocol` (e.g. `Searchable`) with `get_searchable_fields() -> list[str]`; each class implements it.
  - **Option B — Dataclass field metadata**: tag fields with `field(metadata={SEARCHABLE: True})`; iterate via `dataclasses.fields(obj)`.
  - Prefer Protocol for simple cases; use dataclass metadata for declarative per-field control.
