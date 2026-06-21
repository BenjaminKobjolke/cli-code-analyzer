# AutoHotkey Analyzer

## Overview

The AutoHotkey analyzer validates AutoHotkey scripts by running the **real AHK
interpreter** in load-but-don't-execute mode and reporting the syntax/load errors
it finds. There is no mature standalone AHK linter, so leaning on the interpreter
gives accurate, zero-false-positive results instead of regex guesswork.

It supports both **AutoHotkey v1 and v2**, selected per script.

## Supported Languages

AutoHotkey only (`--language autohotkey`, alias `ahk`). File extensions: `.ahk`,
`.ah2`, `.ahk2`.

## How it works

AutoHotkey projects are built from `#Include`d sub-files that are not valid in
isolation. So the analyzer:

1. Discovers every AHK file and scans `#Include` / `#IncludeAgain` directives to
   build an include graph.
2. Validates only **root scripts** (entry points not included by any other file).
   Validating a root pulls in its whole include tree; errors are still reported
   against the correct sub-file and line.
3. Detects the version per root: a `#Requires AutoHotkey v2` line => v2, otherwise
   v1.
4. Runs the matching interpreter and parses its stderr.

### Invocation (verified on v1.1.37 and v2.0.10)

```
v2:  AutoHotkey64.exe  /ErrorStdOut=UTF-8 /validate "<root>.ahk"
v1:  AutoHotkeyU64.exe /iLib "<discard>"  /ErrorStdOut    "<root>.ahk"
```

Both **load and syntax-check without executing** the script (no GUI, no app
launch), write errors to stderr, and exit `2` on error / `0` when clean. The
interpreter runs with its working directory set to the root's folder so relative
`#Include`s resolve (required for v1). AutoHotkey is a GUI-subsystem program, so
its error output is only visible when captured via a pipe - which the analyzer
does.

> Do **not** run `/ErrorStdOut` without `/validate` (v2) or `/iLib` (v1): that
> executes the script and launches valid apps.

## Dependencies

AutoHotkey must be installed (download: https://www.autohotkey.com/). Configure
the interpreter paths in `settings.ini` (prompted on first run):

```ini
[autohotkey]
autohotkey_v2_path = C:\Program Files\AutoHotkey\v2\AutoHotkey64.exe
autohotkey_v1_path = C:\Program Files\AutoHotkey\AutoHotkeyU64.exe
```

Only the version(s) your scripts use are required. If a needed interpreter is not
configured, validation for those roots is **skipped** (not a failure).

## Configuration

```json
{
  "autohotkey_analyze": {
    "enabled": true
  }
}
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enabled` | boolean | true | Enable/disable this analyzer |

## Output

### Console
```
Running AutoHotkey validation...
AutoHotkey: 1 issue(s) found
```

### CSV (`autohotkey_analyze.csv`)

| Column | Description |
|--------|-------------|
| file | Relative file path of the offending script |
| line | Line number |
| severity | Always ERROR (syntax/load failures) |
| message | Interpreter error text (incl. the `Specifically:` detail) |

## Example Usage

```bash
python main.py --language autohotkey --path ./src
python main.py --language ahk --path ./src --output ./reports
python main.py --list-analyzers autohotkey
```

## Notes

- Runs once per analysis run (project-wide), validating each root script.
- Under `--only-changed` / `--file`, only roots whose include tree contains a
  changed file are validated.
- Include resolution matches by file name (handles `<Lib>`, `%A_ScriptDir%\...`,
  and relative paths) - a precise path resolver is only needed if this misfires.
