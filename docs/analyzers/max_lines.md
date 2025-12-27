# Max Lines Per File Analyzer

## Overview

The Max Lines analyzer checks if source files exceed configurable line count thresholds. This helps maintain readable and maintainable codebases by flagging overly large files that may need refactoring.

## Supported Languages

All languages - this analyzer applies universally to all files discovered during analysis.

## Dependencies

None - this is a pure Python implementation with no external tools required.

## Configuration

```json
{
  "max_lines_per_file": {
    "enabled": true,
    "warning": 300,
    "error": 500,
    "exclude_patterns": [
      "venv/**",
      "__pycache__/**",
      "*.pyc",
      ".git/**"
    ],
    "exceptions": [
      {
        "file": "services/large_service.py",
        "warning": 600,
        "error": 800
      }
    ]
  }
}
```

### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enabled` | boolean | true | Enable/disable this analyzer |
| `warning` | integer | 300 | Line count threshold for warnings |
| `error` | integer | 500 | Line count threshold for errors |
| `exclude_patterns` | array | [] | Glob patterns for files to exclude |
| `exceptions` | array | [] | File-specific threshold overrides |

### Exception Configuration

Exceptions allow per-file threshold overrides:

```json
{
  "file": "path/to/file.py",
  "warning": 600,
  "error": 800
}
```

The `file` pattern supports:
- Exact match: `"services/my_service.py"`
- Glob patterns: `"services/*.py"`, `"**/test_*.py"`
- Ends-with match: `"my_service.py"` matches `"lib/services/my_service.py"`

## Output Format

### Console
```
Checking max lines per file...
Max lines report saved to: code_analysis_results/max_lines.csv
```

### CSV Output (`max_lines.csv`)

| Column | Description |
|--------|-------------|
| file | Relative file path |
| lines | Actual line count |
| threshold | Threshold that was exceeded |
| severity | WARNING or ERROR |

## Severity Levels

- **WARNING**: File exceeds warning threshold but is below error threshold
- **ERROR**: File exceeds error threshold

## Example Usage

```bash
# Analyze Python project with default thresholds
python main.py --language python --path ./src --rules rules.json

# With custom output folder
python main.py --language python --path ./src --rules rules.json --output ./reports
```
