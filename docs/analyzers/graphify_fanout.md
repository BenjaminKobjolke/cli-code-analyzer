# Graphify Fan-Out Analyzer

## Overview

The graphify fan-out analyzer flags classes with **high outgoing coupling** — a class that
depends on many other things while little depends back on it (the "greedy consumer" shape). It
reads a pre-built [graphify](https://github.com/) directed graph (`graphify-out/graph.json`) and
applies smarts a raw dependency count lacks:

- **Hub exclusion** — edges to centralized constant registries (endpoints, route names, i18n keys)
  are mandated and healthy; they do **not** count as fan-out. Hubs come from the configured
  `hub_classes` list **plus** an auto-detected set of the highest-fan-in nodes.
- **Fan-in ratio** — a class is only an offender if `fan_in / fan_out < ratio_max`. High fan-out
  **and** high fan-in is a shared hub (base class, DTO) and is left alone.
- **Domain floor** — per-file `exceptions` raise the threshold for classes that legitimately touch
  many endpoints (e.g. a document controller).

It complements structural coupling tools: for Python, `pyscn_analyze` already reports per-class CBO.
This analyzer is language-agnostic (works for any language graphify can parse) and adds the
hub/ratio/floor heuristics that stock coupling counts do not have.

## Supported Languages

Any language graphify parses. Registered for: php, python, flutter, csharp, javascript, svelte.

## Dependencies

**A graphify graph must already exist** at `graph_path` (default `graphify-out/graph.json`). The
analyzer does **not** build or refresh the graph — build it yourself first, e.g.:

```bash
graphify src --directed
```

If the analyzer is enabled but the graph is missing, it emits a single **WARNING** (visible in the
console and in `graphify_fanout.csv`) telling you to install graphify and build the graph. It never
fails the run for a missing graph.

## Configuration

```json
{
  "graphify_fanout": {
    "enabled": false,
    "warning": 20,
    "error": 32,
    "ratio_max": 0.25,
    "graph_path": "graphify-out/graph.json",
    "hub_classes": ["ApiEndpoints", "RouteNames", "TranslationKeys", "UrlPaths"],
    "hub_autodetect": true,
    "hub_autodetect_percentile": 95,
    "exceptions": []
  }
}
```

### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enabled` | boolean | false | Enable/disable this analyzer (opt-in) |
| `warning` | int | 20 | Fan-out warning threshold (after hub exclusion) |
| `error` | int | 32 | Fan-out error threshold (after hub exclusion) |
| `ratio_max` | float | 0.25 | Max `fan_in / fan_out` for a class to count as an offender. At/above this it's treated as a healthy hub and skipped |
| `graph_path` | string | `graphify-out/graph.json` | Graph location, relative to `--path` |
| `hub_classes` | array | `[]` | Class/label names whose incoming edges are excluded from everyone's fan-out (your constant registries) |
| `hub_autodetect` | boolean | true | Also treat the highest-fan-in nodes as hubs automatically |
| `hub_autodetect_percentile` | int | 95 | Fan-in percentile at/above which a node is auto-treated as a hub (only nodes with fan-in > 1) |
| `exceptions` | array | `[]` | Per-file threshold overrides (see below) |

### Hub detection

Two independent knobs decide what is *not* an offender:

- **`hub_classes` + `hub_autodetect`** control *which edges don't count* — edges pointing at a hub
  are removed from the source's fan-out. Use `hub_classes` for named constant registries;
  auto-detect catches base classes / shared DTOs by their high fan-in.
- **`ratio_max`** controls *which classes are spared* even with high fan-out — anything with enough
  fan-in of its own.

### Per-File Exceptions

Exceptions follow the standard BaseRule pattern (same as `pyscn_analyze` / `dart_code_linter`) —
per-file `warning`/`error` overrides:

```json
"graphify_fanout": {
  "warning": 20,
  "error": 32,
  "exceptions": [
    { "file": "*/InvoiceDocumentController.php", "warning": 40, "error": 60 },
    { "file": "AppExtension.php", "warning": 30 }
  ]
}
```

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
graphify fan-out: 5 offender(s)
  Controller/InvoiceDocumentController.php
    [fan-out] 'InvoiceDocumentController' fan-out 30 (fan-in 1, ratio 0.03) >= 20 - high outgoing coupling; prefer an injected collaborator or a config object over many direct dependencies
```

### CSV Output (`graphify_fanout.csv`)

| Column | Description |
|--------|-------------|
| file_path | File path as recorded in the graph (`source_file`) |
| line | Node's declaration line (from graphify `source_location`), if known |
| severity | ERROR or WARNING |
| message | `[fan-out]` finding with the class name, fan-out, fan-in, and ratio |

## How Fan-Out Is Counted

For each node, **effective fan-out** = outgoing edges that are **neither**:
- structural containment (`contains` — a file node holding its own class), **nor**
- pointed at a hub (configured or auto-detected).

A node is reported when `effective_fan_out >= warning` **and** `fan_in / effective_fan_out < ratio_max`.
Nodes without a `source_file` (external types, interfaces) are never reported, but can still act as
hub targets.

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
- Never builds the graph — reads `graph_path` as-is. A stale graph gives stale results; rebuild it
  after code changes.
- The fixes this analyzer points at (inject a collaborator; bundle config into a value object) are
  documented as coding rules in `coding-rules` (`COMMON_RULES.md` → "Inject Collaborators, Don't
  Fold Dependencies In", plus the PHP and Flutter language files).
