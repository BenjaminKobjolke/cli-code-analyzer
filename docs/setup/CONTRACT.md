# Contract Repository Setup

The `contract` analyzer checks JSON syntax and validates enum definitions in `enums.json`. It
runs in-process and needs no external analyzer, compiler, or package installation.

## Quick Start

From the contract repository, run:

```bash
python D:/GIT/BenjaminKobjolke/cli-code-analyzer/main.py --language contract --path . --rules code_analysis_rules.json --fail-on-warnings
```

The JSON alias also works:

```bash
python D:/GIT/BenjaminKobjolke/cli-code-analyzer/main.py --language json --path . --rules code_analysis_rules.json --fail-on-warnings
```

Use `--only-changed` in a changed-files check to inspect changed and untracked `.json` files:

```bash
python D:/GIT/BenjaminKobjolke/cli-code-analyzer/main.py --language contract --path . --rules code_analysis_rules.json --only-changed --fail-on-warnings
```

If the repository has no rules file yet, create `code_analysis_rules.json` containing `{}`. The
`contract_enums` rule is enabled by default for the contract language. To turn it off explicitly,
add `"contract_enums": {"enabled": false}`.

## Discovery and Excludes

The analyzer discovers `.json` files. It excludes `.git/`, `.claude/`, `node_modules/`,
`graphify-out/`, `tickets/`, `code_analysis_results/`, `tmp/`, and `coding-rules.json` by default.
The committed `code_analysis_rules.json` remains in scope. `--only-changed` also skips ignored
files and checks only new or modified files.

Add other repository-wide generated or local folders to `global_exclude_paths` in the rules file;
these are bare directory names and apply to discovery for every analyzer. Keep committed contract
JSON in scope so malformed files and invalid enum definitions are reported. For example:

```json
{
  "global_exclude_paths": ["local-cache", "generated"]
}
```

See [`contract_enums`](../analyzers/contract_enums.md) for the enum format and findings.
