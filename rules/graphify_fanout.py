"""Graphify fan-out rule — flags classes with high *outgoing* coupling.

Reads a graphify directed graph (`graphify-out/graph.json`) and reports nodes
whose fan-out is high while their fan-in is low — the "greedy consumer" shape a
raw dependency count misses. The smarts a plain coupling count lacks live here:

- **Hub exclusion** — edges to centralized constant registries (endpoints, route
  names, i18n keys) are mandated and healthy; they are not counted as fan-out.
  Hubs come from the configured `hub_classes` list plus an auto-detected set of
  the highest-fan-in nodes (config + auto-detect fallback).
- **Fan-in ratio** — a class is only an offender if fan_in / fan_out is below
  `ratio_max`. High fan-out + high fan-in is a shared hub (base class, DTO) and
  is left alone.
- **Domain floor** — per-file `exceptions` raise the threshold for classes that
  legitimately touch many endpoints (e.g. a document controller).

The rule never builds the graph. If it is enabled but the graph is missing, it
emits a single WARNING so the report/CSV tells the user to install graphify and
build the graph.
"""

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from models import RuleResult, Severity, Violation
from rules.base import ProjectWideRule

# Relation kinds that are structural containment (file -> its own class), not real
# outgoing coupling. Excluding them keeps file-container nodes off the report.
_STRUCTURAL_RELATIONS = {'contains'}


