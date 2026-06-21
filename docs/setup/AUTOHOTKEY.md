# AutoHotkey Project Setup

This guide explains how to set up cli-code-analyzer for AutoHotkey projects.

## Prerequisites

- AutoHotkey v1 and/or v2 installed (https://www.autohotkey.com/). Only the
  version(s) your scripts use are required.

## Quick Start

```bash
python main.py --language autohotkey --path /path/to/your/project
# alias:
python main.py --language ahk --path /path/to/your/project
```

File extensions analyzed: `.ahk`, `.ah2`, `.ahk2`.

## Available Rules

| Rule | Description |
|------|-------------|
| `max_lines_per_file` | Checks file length against warning/error thresholds |
| `autohotkey_analyze` | Syntax/load validation via the real AHK interpreter (v1 & v2) |

## Interpreter configuration

On first run you are prompted for the interpreter path(s); they are stored in
`settings.ini`:

```ini
[autohotkey]
autohotkey_v2_path = C:\Program Files\AutoHotkey\v2\AutoHotkey64.exe
autohotkey_v1_path = C:\Program Files\AutoHotkey\AutoHotkeyU64.exe
```

The version is chosen per script: a `#Requires AutoHotkey v2` line selects v2,
otherwise v1. If the needed interpreter is not configured, that script's
validation is skipped (not a failure).

## How validation works

Only entry-point ("root") scripts are validated - those not `#Include`d by any
other file. Validating a root pulls in its whole include tree, and errors are
reported against the correct sub-file. Scripts are loaded and syntax-checked
**without being executed** (no GUI / app launch). See
`docs/analyzers/autohotkey_analyze.md` for details.

## Example Configuration

```json
{
  "log_level": "all",
  "max_lines_per_file": {
    "enabled": true,
    "warning": 300,
    "error": 500
  },
  "autohotkey_analyze": {
    "enabled": true
  }
}
```
