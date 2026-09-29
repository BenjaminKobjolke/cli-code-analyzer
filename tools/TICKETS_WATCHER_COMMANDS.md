# Version
1

<!-- Managed by `tickets-watcher --setup`. Replaced whole when the version above changes;
     edit the shipped template in the tickets-watcher repo, not this copy. -->

# Writing a batch file that works as a Tickets Watcher command

A `.bat` or `.cmd` under `tools/` can show up as a command button in the Tickets Watcher app —
either named in the watcher's `settings.json` under `commands`, or offered by the app's picker as
any runnable file. The run starts in the project root and the process exit code is the run's
result, so end with an explicit `exit /b <code>`.

## Never block on a human

- **No `pause`.** The watcher strips it, but any other caller (CI, another bat, an agent) hangs
  forever. A bat that must open on `set /p` or `choice` is rewritten so the question becomes an
  app prompt — see *Prompts* below.
- **No `start` without `/wait`.** The run would finish while the started work continues and its
  output is lost. Use `start /wait` if you must open a window.
- **No GUI window that waits for a click.** Nothing will click it.

## Prompts

- A `set /p` or `choice` **in the started `.bat` itself** becomes a question answerable from the
  phone app. Keep prompts in the top-level bat.
- A prompt in a **second bat reached through `call`** is not rewritten and blocks until the run
  times out. Pass answers to it as arguments instead of asking inside it.
- PowerShell `Read-Host`, `Get-Credential` and `PromptForChoice` are not supported.

## Child programs that ask for input

A child program keeps the run from hanging only if it says so itself:

- **Reads a line** (Python `input()`, Node readline): print `::tw-input-line::` on its own
  flushed line immediately before reading, and only when `TICKETS_WATCHER_COMMAND_RUN=1` is set,
  so a normal terminal run is unchanged.
- **Reads stdin until EOF** (`codex exec`, `claude -p` and similar agent CLIs): give it closed
  stdin — `<NUL` in a bat, `stdin=subprocess.DEVNULL` in Python — or it waits forever on the
  watcher's open pipe.

## Things that behave differently here

- `%~n0` / `%~nx0` see the temporary `.tw-run-*` copy name. `%~dp0` is safe.
- The run has a time limit (`commands.timeout_seconds`); time spent waiting for an answer does
  not count against it.
