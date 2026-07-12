# Graphify Fan-Out Analyzer

## Overview

The graphify fan-out analyzer flags classes with **high outgoing coupling** — a class that
depends on many other things while little depends back on it (the "greedy consumer" shape). It
reads a pre-built [graphify](https://github.com/) directed graph (`graphify-out/graph.json`) and
applies smarts a raw dependency count lacks:

- **Class roll-up (distinct units)** — graphify emits a separate node per method (`.foo()`) beside
  the class node, so a class's real dependencies (used inside method bodies) scatter across its
  method nodes. The analyzer rolls every node up to its owning **unit** (its `source_file`) and
  counts **distinct external units**, so method-body edges land on the owning class and five calls
  to the same collaborator count once. Intra-unit edges (a method calling its own class) are
  cohesion, not fan-out, and are dropped.
- **Hub exclusion** — edges to widely-shared units (constant registries, base classes, entities)
  are mandated and healthy; they do **not** count as fan-out. Hubs come from the configured
  `hub_classes` list **plus** an auto-detected set of high-fan-in units (`hub_min_fanin`).
- **Fan-in ratio** — a class is only a greedy-consumer offender if `fan_in / fan_out < ratio_max`.
  High fan-out **and** high fan-in is a chokepoint (base class, DTO); it is spared the `[fan-out]`
  finding but surfaced as an INFO `[chokepoint]` note when its absolute fan-out still clears the
  warning bar.
- **Severity tiers** — `error` / `warning` / `info` thresholds, so borderline classes just under
  the warning line stay visible (INFO) instead of vanishing.
- **Domain floor** — per-file `exceptions` raise the `info`/`warning`/`error` thresholds for classes
  that legitimately touch many units (e.g. a DI container, route file, document controller).

It complements structural coupling tools: for Python, `pyscn_analyze` already reports per-class CBO.
This analyzer is language-agnostic (works for any language graphify can parse) and adds the
hub/ratio/floor heuristics that stock coupling counts do not have.

## Supported Languages

Any language graphify parses. Registered for: php, python, flutter, csharp, javascript, svelte.

## Dependencies

**A graphify graph must exist** at `graph_path` (default `graphify-out/graph.json`). By default the
analyzer does **not** build the graph — build it yourself first:

```bash
graphify src --directed      # first build (directed is required for fan-out)
graphify update src          # refresh after code changes (re-extracts code, no LLM)
```

If the analyzer is enabled but the graph is missing, it emits a single **WARNING** (visible in the
console and in `graphify_fanout.csv`) telling you to install graphify and build the graph. It never
fails the run for a missing graph.

### Optional: auto-build before analysis (`auto_build`)

Set `auto_build: true` to refresh the graph at the start of each run so results are never stale.
It runs `graphify update <build_path>` (default `build_path: "src"`), which re-extracts code files
with no LLM and preserves the existing graph's directed flag. Override the command with
`build_command` (string or argv list). It **soft-fails**: a missing `graphify` binary or a failed
build logs a warning and falls through to the existing graph — it never breaks the analysis run.
Default is `false`, keeping the "reads the graph as-is" contract unless you opt in.

## Configuration

```json
{
  "graphify_fanout": {
    "enabled": false,
    "info": 15,
    "warning": 20,
    "error": 32,
    "ratio_max": 0.25,
    "graph_path": "graphify-out/graph.json",
    "hub_classes": ["ApiEndpoints", "RouteNames", "TranslationKeys", "UrlPaths"],
    "hub_autodetect": true,
    "hub_min_fanin": 25,
    "hub_autodetect_percentile": 99,
    "auto_build": false,
    "build_path": "src",
    "exceptions": []
  }
}
```

### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enabled` | boolean | false | Enable/disable this analyzer (opt-in) |
| `info` | int | 15 | Fan-out INFO threshold (after hub exclusion). Borderline classes surface quietly. Omit to disable the INFO tier |
| `warning` | int | 20 | Fan-out warning threshold (after hub exclusion) |
| `error` | int | 32 | Fan-out error threshold (after hub exclusion) |
| `ratio_max` | float | 0.25 | Max `fan_in / fan_out` for a class to be a greedy-consumer offender. At/above this it's a chokepoint — spared the `[fan-out]` finding, surfaced as INFO `[chokepoint]` if its fan-out clears `warning` |
| `graph_path` | string | `graphify-out/graph.json` | Graph location, relative to `--path` |
| `hub_classes` | array | `[]` | Class/label names whose incoming edges are excluded from everyone's fan-out (your constant registries) |
| `hub_autodetect` | boolean | true | Also treat high-fan-in units as hubs automatically |
| `hub_min_fanin` | int | 25 | **Absolute** cutoff: a unit depended on by ≥ this many distinct units is a hub. Tie-immune and predictable — preferred over the percentile |
| `hub_autodetect_percentile` | int | 99 | Fallback only, used when `hub_min_fanin` is unset. Fan-in percentile at/above which a unit is auto-treated as a hub (tie-fragile on distinct-unit fan-in — prefer `hub_min_fanin`) |
| `auto_build` | boolean | false | Refresh the graph via `graphify update <build_path>` before analyzing (soft-fails). See Dependencies |
| `build_path` | string | `src` | Path passed to `graphify update` when `auto_build` is on |
| `build_command` | string/array | — | Override the auto-build command entirely |
| `exceptions` | array | `[]` | Per-file threshold overrides — `info`/`warning`/`error` (see below) |

### Hub detection

Two independent knobs decide what is *not* an offender:

- **`hub_classes` + `hub_autodetect`** control *which edges don't count* — edges pointing at a hub
  are removed from the source's fan-out. Use `hub_classes` for named constant registries;
  auto-detect catches base classes / shared entities by their high fan-in.
- **`ratio_max`** controls *which classes are spared* even with high fan-out — anything with enough
  fan-in of its own (see the chokepoint note below).

**Auto-detect uses an absolute cutoff.** `hub_min_fanin` (default 25) means "depended on by 25+
distinct units → hub." This is predictable and tie-immune. The older `hub_autodetect_percentile` is
a fallback used only when `hub_min_fanin` is unset: on distinct-unit fan-in the distribution is
tie-heavy (many units share the same small fan-in), so a percentile cut sweeps in far too many
units. Prefer the absolute cutoff.

### Per-File Exceptions

Exceptions follow the standard BaseRule pattern (same as `pyscn_analyze` / `dart_code_linter`) —
per-file `info`/`warning`/`error` overrides:

```json
"graphify_fanout": {
  "info": 15,
  "warning": 20,
  "error": 32,
  "exceptions": [
    { "file": "*/InvoiceDocumentController.php", "info": 40, "warning": 40, "error": 60 },
    { "file": "*Routes.php", "info": 30, "warning": 30, "error": 50 }
  ]
}
```

> **Raise `info` too, not just `warning`/`error`.** An exception only overrides the tiers you list;
> the others fall back to the base config. For an accept-by-design file (DI container, route file),
> set `info` to the same floor as `warning` — otherwise the base `info` threshold still flags it at
> the lower level and it keeps nagging as INFO.

> **Caveat — match on filename or glob, not a full path.** The offender's file path is graphify's
> `source_file`, which is relative to the graph's own source root (e.g.
> `Controller/InvoiceDocumentController.php`), **not** the analyzer's `--path`. Path matching tries
> base-relative, rules.json-relative, and filename-only, so a **glob**
> (`*/InvoiceDocumentController.php`) or a **filename** (`InvoiceDocumentController.php`) matches
> reliably. A path anchored at the project root (`src/Controller/InvoiceDocumentController.php`) may
> not match, because the graph path omits the `src/` prefix.

