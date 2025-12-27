# PHP Project Setup

This guide explains how to set up cli-code-analyzer for PHP projects.

## Prerequisites

- Python 3.9+
- PHP 8.4+
- Composer
- PMD (optional, for duplicate code detection)

## Quick Start

1. Install PHP dependencies:
   ```bash
   cd php
   install.bat
   # or: composer install
   ```

2. Run analysis:
   ```bash
   python main.py --language php --path /path/to/your/project
   ```

## Available Rules

| Rule | Description |
|------|-------------|
| `max_lines_per_file` | Checks file length against warning/error thresholds |
| `pmd_duplicates` | Detects duplicate code blocks (requires PMD) |
| `phpstan_analyze` | Static analysis using PHPStan |
| `php_cs_fixer` | Code style checking using PHP-CS-Fixer |

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
      "php": ["vendor/**", "node_modules/**", ".git/**"]
    }
  },
  "phpstan_analyze": {
    "enabled": true,
    "level": 5,
    "exclude_patterns": ["vendor/**", "node_modules/**", ".git/**"]
  },
  "php_cs_fixer": {
    "enabled": true,
    "rules": "@PSR12",
    "exclude_patterns": ["vendor/**", "node_modules/**", ".git/**"]
  }
}
```

## PHPStan Configuration

| Option | Description | Default |
|--------|-------------|---------|
| `level` | Analysis strictness (0-9, higher = stricter) | 5 |
| `exclude_patterns` | Glob patterns to exclude from analysis | `[]` |
| `analyze_path` | Specific path to analyze within project | project root |

### PHPStan Levels

| Level | Description |
|-------|-------------|
| 0 | Basic checks (unknown classes, functions, methods) |
| 1 | Possibly undefined variables, unknown magic methods |
| 2 | Unknown methods on all expressions (not just $this) |
| 3 | Return types, types assigned to properties |
| 4 | Basic dead code checking |
| 5 | Arguments and return types (recommended) |
| 6 | Report missing typehints |
| 7 | Report partially wrong union types |
| 8 | Report nullable issues |
| 9 | Be strict about mixed type |

## PHP-CS-Fixer Configuration

| Option | Description | Default |
|--------|-------------|---------|
| `rules` | Coding standard to enforce | `@PSR12` |
| `exclude_patterns` | Glob patterns to exclude from analysis | `[]` |

### Common Rule Sets

| Rule Set | Description |
|----------|-------------|
| `@PSR12` | PSR-12 coding standard (recommended) |
| `@PSR2` | PSR-2 coding standard |
| `@Symfony` | Symfony coding standard |
| `@PhpCsFixer` | PHP-CS-Fixer's own style |

## Exclusion Patterns

Common patterns to exclude from analysis:

| Pattern | Purpose |
|---------|---------|
| `vendor/**` | Composer dependencies |
| `node_modules/**` | npm dependencies |
| `.git/**` | Git repository data |
| `storage/**` | Laravel storage directory |
| `bootstrap/cache/**` | Laravel cache |

## Example Batch Files (Windows)

### Analyze Code

Create `analyze_code.bat` in your project root:

```batch
@echo off
d:
cd "d:\path\to\cli-code-analyzer"

call venv\Scripts\python.exe main.py --language php --path "D:\path\to\your\project" --verbosity minimal --output "D:\path\to\your\project\code_analysis_results" --maxamountoferrors 50 --rules "D:\path\to\your\project\code_analysis_rules.json"

cd %~dp0
pause
```

### Auto-Fix Code Style

Create `fix_php_issues.bat` in your project root:

```batch
@echo off
d:
cd "d:\path\to\cli-code-analyzer"

call venv\Scripts\python.exe php_fixer.py --path "D:\path\to\your\project" --rules "D:\path\to\your\project\code_analysis_rules.json"

cd %~dp0
pause
```

### Dry Run (Preview Fixes)

Create `fix_php_issues_dry_run.bat` to preview what would be fixed:

```batch
@echo off
d:
cd "d:\path\to\cli-code-analyzer"

call venv\Scripts\python.exe php_fixer.py --path "D:\path\to\your\project" --rules "D:\path\to\your\project\code_analysis_rules.json" --dry-run

cd %~dp0
pause
```

## CLI Options

### Analyzer (main.py)

| Option | Description | Default |
|--------|-------------|---------|
| `--language` | Set to `php` | Required |
| `--path` | Path to project directory or file | Required |
| `--rules` | Path to rules JSON file | `rules.json` |
| `--verbosity` | Output level: `minimal`, `normal`, `verbose` | `normal` |
| `--output` | Folder for CSV/TXT reports | None (console) |
| `--loglevel` | Filter: `error`, `warning`, `all` | `all` |
| `--maxamountoferrors` | Limit violations in CSV | Unlimited |

### PHP Fixer (php_fixer.py)

| Option | Description | Default |
|--------|-------------|---------|
| `--path` | Path to project directory or file | Required |
| `--rules` | Path to rules JSON file | `code_analysis_rules.json` |
| `--dry-run` | Show changes without applying them | False |

## Troubleshooting

### PHPStan not found

If you get a PHPStan path error:
1. Install dependencies: `cd php && composer install`
2. Or run the analyzer once - it will prompt to configure the PHPStan path
3. Or manually edit `settings.ini` in the cli-code-analyzer directory

### PHP-CS-Fixer not found

If you get a PHP-CS-Fixer path error:
1. Install dependencies: `cd php && composer install`
2. Or run the analyzer once - it will prompt to configure the path
3. Or manually edit `settings.ini` in the cli-code-analyzer directory

### PMD not found

If you get a PMD path error:
1. Run the analyzer once - it will prompt to download/configure PMD
2. Or manually edit `settings.ini` in the cli-code-analyzer directory

### Exclusions not working

- Ensure patterns use `/**` for recursive matching
- Use forward slashes `/` in patterns, even on Windows
- Check your vendor directory name matches the pattern

### Memory issues with large projects

PHPStan may run out of memory on large projects. Add to your phpstan.neon:
```yaml
parameters:
    memory_limit: 1G
```

## Auto-Fix Workflow

The recommended workflow for PHP projects:

1. **Analyze** - Find issues:
   ```bash
   python main.py --language php --path . --rules code_analysis_rules.json
   ```

2. **Auto-fix** - Fix code style issues:
   ```bash
   python php_fixer.py --path . --rules code_analysis_rules.json
   ```

3. **Re-analyze** - Confirm remaining issues:
   ```bash
   python main.py --language php --path . --rules code_analysis_rules.json
   ```

Note: PHPStan issues require manual fixes as they are logic/type errors, not style issues.
