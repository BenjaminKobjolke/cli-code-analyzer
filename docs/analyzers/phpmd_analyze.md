# phpmd_analyze

## Overview

Runs PHP Mess Detector (PHPMD) over PHP files using its `codesize` and `design` rulesets. The
analyzer reports supported cyclomatic complexity, NPath complexity, excessive method length,
and excessive parameter count findings with their function names and source locations.

It is registered for PHP scans and is enabled by default when its rule entry is absent. Set
`enabled` to `false` to opt out. PHPMD 3 is included in the analyzer's PHP Composer development
dependencies. From the analyzer checkout, run `cd php && composer install` (or `php/install.bat`)
to install it under `php/vendor/bin`. The analyzer checks that bundled executable first, then
falls back to an external `phpmd` on `PATH`, the configured settings path, or the interactive
path prompt. The Composer executable wrapper uses the PHP selected by the calling project's
`PATH`. If PHPMD is unavailable or returns invalid output, the analyzer reports a failed rule
result instead of treating the scan as clean.

## Configuration

```json
"phpmd_analyze": {
  "enabled": true,
  "log_level": "warning"
}
```

The PHPMD rulesets are currently fixed to `codesize,design`. Rule-level severity filtering,
the global log level, and the maximum-finding limit apply as for other analyzers.

## Excluded folders

PHPMD always skips the default PHP excludes from file discovery: `vendor`, `node_modules`,
`.git`, and `.phpstan-cache`. They are passed to PHPMD as `--exclude` patterns and match a
folder of that exact name at any depth, so a project with several Composer subprojects skips
every one of them:

```
project/
├── vendor/                 skipped
├── api/vendor/             skipped
├── tools/compat/vendor/    skipped
└── src/VendorService.php   analyzed (not a folder named vendor)
```

Each folder is passed with both `/` and `\` separators (`*/vendor/*,*\vendor\*`), because
PHPMD matches the patterns against the raw operating-system path. The list is fixed and cannot
be changed in the rules file.
