# Setup Python Project for CLI Code Analyzer

Help me setup the cli-code-analyzer for a new Python project. Ask me for the local path to the project.

## Files to Create

1. Copy all files from `D:\GIT\BenjaminKobjolke\cli-code-analyzer\prompts\setup_files\` to project's `tools/` folder
2. Edit `tools/config.bat`: set `LANGUAGE=python`
3. Create `code_analysis_rules.json` in project root

## Rules Configuration

```json
{
  "log_level": "all",
  "max_lines_per_file": {
    "enabled": true,
    "warning": 200,
    "error": 300
  },
  "pmd_duplicates": {
    "enabled": true,
    "minimum_tokens": 100,
    "exclude_patterns": {
      "python": ["__pycache__/**", "*.pyc", "venv/**", ".venv/**", ".git/**"]
    }
  },
  "ruff_analyze": {
    "enabled": true,
    "select": ["F", "E4", "E7", "E9", "W", "I", "B", "UP", "SIM", "C4", "PIE", "ARG", "RUF"],
    "ignore": [],
    "exclude_patterns": ["venv", ".venv", "__pycache__", ".git"]
  }
}
```

## Git Ignore

Add to `.gitignore`:
```
code_analysis_results/
```
