# phpmd_analyze

## Overview

Runs PHP Mess Detector (PHPMD) over PHP files using its `codesize` and `design` rulesets. The
analyzer reports supported cyclomatic complexity, NPath complexity, excessive method length,
and excessive parameter count findings with their function names and source locations.

It is registered for PHP scans and is enabled by default when its rule entry is absent. Set
`enabled` to `false` to opt out. PHPMD 3 is included in the analyzer's PHP Composer development
dependencies. From the analyzer checkout, run `cd php && composer install` (or `php/install.bat`)
to install it under `php/vendor/bin`. The analyzer checks that bundled executable first, then
falls back to an external `phpmd` on `PATH`, a Composer-installed executable in the analyzed
project's `vendor/bin`, the configured settings path, or the interactive path prompt. To install
PHPMD in a PHP project, run `composer require --dev phpmd/phpmd`; project-local discovery checks
the bare launcher and Composer's `.bat`/`.cmd` Windows launchers after PATH and `node_modules/.bin`.
The Composer executable wrapper uses the PHP selected by the calling project's `PATH`. If PHPMD is
unavailable or returns invalid output, the analyzer reports a failed rule result instead of treating
the scan as clean.

## Configuration

```json
"phpmd_analyze": {
  "enabled": true,
  "log_level": "warning",
  "exclude_patterns": ["vendor/**", "generated/**"]
}
```

The PHPMD rulesets are currently fixed to `codesize,design`. Rule-level severity filtering,
the global log level, and the maximum-finding limit apply as for other analyzers.

`exclude_patterns` accepts a flat list of PHP path patterns or a language-keyed object such as
`{"php": ["vendor/**", "generated/**"]}`. The configured patterns are added to the default
excludes, so `vendor` remains excluded even when no setting is provided. The project root stays
the PHPMD scan target, which keeps application PHP files in scope.

## Windows workers, timeout, and cache

On Windows the analyzer passes `--threads=1` to PHPMD so PDepend parses files without starting
parallel worker processes. Other platforms keep PDepend's default thread behavior. Each PHPMD
subprocess is bounded by the analyzer's existing 300-second timeout; if it expires, PHPMD is
reported as failed with a timeout message instead of leaving the analyzer waiting indefinitely.

PDepend prefers a writable user cache (`XDG_CACHE_HOME` or `HOME/.cache`) and only falls back to
the system temporary directory when that cache is unavailable. Redirecting `TEMP` or `TMP` alone
may therefore leave PDepend's cache on the original drive. When diagnosing disk-space failures,
check the active PDepend cache location as well as the system temporary directory.

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

Each default folder is passed with both `/` and `\` separators (for example,
`*/vendor/*,*\vendor\*`), because PHPMD matches those patterns against the raw operating-system
path. Additional configured patterns are also passed to PHPMD's `--exclude` option.
