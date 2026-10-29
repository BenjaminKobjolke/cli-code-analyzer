# phpmd_analyze

## Overview

Runs PHP Mess Detector (PHPMD) over PHP files using its `codesize` and `design` rulesets. The
analyzer reports supported cyclomatic complexity, NPath complexity, excessive method length,
and excessive parameter count findings with their function names and source locations.

It is registered for PHP scans and is enabled by default when its rule entry is absent. Set
`enabled` to `false` to opt out. PHPMD is an optional external executable; install it and make
`phpmd` available on `PATH`, configure its path through the analyzer's settings, or provide it
when prompted. If PHPMD is unavailable or returns invalid output, the analyzer reports a failed
rule result instead of treating the scan as clean.

## Configuration

```json
"phpmd_analyze": {
  "enabled": true,
  "log_level": "warning"
}
```

The PHPMD rulesets are currently fixed to `codesize,design`. Rule-level severity filtering,
the global log level, and the maximum-finding limit apply as for other analyzers.
