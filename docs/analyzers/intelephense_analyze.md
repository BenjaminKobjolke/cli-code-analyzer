# Intelephense Analyzer

## Overview

The Intelephense analyzer checks PHP code for errors, warnings, and hints using Intelephense - a high-performance PHP language server. It provides real-time diagnostics including undefined variables, type errors, unused code, and more.

## Supported Languages

PHP only.

## Dependencies

**Intelephense** must be installed globally via npm:

```bash
npm install -g intelephense
```

**Note:** This analyzer also requires the `intelephense-mpc-windows` project to be present as a sibling directory to `cli-code-analyzer`.

## Configuration

```json
{
  "intelephense_analyze": {
    "enabled": true,
    "min_severity": "warning",
    "timeout": 5,
    "exclude_patterns": [
      "vendor/**",
      "node_modules/**",
      ".git/**"
    ],
    "ignore_unused_underscore": true
  }
}
```

### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enabled` | boolean | false | Enable/disable this analyzer |
| `min_severity` | string | "warning" | Minimum severity to report ("error", "warning", "info", "hint") |
| `timeout` | number | 5 | Seconds to wait for diagnostics after indexing |
| `exclude_patterns` | array | [] | Glob patterns to exclude from analysis |
| `ignore_unused_underscore` | boolean | true | Filter out unused `$_xxx` variable hints |

### Severity Levels

| Level | Description |
|-------|-------------|
| `error` | Critical issues that prevent code from working |
| `warning` | Potential problems that should be addressed |
| `info` | Informational messages |
| `hint` | Suggestions for improvement |

## Output Format

### Console
```
Running Intelephense check...
Intelephense found 12 issue(s)
Intelephense report saved to: code_analysis_results/intelephense_analyze.csv
```

### CSV Output (`intelephense_analyze.csv`)

| Column | Description |
|--------|-------------|
| file | Relative file path |
| line | Line number (1-indexed) |
| column | Column number (1-indexed) |
| severity | error, warning, info, or hint |
| message | Description of the issue |

## Severity Mapping

| Intelephense | cli-code-analyzer |
|--------------|-------------------|
| error | ERROR |
| warning | WARNING |
| info | INFO |
| hint | INFO |

## Example Usage

```bash
# Analyze PHP project
python main.py --language php --path ./src --rules rules.json

# With output to specific folder
python main.py --language php --path ./src --rules rules.json --output ./reports

# Filter by log level (errors only)
python main.py --language php --path ./src --rules rules.json --verbosity error
```

## Notes

- Intelephense executes once per analysis run (project-wide, not per-file)
- The analyzer starts an LSP server, indexes all PHP files, then collects diagnostics
- The `timeout` setting controls how long to wait for the LSP to process all files
- For large projects, you may need to increase the timeout value
- The `ignore_unused_underscore` option filters hints about intentionally unused variables (e.g., `$_response`)
- Can be used alongside PHPStan for complementary static analysis coverage
