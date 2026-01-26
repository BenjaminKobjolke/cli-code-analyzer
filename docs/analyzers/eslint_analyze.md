# ESLint Analyzer

## Overview

The ESLint analyzer checks JavaScript and TypeScript code for style violations, potential bugs, and best practice violations using ESLint - the most popular JavaScript linter. It supports hundreds of rules and can be extended with plugins.

## Supported Languages

- JavaScript (`.js`, `.mjs`, `.cjs`)
- TypeScript (`.ts`, `.tsx`)
- JSX (`.jsx`)

## Dependencies

**ESLint** must be installed:

```bash
# Global installation
npm install -g eslint

# Or local installation in your project
npm install --save-dev eslint
```

For TypeScript support, also install:

```bash
npm install --save-dev @typescript-eslint/parser @typescript-eslint/eslint-plugin
```

## Configuration

```json
{
  "eslint_analyze": {
    "enabled": true,
    "config_mode": "auto",
    "env": {
      "browser": true,
      "es2021": true,
      "node": true
    },
    "rules": {
      "no-unused-vars": "warn",
      "no-undef": "error",
      "semi": ["error", "always"]
    },
    "exclude_patterns": [
      "node_modules/**",
      "dist/**",
      "build/**",
      "coverage/**"
    ]
  }
}
```

### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enabled` | boolean | true | Enable/disable this analyzer |
| `config_mode` | string | "auto" | Config mode: "auto", "builtin", or "project" |
| `env` | object | {} | Environment globals (browser, node, es2021, etc.) |
| `rules` | object | {} | ESLint rules and their severity |
| `exclude_patterns` | array | [] | Directories/patterns to exclude |

### Config Modes

| Mode | Behavior |
|------|----------|
| `auto` | Use project config if exists, otherwise use rules.json settings |
| `builtin` | Ignore project config, use only rules.json settings |
| `project` | Require project config, fail if not found |

### Rule Severity Values

ESLint rules can be set to:
- `"off"` or `0` - Turn the rule off
- `"warn"` or `1` - Turn the rule on as a warning
- `"error"` or `2` - Turn the rule on as an error

Rules can also have options:
```json
{
  "rules": {
    "semi": ["error", "always"],
    "quotes": ["warn", "single"],
    "indent": ["error", 2]
  }
}
```

### Common Rules

| Rule | Description |
|------|-------------|
| `no-unused-vars` | Disallow unused variables |
| `no-undef` | Disallow use of undeclared variables |
| `no-console` | Disallow console.log statements |
| `semi` | Require or disallow semicolons |
| `quotes` | Enforce consistent quote style |
| `eqeqeq` | Require === and !== instead of == and != |
| `curly` | Require curly braces for all control statements |
| `no-var` | Require let or const instead of var |
| `prefer-const` | Suggest using const where possible |
| `no-duplicate-imports` | Disallow duplicate imports |

See full rule list: https://eslint.org/docs/rules/

## Output Format

### Console

```
Running ESLint check...
ESLint found 15 issue(s)
ESLint report saved to: code_analysis_results/eslint_analyze.csv
```

### CSV Output (`eslint_analyze.csv`)

| Column | Description |
|--------|-------------|
| file | Relative file path |
| line | Line number |
| column | Column number |
| severity | ERROR, WARNING, or INFO |
| rule | Rule ID (e.g., no-unused-vars, semi) |
| message | Description of the issue |

## Severity Mapping

ESLint uses numeric severity levels that are mapped as follows:

| ESLint Severity | Internal Severity |
|-----------------|-------------------|
| 2 (error) | ERROR |
| 1 (warning) | WARNING |
| 0 (off) | Not reported |

## Example Usage

```bash
# Analyze JavaScript/TypeScript project
python main.py --language javascript --path ./src --rules rules.json

# With output to specific folder
python main.py --language javascript --path ./src --rules rules.json --output ./reports

# Filter by log level (errors only)
python main.py --language javascript --path ./src --rules rules.json --loglevel error

# Limit number of errors in report
python main.py --language javascript --path ./src --rules rules.json --maxamountoferrors 50
```

## Project Config Files

ESLint automatically detects these config files (in `config_mode: "auto"` or `config_mode: "project"`):

- `eslint.config.js` (ESLint 9+ flat config)
- `eslint.config.mjs`
- `eslint.config.cjs`
- `.eslintrc.js`
- `.eslintrc.cjs`
- `.eslintrc.yaml`
- `.eslintrc.yml`
- `.eslintrc.json`
- `.eslintrc`
- `package.json` with `eslintConfig` key

## Notes

- ESLint executes once per analysis run (project-wide, not per-file)
- For TypeScript projects, ensure `@typescript-eslint/parser` is configured in your project
- The `config_mode` option allows flexible handling of existing project configs
- Environment settings (`env`) define which global variables are available
- Use `exclude_patterns` to skip generated or vendor files
