# Code Analysis Fix Instructions

Work on fixing the problems reported in the CSV files located in the `@code_analysis_results` folder.

## CSV File Formats

Each rule generates a CSV with specific columns:

| Rule | CSV Columns |
|------|-------------|
| `ruff_analyze.csv` | `file,line,column,severity,code,message,url` |
| `dart_analyze.csv` | `file,line,column,severity,code,message` |
| `flutter_analyze.csv` | `file,line,column,severity,code,message` |
| `dart_code_linter.csv` | `file_path,metric,severity,message` |
| `line_count_report.csv` | `file,line_count,threshold,severity` |
| `duplicate_code.csv` | `lines,tokens,occurrences,files` |
| `phpstan_analyze.csv` | `file,line,severity,message` |
| `php_cs_fixer.csv` | `file,line,severity,rule,message` |

## Fix Priority

1. **ERROR** severity first - these are critical issues
2. **WARNING** severity second - code quality issues
3. **INFO** severity last - suggestions and improvements

## How to Fix Different Rule Types

### Line Count Issues (`max_lines_per_file`)
- Split large files into smaller, focused modules
- Extract classes/functions into separate files
- Consider if the file has too many responsibilities

### Duplicate Code (`pmd_duplicates`)
- Extract duplicated code into shared functions/utilities
- Create base classes for common patterns
- Use composition or inheritance where appropriate

### Python Issues (`ruff_analyze`)
- Follow the URL in the CSV for rule documentation
- Common fixes: remove unused imports, fix formatting, simplify expressions
- **Auto-fix available**: Many ruff issues can be auto-fixed

### Dart/Flutter Issues (`dart_analyze`, `flutter_analyze`)
- Follow Dart/Flutter style guide
- Fix type errors, null safety issues, unused variables

### Code Metrics (`dart_code_linter`)
- High cyclomatic complexity: break down complex functions
- Long methods: extract smaller functions
- Technical debt: refactor for maintainability

### PHP Issues (`phpstan_analyze`, `php_cs_fixer`)
- Fix type errors and undefined references
- Follow PSR-12 code style
- **Auto-fix available**: PHP-CS-Fixer can auto-fix style issues

## Adding Exceptions to Rules

If after analyzing a file you have good reasons why a threshold is too strict for a specific file, explain your reasoning to me. If I agree, add an exception to `@code_analysis_rules.json`.

### Exception Format

```json
{
  "max_lines_per_file": {
    "enabled": true,
    "warning": 300,
    "error": 500,
    "exceptions": [
      {
        "file": "path/to/file.py",
        "warning": 400,
        "error": 600,
        "reason": "Data access layer - requires getter/setter pairs for ~20 settings"
      }
    ]
  }
}
```

### Valid Reasons for Exceptions

- **Data models**: Files with many properties/fields naturally have more lines
- **Configuration files**: Large config classes with many settings
- **Generated code**: Auto-generated files that shouldn't be split
- **Test files**: Test suites covering many scenarios
- **API contracts**: Files defining many endpoints or DTOs

### Invalid Reasons for Exceptions

- "It's always been this way"
- "It would take too long to refactor"
- "I don't want to change it"

## Workflow

1. Read the CSV files to understand what issues exist
2. Prioritize by severity (ERROR > WARNING > INFO)
3. For each issue:
   - If it's a genuine code problem: fix it
   - If the threshold seems too strict for this file: explain why and wait for approval
4. After fixing, the analysis can be re-run to verify fixes
