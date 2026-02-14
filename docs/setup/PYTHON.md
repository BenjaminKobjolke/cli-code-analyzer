# Python Project Setup

This guide explains how to set up cli-code-analyzer for Python projects.

## Prerequisites

- Python 3.7+
- PMD (optional, for duplicate code detection)
- Ruff (optional, for Python linting)

## Quick Start

```bash
python main.py --language python --path /path/to/your/project
```

## Available Rules

| Rule | Description |
|------|-------------|
| `max_lines_per_file` | Checks file length against warning/error thresholds |
| `pmd_duplicates` | Detects duplicate code blocks (requires PMD) |
| `ruff_analyze` | Fast Python linter with 800+ rules (replaces flake8/pylint) |

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
      "python": [
        "__pycache__/**",
        "*.pyc",
        "venv/**",
        ".venv/**",
        "*venv/**",
        "env/**",
        ".git/**"
      ]
    }
  },
  "ruff_analyze": {
    "enabled": true,
    "select": ["E", "F", "W"],
    "ignore": [],
    "exclude_patterns": ["venv/**", "__pycache__/**", ".git/**"]
  }
}
```

## Exclusion Patterns

Common patterns to exclude from analysis:

| Pattern | Purpose |
|---------|---------|
| `__pycache__/**` | Python bytecode cache |
| `*.pyc` | Compiled Python files |
| `venv/**` | Virtual environment |
| `.venv/**` | Hidden virtual environment |
| `*venv/**` | Any directory ending in "venv" |
| `env/**` | Alternative virtual environment name |
| `.git/**` | Git repository data |

## Example Batch Files (Windows)

Create a `tools` subfolder in your project and place the batch files there.

> **Note:** Do not add `pause` at the end of batch files. These scripts are designed to be called by other tools and `pause` would block execution.

### Analyze Code

Create `tools/analyze_code.bat`:

```batch
@echo off
d:
cd "d:\path\to\cli-code-analyzer"

call venv\Scripts\python.exe main.py --language python --path "D:\path\to\your\project" --verbosity minimal --output "D:\path\to\your\project\code_analysis_results" --maxamountoferrors 50 --rules "D:\path\to\your\project\code_analysis_rules.json"

cd %~dp0..
```

### Auto-Fix Ruff Issues

Create `tools/fix_ruff_issues.bat` to auto-fix Python issues:

```batch
@echo off
d:
cd "d:\path\to\cli-code-analyzer"

call venv\Scripts\python.exe ruff_fixer.py --path "D:\path\to\your\project" --rules "D:\path\to\your\project\code_analysis_rules.json"

cd %~dp0..
```

### Dry Run (Preview Fixes)

Create `tools/fix_ruff_issues_dry_run.bat` to preview what would be fixed:

```batch
@echo off
d:
cd "d:\path\to\cli-code-analyzer"

call venv\Scripts\python.exe ruff_fixer.py --path "D:\path\to\your\project" --rules "D:\path\to\your\project\code_analysis_rules.json" --dry-run

cd %~dp0..
```

## CLI Options

### Analyzer (main.py)

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--language` | `-l` | Set to `python` | Required |
| `--path` | `-p` | Path to project directory or file | Required |
| `--rules` | `-r` | Path to rules JSON file | `rules.json` |
| `--verbosity` | `-v` | Output level: `minimal`, `normal`, `verbose` | `normal` |
| `--output` | `-o` | Folder for CSV/TXT reports | None (console) |
| `--loglevel` | `-L` | Filter: `error`, `warning`, `all` | `all` |
| `--maxamountoferrors` | `-m` | Limit violations in CSV | Unlimited |
| `--list-files` | `-f` | List all analyzed file paths after analysis | Off |

### Ruff Fixer (ruff_fixer.py)

| Option | Description | Default |
|--------|-------------|---------|
| `--path` | Path to project directory or file | Required |
| `--rules` | Path to rules JSON file | `code_analysis_rules.json` |
| `--dry-run` | Show changes without applying them | False |

## Troubleshooting

### PMD not found
If you get a PMD path error:
1. Run the analyzer once - it will prompt to download/configure PMD
2. Or manually edit `settings.ini` in the cli-code-analyzer directory

### Exclusions not working
- Ensure patterns don't have leading `**/` (rglob already searches recursively)
- Use `*venv/**` to match any directory ending in "venv"
- Check your virtual environment name matches a pattern

### Unicode errors in files
PMD may report lexical errors for files with unusual Unicode characters. These are warnings and the file is skipped - your own code will still be analyzed.

### Ruff not found
If you get a Ruff path error:
1. Install Ruff with: `pip install ruff`
2. Or run the analyzer once - it will prompt to configure the Ruff path
3. Or manually edit `settings.ini` in the cli-code-analyzer directory

### Ruff Configuration
Ruff supports many rule categories. Common select options:
- `E` - pycodestyle errors
- `F` - Pyflakes errors
- `W` - pycodestyle warnings
- `B` - flake8-bugbear
- `I` - isort (import sorting)
- `N` - pep8-naming
- `UP` - pyupgrade (Python version upgrades)
- `SIM` - flake8-simplify
- `ARG` - flake8-unused-arguments
- `RUF` - Ruff-specific rules

See https://docs.astral.sh/ruff/rules/ for all available rules.

## Auto-Fix Workflow

The recommended workflow for Python projects:

1. **Analyze** - Find issues:
   ```bash
   python main.py --language python --path . --rules code_analysis_rules.json
   ```

2. **Auto-fix** - Fix what Ruff can automatically fix:
   ```bash
   python ruff_fixer.py --path . --rules code_analysis_rules.json
   ```

3. **Re-analyze** - Confirm remaining issues:
   ```bash
   python main.py --language python --path . --rules code_analysis_rules.json
   ```

Some issues cannot be auto-fixed and require manual intervention (e.g., unused arguments that might be needed for API compatibility).
