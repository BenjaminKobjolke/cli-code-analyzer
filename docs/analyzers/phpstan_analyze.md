# PHPStan Analyzer

## Overview

The PHPStan analyzer runs PHPStan against PHP projects and reports static
analysis errors in `phpstan_analyze.csv`. It supports full-project runs and
changed-file filtering via `--only-changed` / `--file`.

## Dependencies

PHPStan must be available either from the bundled `php/vendor/bin` directory or
from PATH / configured tool settings.

## Configuration

```json
{
  "phpstan_analyze": {
    "enabled": true,
    "level": 5,
    "memory_limit": "1G",
    "bootstrap_files": ["tools/phpstan-bootstrap.php"],
    "config_file": "phpstan.neon",
    "exclude_patterns": ["vendor/**", "node_modules/**", ".git/**"]
  }
}
```

## Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enabled` | boolean | false | Enable/disable this analyzer |
| `level` | number | 5 | PHPStan analysis level, 0-9 |
| `memory_limit` | string | `"1G"` | PHP memory limit passed to PHPStan |
| `bootstrap_files` | array | [] | PHP files loaded before analysis, usually for project autoload setup |
| `config_file` | string | unset | Existing PHPStan NEON config to include |
| `exclude_patterns` | array | [] | Glob patterns converted to PHPStan `excludePaths` |
| `analyze_path` | string/array | project root | Path or paths analyzed in full-project mode |

## Bootstrap Files

Use `bootstrap_files` when a project needs its own autoloader, constants, or
framework registration before PHPStan can resolve classes. The analyzer writes a
temporary PHPStan config that includes these files and still applies
`exclude_patterns`.

Example bootstrap:

```php
<?php

define('ROOT', dirname(__DIR__));
require_once ROOT . '/vendor/autoload.php';
require_once ROOT . '/app/autoload.php';
```

## Existing PHPStan Config

Use `config_file` when the project already has a `phpstan.neon`. The analyzer
includes that file from its generated temporary config so project settings,
bootstrap files, and generated excludes can be used together.

## CSV Output

| Column | Description |
|--------|-------------|
| file | Relative file path |
| line | Line number reported by PHPStan |
| severity | Always `error` |
| identifier | PHPStan rule identifier, when available |
| message | PHPStan message |
| ignorable | PHPStan ignorable flag |
