# Setup PHP Project for CLI Code Analyzer

Help me setup the cli-code-analyzer for a new PHP project. Ask me for the local path to the project.

## Files to Create

1. Copy batch files from `D:\GIT\BenjaminKobjolke\cli-code-analyzer\prompts\setup_files\` to project's `tools/` folder
2. Copy `code_analysis.md` from `D:\GIT\BenjaminKobjolke\cli-code-analyzer\prompts\setup_files\` to project's `prompts/` folder
3. Edit `tools/config.bat`: set `LANGUAGE=php`
4. Create `code_analysis_rules.json` in project root

## Rules Configuration

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
    "exclude_paths": ["vendor", ".git"]
  },
  "phpstan_analyze": {
    "enabled": true,
    "level": 5
  },
  "php_cs_fixer": {
    "enabled": true,
    "rules": "@PSR12",
    "exclude_paths": ["vendor", ".git", "storage", "bootstrap/cache"],
    "managed": true
  }
}
```

## PHP-CS-Fixer Options

The `php_cs_fixer` rule supports the following options:

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enabled` | bool | - | Enable/disable the rule |
| `rules` | string | `@PSR12` | PHP-CS-Fixer ruleset (e.g., `@PSR12`, `@Symfony`) |
| `exclude_paths` | array | `["vendor", ".git"]` | Directories to exclude from analysis |
| `managed` | bool | `true` | Auto-manage `.php-cs-fixer.dist.php` config file |
| `analyze_path` | string | project root | Subdirectory to analyze (e.g., `"app"` or `"src"`) |

When `managed: true` (default), the tool will:
1. Create `.php-cs-fixer.dist.php` if it doesn't exist
2. Update the config file if `exclude_paths` in JSON differs from the config
3. Use the config file when running PHP-CS-Fixer

Set `managed: false` if you have a custom `.php-cs-fixer.dist.php` you don't want modified.

## Git Ignore

Add to `.gitignore`:
```
code_analysis_results/
```
