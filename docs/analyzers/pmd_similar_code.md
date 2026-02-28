# PMD Similar Code Analyzer

## Overview

The PMD Similar Code analyzer detects structurally similar code patterns across your project using PMD's CPD (Copy-Paste Detector) with identifier and literal normalization. Unlike the `pmd_duplicates` analyzer which finds exact token-based duplicates, this analyzer ignores variable names, function names, and literal values when comparing code blocks — catching copy-paste code where developers renamed variables or changed string/number constants.

## Difference from `pmd_duplicates`

| Feature | `pmd_duplicates` | `pmd_similar_code` |
|---------|-------------------|---------------------|
| Detection type | Exact token match | Structural similarity |
| Variable names | Must match exactly | Ignored (normalized) |
| String/number literals | Must match exactly | Ignored (normalized) |
| Use case | Find identical copy-paste | Find modified copy-paste |
| CSV output | `duplicate_code.csv` | `similar_code.csv` |

## Supported Languages

- Dart
- Python
- Java
- JavaScript
- TypeScript
- PHP
- C#

## Dependencies

**PMD** must be installed. The analyzer can auto-download PMD if not found:

- Download manually from: https://pmd.github.io/
- Or let the analyzer download it automatically when first run

## Configuration

```json
{
  "pmd_similar_code": {
    "enabled": true,
    "minimum_tokens": 100,
    "ignore_identifiers": true,
    "ignore_literals": true,
    "ignore_annotations": false,
    "exclude_patterns": {
      "dart": ["*.g.dart", "*.freezed.dart"],
      "python": ["**/__pycache__/**", "*.pyc"],
      "javascript": ["**/node_modules/**", "**/dist/**", "**/build/**"],
      "typescript": ["**/node_modules/**", "**/dist/**", "**/build/**"],
      "svelte": ["**/node_modules/**", "**/dist/**", "**/build/**", "**/.svelte-kit/**"]
    }
  }
}
```

### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enabled` | boolean | false | Enable/disable this analyzer |
| `minimum_tokens` | integer | 100 | Minimum token count for similarity detection |
| `ignore_identifiers` | boolean | true | Ignore variable/function names when comparing |
| `ignore_literals` | boolean | true | Ignore string/number literals when comparing |
| `ignore_annotations` | boolean | false | Ignore annotations/decorators when comparing |
| `exclude_patterns` | object/array | {} | Exclusion patterns (per-language or global) |
| `exclude_paths` | array | [] | Directory paths to exclude |
| `max_results` | integer | null | Maximum number of similar code groups to report |

### Minimum Tokens

The `minimum_tokens` setting controls how large a code block must be to be considered similar:
- Lower values (50-75): Find more similar patterns, including small ones
- Default (100): Balance between precision and noise
- Higher values (150+): Only report significant similarities

### Ignore Flags

- **`ignore_identifiers`**: When `true`, variable names, function names, and type names are normalized before comparison. Two code blocks that differ only in naming will be detected as similar.
- **`ignore_literals`**: When `true`, string constants, numeric literals, and other literal values are normalized. Code blocks that differ only in hardcoded values will be detected.
- **`ignore_annotations`**: When `true`, annotations/decorators (e.g., `@override`, `@Test`) are stripped before comparison.

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
| PHP | `**/vendor/**`, `**/node_modules/**` |
| C# | `**/bin/**`, `**/obj/**`, `**/.vs/**`, `**/packages/**` |

## Output Format

### Console
```
Checking for similar code patterns...
================================================================================
SIMILAR CODE DETECTION RESULTS
================================================================================
Total CSV lines (similar patterns found): 8
Total similar code lines: 412
================================================================================
Similar code report saved to: code_analysis_results/similar_code.csv
```

### CSV Output (`similar_code.csv`)

| Column | Description |
|--------|-------------|
| lines | Number of similar lines |
| tokens | Number of similar tokens |
| occurrences | Number of times the pattern appears |

## Severity Levels

All similar code findings are reported as **WARNING** severity.

## Example Usage

```bash
# Analyze Dart project for similar code
python main.py --language dart --path ./lib --rules rules.json

# Analyze Python project
python main.py --language python --path ./src --rules rules.json

# With specific output folder
python main.py --language java --path ./src --rules rules.json --output ./reports

# Run both duplicate and similar code detection
# (enable both pmd_duplicates and pmd_similar_code in rules.json)
python main.py --language javascript --path ./src --rules rules.json --output ./reports
```

## Notes

- PMD CPD analyzes the entire project at once (not per-file)
- Generated code files (like `*.g.dart`) should be excluded
- The analyzer creates a temporary exclusion file that is cleaned up after analysis
- Text output is shown in console, CSV is saved if output folder specified
- On Windows, PMD stderr warnings about reserved device names (`nul`, `con`, `prn`, `aux`) are automatically filtered out
- This analyzer reuses the same PMD installation as `pmd_duplicates`
- Both `pmd_duplicates` and `pmd_similar_code` can be enabled simultaneously — they produce separate reports
