# Setup Flutter Project for CLI Code Analyzer

Help me setup the cli-code-analyzer for a new Flutter project. Ask me for the local path to the project.

## Files to Create

1. Copy batch files from `D:\GIT\BenjaminKobjolke\cli-code-analyzer\prompts\setup_files\` to project's `tools/` folder
2. Copy `code_analysis.md` from `D:\GIT\BenjaminKobjolke\cli-code-analyzer\prompts\setup_files\` to project's `prompts/` folder
3. Edit `tools/config.bat`: set `LANGUAGE=flutter`
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
      "dart": ["*.g.dart", "*.freezed.dart", "*.mocks.dart", "*.gr.dart"]
    }
  },
  "dart_analyze": {
    "enabled": true
  },
  "dart_code_linter": {
    "enabled": true,
    "auto_install": false,
    "analyze_path": "lib",
    "keep_report": false,
    "metrics": {
      "cyclomatic-complexity": {
        "warning": 10,
        "error": 15
      },
      "number-of-methods": {
        "warning": 10,
        "error": 20
      },
      "technical-debt": {
        "warning": 10,
        "error": 50
      },
      "maintainability-index": {
        "warning": 40,
        "error": 20
      },
      "maximum-nesting-level": {
        "warning": 3,
        "error": 5
      },
      "halstead-volume": {
        "warning": 800,
        "error": 1200
      }
    }
  },
  "flutter_analyze": {
    "enabled": false,
    "exclude_patterns": ["*.g.dart", "*.freezed.dart"]
  }
}
```

## Git Ignore

Add to `.gitignore`:
```
code_analysis_results/
```

## Notes

- Exclude generated files: `*.g.dart`, `*.freezed.dart`, `*.mocks.dart`, `*.gr.dart`
- If `dart_code_linter` is not installed, set `"auto_install": true` or run `dart pub global activate dart_code_linter`
- `maintainability-index` is inverted: lower values = worse code (warning 40, error 20)
