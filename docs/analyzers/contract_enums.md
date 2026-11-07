# Contract JSON Analyzer

## Overview

`contract_enums` checks the syntax of every discovered `.json` file. It also validates the
shared enum definitions in files named `enums.json` at any depth. Findings are errors and include
the relative file path; enum-specific findings name the enum.

For each enum, `values` must be a non-empty array of unique strings in case-sensitive sorted
order. `direction` must be `api_to_client` or `client_to_api`, and `description` must be a
non-empty string. Other valid JSON files are parsed but do not need to follow the enum format.
Malformed JSON findings include the line and column. Files that cannot be read are reported as
analysis failures.

## Example `enums.json`

```json
{
  "AppErrorKind": {
    "values": ["authentication", "network", "unknown"],
    "direction": "api_to_client",
    "description": "Error categories returned by the API."
  }
}
```

Example finding:

```text
ERROR  enums.json  AppErrorKind: values must be sorted
```

The rule is enabled by default for `--language contract`. To disable it, add
`"contract_enums": {"enabled": false}` to the rules file.

## Scope

The `contract` language discovers `.json` files. Default excludes skip local state such as
`.claude/`, `graphify-out/`, `tickets/`, `tmp/`, `node_modules/`, and `code_analysis_results/`, as
well as `coding-rules.json`. `code_analysis_rules.json` remains included so invalid committed
configuration is reported. `--only-changed` checks only changed or untracked JSON files.