## Output Format

### Console
```
Running graphify fan-out analysis...
graphify fan-out: 3 offender(s)
  Service/LeadDuplicationService.php
    [fan-out] 'LeadDuplicationService' fan-out 26 (fan-in 4, ratio 0.15) >= 20 - high outgoing coupling; prefer an injected collaborator or a config object over many direct dependencies
  Service/OrderConfirmationService.php
    [chokepoint] 'OrderConfirmationService' fan-out 23 AND fan-in 21 (ratio 0.91) - high both; spared as a hub, but review whether the 23 outgoing deps are one cohesive job or many
```

Two finding kinds:
- **`[fan-out]`** — a greedy consumer (`ratio < ratio_max`), severity ERROR / WARNING / INFO by
  which threshold its fan-out clears.
- **`[chokepoint]`** — high fan-out **and** high fan-in (`ratio >= ratio_max`), always INFO. Spared
  the greedy-consumer finding but flagged for a cohesion review. Only emitted when fan-out ≥ `warning`.

### CSV Output (`graphify_fanout.csv`)

| Column | Description |
|--------|-------------|
| file_path | File path as recorded in the graph (`source_file`) |
| line | The class node's declaration line (from graphify `source_location`), if known |
| severity | ERROR, WARNING, or INFO |
| message | `[fan-out]` or `[chokepoint]` finding with the class name, fan-out, fan-in, and ratio |

