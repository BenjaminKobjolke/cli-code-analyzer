# Pyscn Analyzer

## Overview

The pyscn analyzer runs [pyscn](https://github.com/ludo-technologies/pyscn) to detect structural Python code-quality issues that traditional linters miss: per-function cyclomatic complexity, CFG-based dead code (unreachable branches), per-class coupling (CBO), and circular module dependencies.

pyscn is a single Go binary that uses tree-sitter parsing and control-flow analysis. It complements (does not replace) `ruff_analyze`: Ruff handles style/lint + unused symbols, pyscn handles structural metrics.

## Supported Languages

Python only.

## Dependencies

**pyscn** must be installed:

```bash
pipx install pyscn
# or
uvx pyscn@latest analyze .
# or
go install github.com/ludo-technologies/pyscn/cmd/pyscn@latest
```

If pyscn is not on `PATH`, the analyzer prompts on first run and saves the path to `settings.ini`.

## Configuration

```json
{
  "pyscn_analyze": {
    "enabled": true,
    "select": ["complexity", "deadcode", "deps"],
    "complexity": {
      "warning": 10,
      "error": 15,
      "exceptions": []
    },
    "dead_code": {
      "severity": "warning"
    },
    "coupling": {
      "warning": 8,
      "error": 15,
      "report_circular_deps": true,
      "circular_severity": "error",
      "exceptions": []
    },
    "exclude_patterns": ["**/__pycache__/**", "*.pyc", "**/.venv/**", "**/venv/**"]
  }
}
```

### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enabled` | boolean | false | Enable/disable this analyzer |
| `select` | array | `["complexity","deadcode","deps"]` | Sub-checks to run. Valid: `complexity`, `deadcode`, `deps`, `clones` |
| `complexity.warning` | int | 10 | Cyclomatic complexity warning threshold |
| `complexity.error` | int | 15 | Cyclomatic complexity error threshold |
| `complexity.exceptions` | array | `[]` | Per-file threshold overrides (see below) |
| `dead_code.severity` | string | `"warning"` | Default severity for dead-code findings (`error`/`warning`/`info`). pyscn's own per-finding severity (critical/warning/info) overrides this when present. |
| `coupling.warning` | int | 8 | CBO warning threshold |
| `coupling.error` | int | 15 | CBO error threshold |
| `coupling.exceptions` | array | `[]` | Per-file CBO threshold overrides |
| `coupling.report_circular_deps` | boolean | true | Emit violations for circular dependencies |
| `coupling.circular_severity` | string | `"error"` | Severity for circular dep violations |
| `exclude_patterns` | array | venv/cache patterns | Globs passed to pyscn for exclusion |

### Sub-check Selection

`select` controls which pyscn analyses run. Recommended: keep `complexity`, `deadcode`, `deps`. **Skip `clones`** unless you disable `pmd_duplicates` and `pmd_similar_code` — otherwise clone results overlap.

### Per-File Exceptions

Exceptions follow the standard BaseRule pattern (same as `dart_code_linter`):

```json
"complexity": {
  "warning": 10,
  "error": 15,
  "exceptions": [
    {
      "file": "src/orchestrator.py",
      "warning": 30,
      "error": 50
    },
    {
      "file": "**/parsers/*.py",
      "warning": 20,
      "error": 40
    }
  ]
}
```

Path matching: relative to `--path`, relative to `rules.json` location, filename only, or glob.

## Output Format

### Console
```
Running pyscn analyze...
pyscn found 7 issue(s)
Report saved to: code_analysis_results/pyscn_analyze.csv
```

### CSV Output (`pyscn_analyze.csv`)

| Column | Description |
|--------|-------------|
| file | Relative file path |
| line | Line number (blank for circular deps) |
| severity | ERROR, WARNING, or INFO |
| subcheck | `complexity`, `deadcode`, `coupling`, or `circular` |
| message | Description of the issue |

## Sub-check Behaviour

| Sub-check | Source field | Severity source |
|-----------|--------------|-----------------|
| `complexity` | `complexity.Functions[].Metrics.Complexity` | Threshold comparison |
| `deadcode` | `dead_code.files[].functions[].findings[]` | pyscn's `severity` (critical→ERROR, warning→WARNING, info→INFO), fallback `dead_code.severity` |
| `coupling` | `cbo.Classes[].Metrics.CouplingCount` | Threshold comparison |
| `circular` | `system.DependencyAnalysis.CircularDependencies` | `coupling.circular_severity` |

## Example Usage

```bash
# Analyze Python project
python main.py --language python --path ./src --rules rules.json

# With output to specific folder
python main.py --language python --path ./src --rules rules.json --output ./reports

# Errors only
python main.py --language python --path ./src --rules rules.json --loglevel error
```

## Ruff coexistence

Do not enable Ruff's `C` (mccabe complexity) family in `ruff_analyze.select` when pyscn is on — they'd double-report complexity. Ruff's F-rules (unused imports/vars) stay with Ruff; pyscn `deadcode` only flags CFG-unreachable branches, not unused symbols.

## Notes

- Project-wide: executes once per analysis run, not per file
- We invoke `pyscn analyze --json` (raw metrics), NOT `pyscn check` (CI gate). Thresholds are applied locally so per-file exceptions work
- `--build-cache` caches pyscn violations like any other analyzer; `--file <path>` queries the cache