class GraphifyFanoutRule(ProjectWideRule):
    """Project-wide rule: flag high fan-out / low fan-in classes from a graphify graph."""

    rule_name = 'graphify_fanout'

    def _run(self, _file_path: Path) -> RuleResult:
        self.logger.info("\nRunning graphify fan-out analysis...")

        graph_rel = self.config.get('graph_path', 'graphify-out/graph.json')
        graph_path = self.base_path / graph_rel

        if not graph_path.exists():
            # Enabled but no graph: surface a visible warning (report + CSV) rather
            # than a silent skip — the user opted in and needs to know why it's blank.
            msg = (f"graphify graph not found at '{graph_rel}'. Install graphify and build the "
                   f"graph (e.g. `graphify src --directed`) to enable fan-out analysis.")
            self.logger.warning(msg)
            return self._ok([Violation(file_path=graph_rel, rule_name=self.rule_name,
                                       severity=Severity.WARNING, message=msg)])

        try:
            data = json.loads(graph_path.read_text(encoding='utf-8'))
        except Exception as e:
            return self._failed(f"could not read graphify graph '{graph_path}': {e}")

        nodes = data.get('nodes') or []
        links = data.get('links') or data.get('edges') or []
        violations = self._analyze(nodes, links)
        violations = self._filter_violations_by_log_level(violations)

        if violations:
            self.logger.info(f"graphify fan-out: {len(violations)} offender(s)")
        else:
            self.logger.info("graphify fan-out: no offenders")

        return self._ok(violations)

    # --- core analysis (pure; unit-tested directly) ---------------------------

    def _analyze(self, nodes: list[dict], links: list[dict]) -> list[Violation]:
        label = {n.get('id'): n.get('label') for n in nodes}
        source = {n.get('id'): n.get('source_file') for n in nodes}
        loc = {n.get('id'): n.get('source_location') for n in nodes}

        # graphify emits one node per method (`.foo()`) separate from its class
        # node, so PHP method-body dependencies attach to method nodes, not the
        # class. Counting fan-out per raw node therefore scatters a class's real
        # coupling across its methods and undercounts it. Roll every node up to
        # its owning *unit* (its source_file; external types keep their own id)
        # and count DISTINCT external units, so five calls to the same collaborator
        # count once and method edges land on the class that owns them.
        def unit(nid: Any) -> Any:
            return source.get(nid) or nid

        file_units = {sf for sf in source.values() if sf}
        hub_units = self._hub_units(nodes, label, links, unit)

        # Distinct external units each unit depends on / is depended on by.
        # Intra-unit edges (method -> own class/method) are cohesion, not fan-out.
        out_targets: dict[Any, set] = defaultdict(set)
        in_sources: dict[Any, set] = defaultdict(set)
        for e in links:
            su, tu = unit(e.get('source')), unit(e.get('target'))
            if su == tu:
                continue
            in_sources[tu].add(su)
            if e.get('relation') in _STRUCTURAL_RELATIONS:
                continue
            if tu in hub_units:
                continue
            out_targets[su].add(tu)

        ratio_max = float(self.config.get('ratio_max', 0.25))
        rep = self._unit_reps(nodes, label, source)

        violations: list[Violation] = []
        for u, targets in out_targets.items():
            if u not in file_units:
                continue  # external/interface unit with no file — nothing to point at
            out = len(targets)
            fin = len(in_sources.get(u, ()))
            ratio = (fin / out) if out else 0.0
            if ratio >= ratio_max:
                continue  # healthy hub or well-balanced

            severity, threshold = self._severity_for(Path(u), out)
            if severity is None:
                continue

            rep_nid = rep.get(u)
            name = label.get(rep_nid) or Path(str(u)).stem
            violations.append(Violation(
                file_path=u,
                rule_name=self.rule_name,
                severity=severity,
                message=(f"[fan-out] '{name}' fan-out {out} (fan-in {fin}, ratio {ratio:.2f}) "
                         f">= {int(threshold)} - high outgoing coupling; prefer an injected "
                         f"collaborator or a config object over many direct dependencies"),
                line=self._parse_line(loc.get(rep_nid)),
            ))
        return violations

    def _hub_units(self, nodes: list[dict], label: dict, links: list[dict], unit) -> set:
        """Hub = configured constant registry OR (auto-detect) a top-percentile fan-in unit.

        Fan-in is measured per unit (distinct external dependants), matching the
        unit-level fan-out roll-up in `_analyze`.
        """
        configured = set(self.config.get('hub_classes', []))
        hub_units = {unit(n.get('id')) for n in nodes if label.get(n.get('id')) in configured}

        if self.config.get('hub_autodetect', True):
            pct = float(self.config.get('hub_autodetect_percentile', 95))
            fan_in: dict[Any, set] = defaultdict(set)
            for e in links:
                su, tu = unit(e.get('source')), unit(e.get('target'))
                if su != tu:
                    fan_in[tu].add(su)
            values = sorted(len(v) for v in fan_in.values() if v)
            if values:
                idx = min(len(values) - 1, int(len(values) * pct / 100))
                cutoff = values[idx]
                # Only meaningful when a unit is a genuine sink; ignore tiny graphs.
                for u, srcs in fan_in.items():
                    if len(srcs) >= cutoff and len(srcs) > 1:
                        hub_units.add(u)
        return hub_units

    def _unit_reps(self, nodes: list[dict], label: dict, source: dict) -> dict:
        """Pick a representative node per file-unit for reporting — prefer the class
        node (label that is neither a method '()' nor the bare '.php' file node) so
        the finding anchors on the class declaration line, not a random method."""
        rep: dict[Any, Any] = {}

        def is_class(nid: Any) -> bool:
            lbl = str(label.get(nid) or '')
            return not lbl.endswith('()') and not lbl.endswith('.php')

        for n in nodes:
            nid = n.get('id')
            sf = source.get(nid)
            if not sf:
                continue
            cur = rep.get(sf)
            if cur is None or (is_class(nid) and not is_class(cur)):
                rep[sf] = nid
        return rep

    def _severity_for(self, file_path: Path, value: int) -> tuple[Severity | None, float | None]:
        thresholds = self._get_threshold_for_file(file_path, self.config)
        error_t = thresholds.get('error')
        warning_t = thresholds.get('warning')
        if error_t is not None and value >= error_t:
            return Severity.ERROR, error_t
        if warning_t is not None and value >= warning_t:
            return Severity.WARNING, warning_t
        return None, None

    @staticmethod
    def _parse_line(location: Any) -> int | None:
        """graphify stores locations like 'L12'; extract the number if present."""
        if isinstance(location, str) and location.startswith('L') and location[1:].isdigit():
            return int(location[1:])
        return None