## How Fan-Out Is Counted

Every graph node is rolled up to its **unit** — its `source_file` (external types with no file keep
their own id). This folds a class's method nodes (`.foo()`) back into the class they belong to.

For each unit, **effective fan-out** = the count of **distinct external units** it points at,
excluding edges that are:
- structural containment (`contains` — a file node holding its own class),
- **intra-unit** (a method calling its own class/another method — cohesion, not coupling), or
- pointed at a hub (configured `hub_classes` or auto-detected via `hub_min_fanin`).

Fan-in is measured the same way: distinct external units that depend on this unit.

A unit is reported as `[fan-out]` when `effective_fan_out >= info` (tiered up to warning/error)
**and** `fan_in / effective_fan_out < ratio_max`. When the ratio is `>= ratio_max` but fan-out still
clears `warning`, it is reported as an INFO `[chokepoint]` instead. Units with no `source_file`
(external types, interfaces) are never reported, but can still act as hub targets.

## Interpreting fan-in vs fan-out (why high-both is not a free pass)

`ratio_max` spares a high-fan-out class when it also has high fan-in. That is a **triage
heuristic, not a verdict** — it stops the analyzer drowning you in base classes, but it can hide a
real god class. Read the two numbers as two different risks:

- **Fan-out** = the class's own dependencies. High fan-out is bad *always* — many reasons for the
  class to break, hard to test in isolation. High fan-in does **not** cancel this.
- **Fan-in** = how many things depend on the class. High fan-in is not the class's own coupling; it
  is **blast radius** — how much breaks when you change it.
- **High both** = a chokepoint, the *worst* ripple position, not a healthy one: change propagates
  *both* directions (it breaks when its deps change, and its dependents break when it changes). The
  only thing high fan-in adds is that refactoring it is scarier, so the analyzer defers to you — it
  does not certify the class as fine.

The number is smoke; **cohesion of the outgoing edges is the fire.** A base controller with 32
outgoing deps is acceptable *only if* those edges are one coherent responsibility — framework
plumbing every controller needs (`render`, `api`, `session`, `logger`, `flash`, `csrf`). The same
32 edges spread across unrelated business concerns is a god class regardless of fan-in. The
analyzer cannot judge cohesion; when a high-fan-in class is spared by `ratio_max`, open it and ask:
*is the fan-out one job, or many?*

Robert Martin's instability metric frames the same idea:

```
I = fan-out / (fan-in + fan-out)
```

- `I` near 0 (high in, low out) → **stable** — correct for a base class / shared library. ✓
- `I` near 1 (low in, high out) → **unstable** — fine for app edges / entry points.
- `I` near 0.5 with **high absolute numbers** → chokepoint. Common in base classes, but only OK if
  the fan-out is cohesive; otherwise it is a genuine refactor target the ratio filter will hide.

**Practical takeaway:** treat a `ratio_max`-spared class as *deferred*, not *cleared*. If it also
trips other signals (max lines, CBO from `pyscn_analyze`, many public methods), the high fan-in is
not protecting you — it is raising the stakes.

## Example Usage

```bash
# Build the graph first (graphify), then analyze
python main.py --language php --path ./my-project --rules rules.json

# With report output
python main.py --language php --path ./my-project --rules rules.json --output ./reports
```

## Notes

- Project-wide: executes once per analysis run, not per file.
- Whole-graph only: skipped under `--only-changed` / `--file` (a single changed file can't be
  re-scored without the whole graph), like `pyscn_analyze`.
- Reads `graph_path` as-is by default — a stale graph gives stale results, so rebuild it after code
  changes (or set `auto_build: true` to refresh automatically before each run).
- The fixes this analyzer points at (inject a collaborator; bundle config into a value object) are
  documented as coding rules in `coding-rules` (`COMMON_RULES.md` → "Inject Collaborators, Don't
  Fold Dependencies In", plus the PHP and Flutter language files).
