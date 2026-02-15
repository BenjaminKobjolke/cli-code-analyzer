# JavaScript/TypeScript Project Setup

This guide explains how to set up cli-code-analyzer for JavaScript and TypeScript projects.

## Prerequisites

- Node.js 14+
- npm or yarn
- ESLint (optional, for linting)
- TypeScript (optional, for type checking)
- PMD (optional, for duplicate code detection)

## Quick Start

```bash
python main.py --language javascript --path /path/to/your/project
```

## Available Rules

| Rule | Description | Supports |
|------|-------------|----------|
| `max_lines_per_file` | Checks file length against warning/error thresholds | JS, TS, JSX, TSX |
| `pmd_duplicates` | Detects duplicate code blocks (requires PMD) | JS, TS |
| `eslint_analyze` | Linting with ESLint (800+ rules available) | JS, TS, JSX, TSX |
| `tsc_analyze` | TypeScript type checking via `tsc --noEmit` (requires TypeScript) | TS, TSX |

## Supported File Extensions

- `.js` - JavaScript
- `.mjs` - ES modules
- `.cjs` - CommonJS modules
- `.ts` - TypeScript
- `.tsx` - TypeScript with JSX
- `.jsx` - JavaScript with JSX

## Example Configuration

Create a `code_analysis_rules.json` file in your project:

```json
{
  "log_level": "all",
  "max_lines_per_file": {
    "enabled": true,
    "warning": 300,
    "error": 500
  },
  "pmd_duplicates": {
    "enabled": true,
    "minimum_tokens": 100,
    "exclude_patterns": {
      "javascript": ["**/node_modules/**", "**/dist/**", "**/build/**"],
      "typescript": ["**/node_modules/**", "**/dist/**", "**/build/**"]
    }
  },
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
      "no-undef": "error"
    },
    "exclude_patterns": ["node_modules/**", "dist/**", "build/**", "coverage/**"]
  }
}
```

## ESLint Configuration Modes

The `config_mode` option controls how ESLint configuration is handled:

| Mode | Behavior |
|------|----------|
| `auto` (default) | Use project's eslint.config.js/.eslintrc if exists, otherwise use rules.json settings |
| `builtin` | Ignore project config, use `--no-eslintrc` with rules.json settings |
| `project` | Require existing project config, fail if not found |

### Auto Mode (Recommended)

In `auto` mode, ESLint will:
1. Look for project-level ESLint config files (`eslint.config.js`, `.eslintrc.*`, `package.json` with `eslintConfig`)
2. If found, use the project config
3. If not found, use the rules defined in `rules.json`

### Builtin Mode

Use `builtin` mode when you want consistent analysis across projects regardless of their individual ESLint configs:

```json
{
  "eslint_analyze": {
    "enabled": true,
    "config_mode": "builtin",
    "env": {
      "browser": true,
      "es2021": true
    },
    "rules": {
      "no-unused-vars": "warn",
      "no-undef": "error",
      "semi": ["error", "always"]
    }
  }
}
```

### Project Mode

Use `project` mode when you want to enforce that projects must have their own ESLint configuration:

```json
{
  "eslint_analyze": {
    "enabled": true,
    "config_mode": "project"
  }
}
```

## TypeScript Type Checking (tsc_analyze)

The `tsc_analyze` rule runs `tsc --noEmit` to catch type errors that ESLint misses — wrong types passed to functions, null safety issues, missing properties, and cross-file type inconsistencies. ESLint is a linter (style/patterns); `tsc` is a type checker (correctness). They are complementary.

**Disabled by default** since not all JavaScript projects use TypeScript. Enable it in your rules JSON:

```json
{
  "tsc_analyze": {
    "enabled": true,
    "tsconfig": "./tsconfig.json"
  }
}
```

### Requirements

- TypeScript installed in your project: `npm install --save-dev typescript`
- A `tsconfig.json` in your project root

### Configuration

| Option | Description | Default |
|--------|-------------|---------|
| `enabled` | Enable/disable the rule | `false` |
| `tsconfig` | Path to tsconfig.json (relative to project) | `./tsconfig.json` |

## TypeScript-Specific Notes (ESLint)

For TypeScript projects, ESLint works out of the box for basic linting. For advanced TypeScript-specific rules, your project should have:

