# Svelte Project Setup

This guide explains how to set up cli-code-analyzer for Svelte and SvelteKit projects.

## Prerequisites

- Node.js 14+
- npm or yarn
- ESLint with `eslint-plugin-svelte` (for linting)
- `svelte-check` (for TypeScript/Svelte type checking)
- PMD (optional, for duplicate code detection)

## Quick Start

```bash
python main.py --language svelte --path /path/to/your/project
```

## Available Rules

| Rule | Description | Supports |
|------|-------------|----------|
| `max_lines_per_file` | Checks file length against warning/error thresholds | `.svelte` |
| `pmd_duplicates` | Detects duplicate code blocks (requires PMD) | `.svelte` |
| `eslint_analyze` | Linting with ESLint + eslint-plugin-svelte | `.svelte` |
| `svelte_check` | TypeScript/Svelte type checking (requires svelte-check) | `.svelte`, `.ts`, `.js` |

## Supported File Extensions

- `.svelte` - Svelte components

## ESLint Setup for Svelte

Your Svelte project needs `eslint-plugin-svelte` installed and configured for ESLint to process `.svelte` files.

### Install

```bash
npm install --save-dev eslint eslint-plugin-svelte
```

### Configure

For flat config (`eslint.config.js`):

```js
import svelte from 'eslint-plugin-svelte';

export default [
  ...svelte.configs['flat/recommended'],
  // your other config
];
```

For legacy config (`.eslintrc.json`):

```json
{
  "extends": ["plugin:svelte/recommended"]
}
```

## svelte-check Setup

`svelte-check` provides TypeScript type checking and Svelte-specific diagnostics. Most SvelteKit projects already have it installed.

### Install

```bash
npm install --save-dev svelte-check
```

### Configuration

The analyzer uses `--output machine` for parseable output and `--tsconfig` to locate your TypeScript config. Configure the tsconfig path in `rules.json`:

```json
{
  "svelte_check": {
    "enabled": true,
    "tsconfig": "./tsconfig.json"
  }
}
```

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
      "svelte": ["**/node_modules/**", "**/dist/**", "**/build/**", "**/.svelte-kit/**"]
    }
  },
  "eslint_analyze": {
    "enabled": true,
    "config_mode": "auto",
    "extensions": [".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".svelte"],
    "exclude_patterns": ["node_modules/**", "dist/**", "build/**", ".svelte-kit/**"]
  },
  "svelte_check": {
    "enabled": true,
    "tsconfig": "./tsconfig.json"
  }
}
```

## Default Exclusion Patterns

The following directories are excluded by default for Svelte projects:

| Pattern | Purpose |
|---------|---------|
| `node_modules/**` | npm dependencies |
| `dist/**` | Build output |
| `build/**` | SvelteKit build output |
| `.svelte-kit/**` | SvelteKit generated files |
| `.git/**` | Git repository data |

## CLI Options

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--language` | `-l` | Set to `svelte` | Required |
| `--path` | `-p` | Path to project directory or file | Required |
| `--rules` | `-r` | Path to rules JSON file | `rules.json` |
| `--verbosity` | `-v` | Output level: `minimal`, `normal`, `verbose` | `normal` |
| `--output` | `-o` | Folder for CSV/TXT reports | None (console) |
| `--loglevel` | `-L` | Filter: `error`, `warning`, `all` | `all` |
| `--maxamountoferrors` | `-m` | Limit violations in CSV | Unlimited |
| `--list-files` | `-f` | List all analyzed file paths after analysis | Off |

## Example Batch Files (Windows)

Create a `tools` subfolder in your project and place the batch files there.

> **Note:** Do not add `pause` at the end of batch files. These scripts are designed to be called by other tools and `pause` would block execution.

### Analyze Code

Create `tools/analyze_code.bat`:

```batch
@echo off
d:
cd "d:\path\to\cli-code-analyzer"

call venv\Scripts\python.exe main.py --language svelte --path "D:\path\to\your\project" --verbosity minimal --output "D:\path\to\your\project\code_analysis_results" --maxamountoferrors 50 --rules "D:\path\to\your\project\code_analysis_rules.json"

cd %~dp0..
```

## Troubleshooting

### ESLint "Parsing error: Unexpected token <" on .svelte files

This means ESLint is trying to parse `.svelte` files without the Svelte parser. Either:
1. Install and configure `eslint-plugin-svelte` in your ESLint config, then add `".svelte"` to the `extensions` array in your `eslint_analyze` rules config
2. Or remove `".svelte"` from `extensions` (it's not included by default) — Svelte-specific checks are better handled by `svelte_check`

### ESLint not finding svelte files

Ensure `eslint-plugin-svelte` is installed in your project and your ESLint config extends the Svelte plugin. You must also add `".svelte"` to the `extensions` array in your `eslint_analyze` rules config. Without both the plugin and the extension configured, ESLint will not process `.svelte` files.

### ESLint not found

If you get an ESLint path error:
1. Install ESLint in your project: `npm install --save-dev eslint` (auto-discovered from `node_modules/.bin/`)
2. Or install ESLint globally: `npm install -g eslint`
3. Or run the analyzer once - it will prompt to configure the ESLint path
4. Or manually edit `settings.ini` in the cli-code-analyzer directory

### svelte-check not found

If you get a svelte-check path error:
1. Install in your project: `npm install --save-dev svelte-check` (auto-discovered from `node_modules/.bin/`)
2. Or run the analyzer once - it will prompt to configure the svelte-check path
3. Or manually edit `settings.ini` in the cli-code-analyzer directory

### PMD not found

If you get a PMD path error:
1. Run the analyzer once - it will prompt to download/configure PMD
2. Or manually edit `settings.ini` in the cli-code-analyzer directory

### .svelte-kit files being analyzed

Ensure `.svelte-kit/**` is in your exclusion patterns. This is included by default but may need to be added to custom rules files.
