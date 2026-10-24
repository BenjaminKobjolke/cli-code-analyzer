# Kotlin Project Setup

Use cli-code-analyzer to check Android and other Kotlin source files. Kotlin complexity checks run
in-process and need no Kotlin compiler, JDK, detekt, or ktlint. PMD is optional and is required only
for duplicate-code and similar-code checks.

## Quick Start

```bash
python main.py --language kotlin --path /path/to/project
# Short alias:
python main.py --language kt --path /path/to/project
```

The analyzer discovers `.kt` and `.kts` files and excludes `build/`, `.gradle/`, `.idea/`, and
`.git/` directories by default.

## Available Analyzers

| Analyzer | Description | Requirement |
|---|---|---|
| `max_lines_per_file` | Checks file length against warning and error thresholds | None |
| `pmd_duplicates` | Finds copied code blocks | PMD (optional) |
| `pmd_similar_code` | Finds structurally similar code | PMD (optional) |
| `kotlin_complexity` | Checks function complexity, NLOC length, and parameter count | lizard, included in requirements |

## Example `code_analysis_rules.json`

```json
{
  "max_lines_per_file": {"enabled": true, "warning": 300, "error": 500},
  "pmd_duplicates": {"enabled": true, "minimum_tokens": 100},
  "kotlin_complexity": {
    "enabled": true,
    "cyclomatic_complexity": {"warning": 10, "error": 15, "exceptions": []},
    "function_length": {"warning": 50, "error": 100, "exceptions": []},
    "parameter_count": {"warning": 5, "error": 8, "exceptions": []}
  }
}
```

Tune thresholds for your project's style. See
[`docs/analyzers/kotlin_complexity.md`](../analyzers/kotlin_complexity.md) for metric details and
per-file exceptions.

## Changed Files and Exit Codes

To check new or modified Kotlin files relative to Git `HEAD`:

```bash
python main.py --language kotlin --path . --rules code_analysis_rules.json --only-changed
```

The command exits with code `1` when an error finding is reported or analysis fails, and `0` when
there are no errors. Warnings alone do not fail the run; set a metric's `error` threshold to the
value that should block your build.