1. **typescript-eslint** installed:
   ```bash
   npm install --save-dev @typescript-eslint/parser @typescript-eslint/eslint-plugin
   ```

2. **ESLint config** with TypeScript support (example `.eslintrc.json`):
   ```json
   {
     "parser": "@typescript-eslint/parser",
     "plugins": ["@typescript-eslint"],
     "extends": [
       "eslint:recommended",
       "plugin:@typescript-eslint/recommended"
     ]
   }
   ```

When using `config_mode: "auto"` or `config_mode: "project"`, the analyzer will use your project's TypeScript-aware ESLint configuration.

## Exclusion Patterns

Common patterns to exclude from analysis:

| Pattern | Purpose |
|---------|---------|
| `node_modules/**` | npm dependencies |
| `dist/**` | Build output |
| `build/**` | Build output (alternative) |
| `coverage/**` | Test coverage reports |
| `.git/**` | Git repository data |
| `*.min.js` | Minified files |
| `*.bundle.js` | Bundled files |

## Example Batch Files (Windows)

Create a `tools` subfolder in your project and place the batch files there.

> **Note:** Do not add `pause` at the end of batch files. These scripts are designed to be called by other tools and `pause` would block execution.

### Analyze Code

Create `tools/analyze_code.bat`:

```batch
@echo off
d:
cd "d:\path\to\cli-code-analyzer"

call venv\Scripts\python.exe main.py --language javascript --path "D:\path\to\your\project" --verbosity minimal --output "D:\path\to\your\project\code_analysis_results" --maxamountoferrors 50 --rules "D:\path\to\your\project\code_analysis_rules.json"

cd %~dp0..
```

## CLI Options

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--language` | `-l` | Set to `javascript` | Required |
| `--path` | `-p` | Path to project directory or file | Required |
| `--rules` | `-r` | Path to rules JSON file | `rules.json` |
| `--verbosity` | `-v` | Output level: `minimal`, `normal`, `verbose` | `normal` |
| `--output` | `-o` | Folder for CSV/TXT reports | None (console) |
| `--loglevel` | `-L` | Filter: `error`, `warning`, `all` | `all` |
| `--maxamountoferrors` | `-m` | Limit violations in CSV | Unlimited |
| `--list-files` | `-f` | List all analyzed file paths after analysis | Off |

## Troubleshooting

### ESLint not found

If you get an ESLint path error:
1. Install ESLint in your project: `npm install --save-dev eslint` (auto-discovered from `node_modules/.bin/`)
2. Or install ESLint globally: `npm install -g eslint`
3. Or run the analyzer once - it will prompt to configure the ESLint path
4. Or manually edit `settings.ini` in the cli-code-analyzer directory

### PMD not found

If you get a PMD path error:
1. Run the analyzer once - it will prompt to download/configure PMD
2. Or manually edit `settings.ini` in the cli-code-analyzer directory

### TypeScript parsing errors

If ESLint reports parsing errors on TypeScript files:
1. Ensure your project has `@typescript-eslint/parser` installed
2. Configure your project's ESLint to use the TypeScript parser
3. Or use `config_mode: "builtin"` for basic JavaScript-only linting

### tsc not found

If you get a tsc path error:
1. Install TypeScript in your project: `npm install --save-dev typescript` (auto-discovered from `node_modules/.bin/`)
2. Or install TypeScript globally: `npm install -g typescript`
3. Or run the analyzer once - it will prompt to configure the tsc path
4. Or manually edit `settings.ini` in the cli-code-analyzer directory

### Exclusions not working

- Ensure patterns use forward slashes (`/`) even on Windows
- Use `**` for recursive matching
- Check that node_modules is properly excluded

## Common ESLint Rules

When using `config_mode: "builtin"`, you can configure these common rules:

| Rule | Description |
|------|-------------|
| `no-unused-vars` | Disallow unused variables |
| `no-undef` | Disallow undeclared variables |
| `semi` | Require/disallow semicolons |
| `quotes` | Enforce quote style |
| `no-console` | Disallow console.log |
| `eqeqeq` | Require === and !== |
| `curly` | Require curly braces |
| `no-var` | Require let/const instead of var |
| `prefer-const` | Prefer const over let |

See https://eslint.org/docs/rules/ for all available rules.
