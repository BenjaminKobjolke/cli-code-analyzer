# Kotlin Function Complexity Analyzer

## Overview

`kotlin_complexity` measures Kotlin functions with lizard's built-in Kotlin reader. It can report
cyclomatic complexity, function length in non-comment lines of code (NLOC), and parameter count.
Each configured metric produces at most one finding per function, at the function's starting line.

Lizard parses Kotlin heuristically. Lambdas may count toward their enclosing function, so review
findings in code that uses many nested lambdas.

## Configuration

Each metric is optional. Omit a metric block to leave it unchecked. Thresholds are inclusive: a
value at or above `error` is an error; otherwise a value at or above `warning` is a warning.
An exception can override either threshold for matching files.

```json
{
  "kotlin_complexity": {
    "enabled": true,
    "cyclomatic_complexity": {"warning": 10, "error": 15, "exceptions": []},
    "function_length": {"warning": 50, "error": 100, "exceptions": []},
    "parameter_count": {"warning": 5, "error": 8, "exceptions": []}
  }
}
```

Example exception:

```json
{
  "file": "app/src/main/java/example/Big.kt",
  "warning": 20,
  "error": 30
}
```

Place exception objects inside the relevant metric's `exceptions` array.

## Example finding

```text
ERROR  app/src/main/java/example/Screen.kt:42  Screen.render: cyclomatic complexity 16 (limit: 15)
```

CSV output uses the standard rule columns: `file_path`, `line`, `column`, `severity`, and
`message`. Kotlin `.kt` and `.kts` files also work with `--only-changed` and `--file`.
