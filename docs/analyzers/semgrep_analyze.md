# semgrep_analyze

## Overview

Project-wide pattern scanning using [semgrep](https://github.com/semgrep/semgrep). Ships with bundled rules in `semgrep_rules/` that flag complex boolean conditions (3+ operands), e.g. `if (a && b && c)`. Registered for flutter, python, php, csharp, javascript and svelte (semgrep scans the `.js`/`.ts` files of Svelte projects, not `.svelte` markup). Not available for AutoHotkey.

Note: Dart is an *experimental* language in semgrep Community Edition — parsing works well in practice (~100% parsed lines on real Flutter projects) but very new syntax may be skipped.

## Dependencies

```bash
pip install semgrep
```

Semgrep runs natively on Windows (no WSL/Docker needed) since the Fall 2025 release. Path resolution: PATH → `settings.ini` (`[semgrep] semgrep_path`) → interactive prompt.

## Configuration

```json
"semgrep_analyze": {
  "enabled": true,
  "config": null,
  "exclude_patterns": ["node_modules", ".venv", "venv", "vendor", "build", "dist", ".dart_tool", "*.g.dart", "*.freezed.dart"]
}
```

## Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enabled` | bool | `true` | Enable/disable the analyzer |
| `config` | string \| null | `null` | Semgrep `--config` value. `null` = bundled `semgrep_rules/` directory. Accepts a path (relative to `--path` or absolute) to a YAML file/directory, or a semgrep registry ref like `"p/default"` (needs network) |
| `exclude_patterns` | array | see above | Passed to semgrep as `--exclude`. Use **simple name globs** (`venv`, `*.g.dart`), matched against file/directory names — NOT path globs. `**/venv/**`-style patterns break semgrep's target resolution on Windows (it starts scanning `venv\..`, i.e. the whole project) |

Violation severity comes from each semgrep rule's `severity:` (INFO/WARNING/ERROR) in the YAML. Log-level filtering and `--maxamountoferrors` apply as usual.

## Bundled rules

`semgrep_rules/complex_boolean.yaml`:

- `complex-boolean-condition` (dart, javascript, typescript, php, csharp): `if ($A && $B && $C) ...` / `if ($A || $B || $C) ...` — matches 3 or more operands (associativity covers longer chains). Mixed `a && b || c` chains are not matched.
- `complex-boolean-condition-python`: same for `and`/`or`.

Add your own rules by dropping more YAML files into `semgrep_rules/`, or point `config` at a project-local rules directory.

## Filter mode

Scopeable: under `--file` / `--only-changed`, semgrep receives only the matching changed files (`.py .js .jsx .ts .tsx .php .cs .dart`) as targets.

## CSV Output

`semgrep_analyze.csv` in the output folder:

| Column | Description |
|--------|-------------|
| file | Relative file path |
| line | Line number |
| column | Column number |
| severity | INFO/WARNING/ERROR |
| message | Rule message + `[check_id]` |
