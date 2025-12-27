# Ruff Analyzer

## Overview

The Ruff analyzer checks Python code for style violations, complexity issues, logic errors, and other problems using Ruff - an extremely fast Python linter written in Rust. It supports hundreds of rules from popular linters like Pyflakes, pycodestyle, isort, and more.

## Supported Languages

Python only.

## Dependencies

**Ruff** must be installed:

```bash
pip install ruff
```

Or download from: https://docs.astral.sh/ruff/installation/

## Configuration

```json
{
  "ruff_analyze": {
    "enabled": true,
    "select": [
      "F",
      "E4", "E7", "E9",
      "W",
      "I",
      "B",
      "UP",
      "SIM",
      "C4",
      "PIE",
      "ARG",
      "RUF"
    ],
    "ignore": [],
    "exclude_patterns": [
      "venv",
      "__pycache__",
      ".git",
      ".venv",
      "node_modules",
      "build",
      "dist"
    ]
  }
}
```

### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enabled` | boolean | true | Enable/disable this analyzer |
| `select` | array | [] | Rule codes to enable |
| `ignore` | array | [] | Rule codes to ignore |
| `exclude_patterns` | array | [] | Directories/patterns to exclude |

### Common Rule Codes

| Code | Source | Description |
|------|--------|-------------|
| `F` | Pyflakes | Logical errors (undefined names, unused imports) |
| `E` | pycodestyle | Style errors |
| `W` | pycodestyle | Style warnings |
| `I` | isort | Import sorting |
| `B` | flake8-bugbear | Bug-prone patterns |
| `UP` | pyupgrade | Python upgrade suggestions |
| `SIM` | flake8-simplify | Simplification suggestions |
| `C4` | flake8-comprehensions | Comprehension improvements |
| `PIE` | flake8-pie | Misc improvements |
| `ARG` | flake8-unused-arguments | Unused function arguments |
| `RUF` | Ruff-specific | Ruff's own rules |

See full rule list: https://docs.astral.sh/ruff/rules/

## Output Format

### Console
```
Running ruff check...
Ruff found 15 issue(s)
Ruff analyze report saved to: code_analysis_results/ruff_analyze.csv
```

### CSV Output (`ruff_analyze.csv`)

| Column | Description |
|--------|-------------|
| file | Relative file path |
| line | Line number |
| column | Column number |
| severity | ERROR, WARNING, or INFO |
| code | Rule code (e.g., F401, E501) |
| message | Description of the issue |
| url | Link to rule documentation |

## Severity Mapping

| Code Prefix | Severity |
|-------------|----------|
| `E` (pycodestyle errors) | ERROR |
| `F` (Pyflakes) | WARNING |
| `W` (warnings) | WARNING |
| Others | INFO |

## Example Usage

```bash
# Analyze Python project
python main.py --language python --path ./src --rules rules.json

# With output to specific folder
python main.py --language python --path ./src --rules rules.json --output ./reports

# Filter by log level (errors only)
python main.py --language python --path ./src --rules rules.json --verbosity error
```

## Notes

- Ruff executes once per analysis run (project-wide, not per-file)
- Very fast compared to traditional Python linters
- Supports configuration via `pyproject.toml` or `ruff.toml` in addition to rules.json
