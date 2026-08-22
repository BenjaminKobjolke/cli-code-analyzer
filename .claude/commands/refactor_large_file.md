---
description: Safely refactor a file flagged by max_lines_per_file into smaller cohesive units, or justify an exception

argument-hint: file path (optional)
---

The user's target is: $ARGUMENTS

## 1. Pick target

If $ARGUMENTS names a file, use it. Otherwise read
@code_analysis_results/line_count_report.csv (`file,line_count,threshold,severity`),
list the flagged files worst-first, and ask the user which to take (or take the single
worst one if there's only one). Determine the file's language from its extension /
the project.

## 2. Decide split vs exception — before touching code

Read the target file completely and judge whether it is genuinely cohesive. If it's a
data model, config class, generated code, test suite, or API/DTO contract — matching
the Valid Reasons already listed in @prompts/setup_files/code_analysis.md — do NOT
split it. Instead propose an exception in @code_analysis_rules.json using that same
file's `exceptions` format (`file`, `warning`, `error`, `reason`) and wait for the
user's approval before adding it. Reuse the Valid/Invalid reason lists there rather
than re-deriving them. Otherwise continue to step 3.

## 3. Orient (optional)

Only if `graphify-out/graph.json` already exists in this project, run
`graphify explain "<name>"` and/or `graphify query "<name> callers usages" --budget 1000`
for a quick dependency map. If it doesn't exist, skip this step entirely — do not build
a graph and do not read `graph.json` directly.

## 4. Verify in source

- Read the target file fully.
- Grep every usage of the class/functions in it, including any public method that
  might move.
- Read the important callers and dependencies, and any relevant tests.
- Skim a sibling file in the same area for the project's existing naming/architecture
  conventions.

Do not start editing until you understand the public API, shared state, lifecycle,
callers, and test coverage.

## 5. Find responsibility boundaries

Cluster the file's code by responsibility: persistence, networking/API, validation,
parsing, formatting, caching, state management, domain logic, filesystem, UI,
lifecycle, method groups sharing the same state, duplicated logic.

Avoid: `Utils`/`Helpers`/`Common` dumping grounds, one-method classes with no real
abstraction, unnecessary interfaces or DI, splitting for stylistic reasons alone.

A flagged line count is a reason to investigate, not a mandate to split — if the file
is genuinely cohesive, go back to step 2's exception path instead of forcing a split.

## 6. Execute incrementally

Write a short ordered extraction plan, then execute it immediately. Per extraction:
keep public behavior compatible, update imports/callers, run the project's tests and
lint/static-analysis, fix all regressions before starting the next extraction. Add a
characterization test before changing behavior that isn't already covered.

## 7. Preserve behavior

Unless clearly necessary, don't change public APIs, observable behavior, serialization
formats, persistence behavior, lifecycle semantics, or error/exception behavior, and
don't add new dependencies. If a public API change looks necessary, check all callers
first.

## 8. Verify with the analyzer

Re-run the analyzer on the touched files and confirm:
- `max_lines_per_file` no longer errors on the target file, and
- no new violations appeared — especially `pmd_duplicates` (extraction can duplicate
  code) and any complexity/coupling analyzers for the project's language.

Prefer the project's own runner if present (e.g. `tools\analyze_changed_and_new_files.bat`,
which uses `--only-changed`), otherwise run a scoped check directly, e.g.:

```
venv\Scripts\python.exe main.py --language <lang> --path <target> --only-analyzer max_lines_per_file pmd_duplicates
```

Then review the complete diff — no duplicate implementations left behind, each new
unit has one responsibility, original file genuinely easier to understand — and
summarize: what was extracted and why, public API changes if any, checks run,
before/after line counts, and any exception proposed instead.
