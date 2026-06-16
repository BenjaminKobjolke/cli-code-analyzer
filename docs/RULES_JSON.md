# rules.json Reference

`rules.json` (passed via `-r`/`--rules`, default `rules.json`) configures which
analyzers run, their thresholds, severity filtering, and per-file exceptions. It
is a single JSON object: top-level keys are either **global settings** or
**per-rule config blocks** keyed by analyzer name.

```jsonc
{
  "log_level": "error",     // global setting
  "max_errors": 20,         // global setting
  "max_lines_per_file": {   // per-rule block
    "enabled": true,
    "warning": 300,
    "error": 500
  }
}
```

## Global settings

| Key | Type | Default | Meaning |
|-----|------|---------|---------|
| `log_level` | `"error"` \| `"warning"` \| `"all"` | `all` | Default severity filter for every rule. See [Log level resolution](#log-level-resolution). |
| `max_errors` | positive int | unset (unlimited) | Caps violations reported **per rule/analyzer** (not a global total). See [Max errors](#max-errors). |

Any other top-level key is treated as a per-rule config block.

## Per-rule config blocks

Each analyzer reads its own block (e.g. `dart_code_linter`, `ruff_analyze`,
`pmd_duplicates`). Common fields:

| Field | Meaning |
|-------|---------|
| `enabled` | `true`/`false`. A rule absent or `false` does not run. |
| `log_level` | Per-rule severity filter; overrides the global `log_level`. |
| `warning` / `error` | Numeric thresholds (meaning depends on the metric — lines, complexity, coverage %, etc.). |
| `exclude_patterns` | Glob patterns (forward slashes, even on Windows) to skip files. Shape varies per analyzer — a flat list, or keyed by language for PMD. |
| `exceptions` | Per-file overrides of thresholds. See [Exceptions](#exceptions). |
| `severity` | For rules that emit a single severity, sets it to `warning`/`error`. |

Per-analyzer fields are documented under [`docs/analyzers/`](analyzers/).

## Max errors

`max_errors` limits how many violations each analyzer reports. With
`"max_errors": 20`, every rule emits at most 20 violations (per CSV / per type),
so the report is not flooded by one noisy rule. It is **per rule**, not a global
cap across all rules.

Resolution precedence (highest first):

1. CLI `-m`/`--maxamountoferrors`
2. `max_errors` in `rules.json`
3. Filter-mode default of `5` (applies to `--file` and `--only-changed`)
4. Unlimited

So a `--file` query with no `-m` and no `rules.json` `max_errors` reports 5 per
rule; add `"max_errors": 20` to raise that to 20 without touching the command.

PMD rules (`pmd_duplicates`, `pmd_similar_code`) also accept a per-rule
`max_results` field, used only when no higher-precedence cap is set.

## Log level resolution

Precedence (highest first): CLI `--loglevel` > per-rule `log_level` > global
`log_level` > default (`all`). `error` shows errors only; `warning` shows
warnings and errors; `all` shows everything.

## Exceptions

`exceptions` arrays raise thresholds for specific files (e.g. a generated file or
an intentionally large model). Each entry targets a file and supplies overriding
`warning`/`error` values plus a `reason` and `checked` date for auditability:

```jsonc
"exceptions": [
  {
    "file": "models/view_settings/domain/view_settings.dart",
    "warning": 1120,
    "error": 1240,
    "reason": "80+ doc-commented fields; not splittable without code generation",
    "checked": "2026-06-14"
  }
]
```

Path matching order:

1. Relative to `--path` (base path)
2. Relative to the `rules.json` location
3. Filename only
4. Glob patterns (`**/`, `*`, `?`)

PMD duplicate exceptions instead use a `files` array (the set of files whose
mutual duplication is accepted).

## Related

- [`README.md`](../README.md) — CLI usage and arguments
- [`docs/analyzers/`](analyzers/) — per-analyzer configuration and output
- [`CREATING_NEW_ANALYZER.md`](../CREATING_NEW_ANALYZER.md) — adding a new analyzer
