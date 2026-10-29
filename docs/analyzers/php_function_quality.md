# php_function_quality

## Overview

Checks individual PHP functions and methods for configurable size and complexity thresholds. It
uses Lizard to locate functions and calculate lines of code and cyclomatic complexity. The
analyzer also estimates cognitive complexity and control-flow nesting from PHP source.

The analyzer is registered for PHP scans and is enabled by default when its entry is absent. It
does not run for scans of other languages. Set `enabled` to `false` to opt out.

## Configuration

```json
"php_function_quality": {
  "enabled": true,
  "function_length": {"warning": 50, "error": 100, "exceptions": []},
  "cyclomatic_complexity": {"warning": 10, "error": 15, "exceptions": []},
  "cognitive_complexity": {"warning": 15, "error": 25, "exceptions": []},
  "nesting_depth": {"warning": 4, "error": 6, "exceptions": []},
  "parameter_count": {"warning": 5, "error": 8, "exceptions": []},
  "exclude_patterns": ["vendor/**", "**/vendor/**"]
}
```

Each metric can set `warning` and `error` limits; reaching the error limit reports an error,
otherwise reaching the warning limit reports a warning. Per-file `exceptions` use the same
`file`, `warning`, and `error` fields as other threshold-based analyzers. The default warning
limits are 50 lines, cyclomatic complexity 10, cognitive complexity 15, and nesting depth 4.
Parameter-count checks run only when configured.

`exclude_patterns` skips matching PHP paths. Patterns use forward slashes on every platform.

## Limits

Lizard supplies function boundaries and core metrics, but cognitive complexity and nesting are
estimated from masked PHP source rather than a complete PHP abstract syntax tree. Findings are
threshold signals for review, not proof that a function is defective.
