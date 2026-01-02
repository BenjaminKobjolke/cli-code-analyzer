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
    "exclude_patterns": {
      "php": ["vendor/**", ".git/**"]
    }
  },
  "phpstan_analyze": {
    "enabled": true,
    "level": 5
  },
  "php_cs_fixer": {
    "enabled": true,
    "rules": "@PSR12"
  }
}
```

## Git Ignore

Add to `.gitignore`:
```
code_analysis_results/
```
