# TSC Analyzer

## Overview

The TSC analyzer runs TypeScript's `tsc --noEmit` compiler to perform type checking on your project without emitting output files. It catches type errors, missing imports, incorrect type usage, and other issues that TypeScript's type system can detect.

## Supported Languages

- TypeScript (`.ts`, `.tsx`)
- JavaScript with type checking (`.js`, `.jsx` when `checkJs` is enabled in tsconfig)

## Dependencies

**TypeScript** must be installed:

```bash
# Local installation in your project (recommended)
npm install --save-dev typescript

# Or global installation
npm install -g typescript
```

## Configuration

```json
{
  "tsc_analyze": {
    "enabled": true,
    "tsconfig": "./tsconfig.json",
    "skip_svelte_resolve_errors": true,
    "ignore_codes": []
  }
}
```

### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enabled` | boolean | false | Enable/disable this analyzer |
| `tsconfig` | string | `null` | Path to tsconfig.json (passed as `--project` flag) |
| `skip_svelte_resolve_errors` | boolean | true | Filter out TS2614 false positives caused by `.svelte` file imports (see below) |
| `ignore_codes` | array | `[]` | List of TypeScript error codes to ignore entirely (e.g., `["TS7006"]`) |

### skip_svelte_resolve_errors

When `tsc` encounters imports from `.svelte` files, it cannot resolve the actual exports and falls back to the `*.svelte` ambient module declaration. This causes **TS2614** errors for every named import from Svelte files — but only for Svelte-related imports. Real TS2614 errors (e.g., importing a non-existent named export from a `.ts` module) are still reported.

This option is enabled by default and specifically filters TS2614 errors that reference `*.svelte` modules, leaving all other TS2614 errors intact.

### ignore_codes

The `ignore_codes` option filters out **all** violations matching the specified TypeScript error codes. Use this sparingly as it suppresses all instances of a code regardless of context.

| Code | Description | When to ignore |
|------|-------------|----------------|
| `TS7006` | Parameter implicitly has an 'any' type | When strict mode flags are too noisy for legacy code |

## Svelte Projects

When using `tsc_analyze` alongside Svelte, enable `skip_svelte_resolve_errors` (on by default) and pair it with the `svelte_check` analyzer which handles Svelte-aware type checking correctly:

```json
{
  "svelte_check": {
    "enabled": true,
    "tsconfig": "./tsconfig.json"
  },
  "tsc_analyze": {
    "enabled": true,
    "tsconfig": "./tsconfig.json",
    "skip_svelte_resolve_errors": true
  }
}
```

## Output Format

### Console

```
Running tsc type checking...
tsc found 3 issue(s)
tsc report saved to: code_analysis_results/tsc_analyze.csv
```

### CSV Output (`tsc_analyze.csv`)

| Column | Description |
|--------|-------------|
| file | Relative file path |
| line | Line number |
| column | Column number |
| severity | ERROR or WARNING |
| code | TypeScript error code (e.g., TS2614) |
| message | Description of the issue |

## Severity Mapping

| tsc Severity | Internal Severity |
|--------------|-------------------|
| error | ERROR |
| warning | WARNING |

## Example Usage

```bash
# Analyze TypeScript project
python main.py --language javascript --path ./src --rules rules.json

# With Svelte project (Svelte false positives filtered by default)
python main.py --language typescript,svelte --path . --rules rules.json

# Filter by log level (errors only)
python main.py --language javascript --path ./src --rules rules.json --loglevel error

# Save report to file
python main.py --language javascript --path ./src --rules rules.json --output ./reports
```

## Notes

- TSC executes once per analysis run (project-wide, not per-file)
- Uses `--pretty false` for machine-parseable output
- If no `tsconfig` is specified, tsc uses its default resolution (finds nearest tsconfig.json)
- For Svelte projects, `skip_svelte_resolve_errors` (default: true) filters only the Svelte-specific TS2614 false positives while preserving real TS2614 errors
