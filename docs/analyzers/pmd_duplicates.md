# PMD Duplicates Analyzer

## Overview

The PMD Duplicates analyzer detects copy-paste code (duplicate code blocks) across your project using PMD's CPD (Copy-Paste Detector). Duplicate code increases maintenance burden and bug risk - when a bug is found in duplicated code, it must be fixed in multiple places.

## Supported Languages

- Dart
- Python
- Java
- JavaScript
- TypeScript

## Dependencies

**PMD** must be installed. The analyzer can auto-download PMD if not found:

- Download manually from: https://pmd.github.io/
- Or let the analyzer download it automatically when first run

## Configuration

```json
{
  "pmd_duplicates": {
    "enabled": true,
    "minimum_tokens": 100,
    "exclude_patterns": {
      "dart": ["*.g.dart", "*.freezed.dart"],
      "python": ["**/__pycache__/**", "*.pyc"],
      "java": ["**/target/**", "**/build/**"],
      "javascript": ["**/node_modules/**", "**/dist/**", "**/build/**"],
      "typescript": ["**/node_modules/**", "**/dist/**", "**/build/**"]
    }
  }
}
```

### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enabled` | boolean | true | Enable/disable this analyzer |
| `minimum_tokens` | integer | 100 | Minimum token count for duplicate detection |
| `exclude_patterns` | object/array | {} | Exclusion patterns (per-language or global) |

### Minimum Tokens

The `minimum_tokens` setting controls how large a code block must be to be considered a duplicate:
- Lower values (50-75): Find more duplicates, including small patterns
- Default (100): Balance between precision and noise
- Higher values (150+): Only report significant duplications

### Exclude Patterns

Patterns can be configured per-language or globally:

**Per-language (recommended):**
```json
{
  "exclude_patterns": {
    "dart": ["*.g.dart", "*.freezed.dart"],
    "python": ["**/__pycache__/**"]
  }
}
```

**Global:**
```json
{
  "exclude_patterns": ["**/generated/**", "**/vendor/**"]
}
```

### Default Exclusions

| Language | Default Patterns |
|----------|-----------------|
| Dart | `*.g.dart`, `*.freezed.dart` |
| Python | `**/__pycache__/**`, `*.pyc` |
| Java | `**/target/**`, `**/build/**` |
| JavaScript | `**/node_modules/**`, `**/dist/**`, `**/build/**` |
| TypeScript | `**/node_modules/**`, `**/dist/**`, `**/build/**` |

## Output Format

### Console
```
Checking for duplicate code...
================================================================================
DUPLICATE CODE DETECTION RESULTS
================================================================================
Total CSV lines (duplicates found): 5
Total duplicate code lines: 234
================================================================================
Duplicate code report saved to: code_analysis_results/duplicate_code.csv
```

### CSV Output (`duplicate_code.csv`)

| Column | Description |
|--------|-------------|
| lines | Number of duplicated lines |
| tokens | Number of duplicated tokens |
| occurrences | Number of times the code appears |

## Severity Levels

All duplicate code findings are reported as **WARNING** severity.

## Example Usage

```bash
# Analyze Dart project for duplicates
python main.py --language dart --path ./lib --rules rules.json

# Analyze Python project
python main.py --language python --path ./src --rules rules.json

# With specific output folder
python main.py --language java --path ./src --rules rules.json --output ./reports
```

## Notes

- PMD CPD analyzes the entire project at once (not per-file)
- Generated code files (like `*.g.dart`) should be excluded
- The analyzer creates a temporary exclusion file that is cleaned up after analysis
- Text output is shown in console, CSV is saved if output folder specified
- On Windows, PMD stderr warnings about reserved device names (`nul`, `con`, `prn`, `aux`) are automatically filtered out
