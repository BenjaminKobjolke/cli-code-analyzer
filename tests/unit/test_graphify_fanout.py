"""Tests for the graphify fan-out rule."""

import json

from models import RuleStatus, Severity
from rules.context import RuleContext
from rules.graphify_fanout import GraphifyFanoutRule


def _rule(config, base_path):
    return GraphifyFanoutRule(RuleContext(config=config, base_path=base_path))


# A tiny directed graph mirroring the real shape:
#   hub      -> high fan-in, must be SPARED
#   greedy   -> high fan-out, fan-in 1, must be FLAGGED
#   consts   -> a configured constant registry; edges to it must NOT count as fan-out
#   balanced -> equal out/in, ratio >= ratio_max, must be SPARED
def _sample_graph():
    nodes = [
        {'id': 'hub', 'label': 'BaseController', 'source_file': 'a.php', 'source_location': 'L1'},
        {'id': 'greedy', 'label': 'GreedyController', 'source_file': 'b.php', 'source_location': 'L5'},
        {'id': 'consts', 'label': 'ApiEndpoints', 'source_file': 'c.php', 'source_location': 'L1'},
        {'id': 'balanced', 'label': 'Service', 'source_file': 'd.php', 'source_location': 'L1'},
    ]
    links = []
    # 25 distinct sinks the greedy class depends on (real coupling)
    for i in range(25):
        nodes.append({'id': f'dep{i}', 'label': f'Dep{i}', 'source_file': f'dep{i}.php'})
        links.append({'source': 'greedy', 'target': f'dep{i}', 'relation': 'references'})
    # greedy also touches the constant hub 5x — must be excluded from fan-out
    for _ in range(5):
        links.append({'source': 'greedy', 'target': 'consts', 'relation': 'references'})
    # hub is depended on by many (high fan-in) and depends on 22 things (high fan-out too)
    for i in range(30):
        links.append({'source': f'user{i}', 'target': 'hub', 'relation': 'extends'})
    for i in range(22):
        links.append({'source': 'hub', 'target': f'hdep{i}', 'relation': 'references'})
    # balanced: out 21, in 21 -> ratio 1.0
    for i in range(21):
        links.append({'source': 'balanced', 'target': f'bdep{i}', 'relation': 'references'})
        links.append({'source': f'bin{i}', 'target': 'balanced', 'relation': 'references'})
    return nodes, links


def _base_config():
    return {'warning': 20, 'error': 32, 'ratio_max': 0.25,
            'hub_classes': ['ApiEndpoints'], 'hub_autodetect': True,
            'hub_autodetect_percentile': 95}


def test_flags_greedy_spares_hub_and_balanced(tmp_path):
    nodes, links = _sample_graph()
    rule = _rule(_base_config(), tmp_path)
    violations = rule._analyze(nodes, links)
    # "Flagged as a greedy consumer" = the [fan-out] finding, distinct from the
    # INFO [chokepoint] note a high-fan-in hub may still get.
    fanout = {v.file_path for v in violations if '[fan-out]' in v.message}

    assert 'b.php' in fanout, "greedy consumer must be flagged"
    assert 'a.php' not in fanout, "high fan-in hub must be spared from the fan-out finding"
    assert 'd.php' not in fanout, "balanced (ratio >= max) must be spared from the fan-out finding"
    # greedy fan-out is 25 (const-hub edges excluded), a warning not an error
    greedy = next(v for v in violations if v.file_path == 'b.php')
    assert greedy.severity == Severity.WARNING
    assert 'fan-out 25' in greedy.message


def test_constant_hub_edges_excluded(tmp_path):
    """Without hub exclusion greedy would count 30 out; with it, 25 (below error=32)."""
    nodes, links = _sample_graph()
    rule = _rule(_base_config(), tmp_path)
    greedy = next(v for v in rule._analyze(nodes, links) if v.file_path == 'b.php')
    assert 'fan-out 25' in greedy.message  # 30 raw - 5 to ApiEndpoints


def test_domain_floor_exception_raises_threshold(tmp_path):
    nodes, links = _sample_graph()
    config = _base_config()
    config['exceptions'] = [{'file': 'b.php', 'warning': 40, 'error': 60}]
    rule = _rule(config, tmp_path)
    flagged = {v.file_path for v in rule._analyze(nodes, links)}
    assert 'b.php' not in flagged, "raised per-file floor should spare the domain leaf"


def _method_graph():
    """A class split into class-node + method-nodes, mirroring how graphify emits
    PHP. The class's real coupling lives on its METHOD nodes, not the class node."""
    nodes = [
        {'id': 'svc', 'label': 'Service', 'source_file': 'svc.php', 'source_location': 'L1'},
        {'id': 'svc.m1', 'label': 'm1()', 'source_file': 'svc.php'},
        {'id': 'svc.m2', 'label': 'm2()', 'source_file': 'svc.php'},
    ]
    links = [
        {'source': 'svc', 'target': 'svc.m1', 'relation': 'contains'},
        {'source': 'svc', 'target': 'svc.m2', 'relation': 'contains'},
        {'source': 'svc.m1', 'target': 'svc.m2', 'relation': 'calls'},  # intra-unit, not fan-out
    ]
    # class node: 2 constructor deps; methods: 20 more with a 4-way overlap between m1/m2
    for i in range(2):
        nodes.append({'id': f'dep{i}', 'label': f'Dep{i}', 'source_file': f'dep{i}.php'})
        links.append({'source': 'svc', 'target': f'dep{i}', 'relation': 'references'})
    for i in range(2, 14):
        nodes.append({'id': f'dep{i}', 'label': f'Dep{i}', 'source_file': f'dep{i}.php'})
        links.append({'source': 'svc.m1', 'target': f'dep{i}', 'relation': 'references'})
    for i in range(10, 22):  # dep10-13 overlap m1 -> must de-dupe to distinct units
        if i >= 14:
            nodes.append({'id': f'dep{i}', 'label': f'Dep{i}', 'source_file': f'dep{i}.php'})
        links.append({'source': 'svc.m2', 'target': f'dep{i}', 'relation': 'references'})
    return nodes, links


def _method_config():
    return {'info': 15, 'warning': 20, 'error': 32, 'ratio_max': 0.25,
            'hub_classes': [], 'hub_autodetect': True, 'hub_min_fanin': 25}


def test_rolls_method_edges_up_to_owning_class(tmp_path):
    """The bug: per-node counting saw class-node 2, m1 12, m2 12 — none >= 20, so the
    class was never flagged. Rolled up + de-duped it is 22 distinct external units."""
    nodes, links = _method_graph()
    violations = _rule(_method_config(), tmp_path)._analyze(nodes, links)
    svc = next((v for v in violations if v.file_path == 'svc.php'), None)
    assert svc is not None, "class coupling must roll up from its method nodes"
    assert 'fan-out 22' in svc.message, "distinct external units: dep0..dep21 (overlap de-duped)"
    assert '[fan-out]' in svc.message
    assert svc.severity == Severity.WARNING


def test_info_tier_flags_below_warning(tmp_path):
    """A class between info (15) and warning (20) surfaces quietly as INFO."""
    nodes = [{'id': 'c', 'label': 'C', 'source_file': 'c.php', 'source_location': 'L1'}]
    links = []
    for i in range(16):  # 16 distinct deps: >= info 15, < warning 20
        nodes.append({'id': f'd{i}', 'label': f'D{i}', 'source_file': f'd{i}.php'})
        links.append({'source': 'c', 'target': f'd{i}', 'relation': 'references'})
    v = _rule(_method_config(), tmp_path)._analyze(nodes, links)
    c = next(x for x in v if x.file_path == 'c.php')
    assert c.severity == Severity.INFO
    assert 'fan-out 16' in c.message


def test_chokepoint_high_both_surfaces_as_info(tmp_path):
    """High fan-out AND high fan-in is spared from [fan-out] but emitted as an INFO
    [chokepoint] so its cohesion still gets reviewed."""
    nodes = [{'id': 'k', 'label': 'Chokepoint', 'source_file': 'k.php', 'source_location': 'L1'}]
    links = []
    for i in range(24):  # out 24 (>= warning)
        nodes.append({'id': f'o{i}', 'label': f'O{i}', 'source_file': f'o{i}.php'})
        links.append({'source': 'k', 'target': f'o{i}', 'relation': 'references'})
    for i in range(24):  # in 24 -> ratio 1.0 >= ratio_max
        links.append({'source': f'in{i}', 'target': 'k', 'relation': 'references'})
    v = _rule(_method_config(), tmp_path)._analyze(nodes, links)
    k = next(x for x in v if x.file_path == 'k.php')
    assert k.severity == Severity.INFO
    assert '[chokepoint]' in k.message
    assert '[fan-out]' not in k.message


def test_absolute_hub_min_fanin_excludes_edges(tmp_path):
    """A unit depended on by >= hub_min_fanin distinct units is a hub; edges to it
    don't count toward anyone's fan-out."""
    nodes = [{'id': 'g', 'label': 'Greedy', 'source_file': 'g.php', 'source_location': 'L1'},
             {'id': 'hub', 'label': 'SharedHub', 'source_file': 'hub.php'}]
    links = []
    for i in range(20):  # greedy depends on 20 normal deps + the hub = 21 raw distinct
        nodes.append({'id': f'd{i}', 'label': f'D{i}', 'source_file': f'd{i}.php'})
        links.append({'source': 'g', 'target': f'd{i}', 'relation': 'references'})
    links.append({'source': 'g', 'target': 'hub', 'relation': 'references'})
    for i in range(30):  # hub has fan-in 30 >= hub_min_fanin 25 -> hub
        links.append({'source': f'u{i}', 'target': 'hub', 'relation': 'references'})
    v = _rule(_method_config(), tmp_path)._analyze(nodes, links)
    g = next(x for x in v if x.file_path == 'g.php')
    # 21 raw distinct - 1 hub = 20. The hub edge must NOT count: 'fan-out 20', not 21.
    assert 'fan-out 20' in g.message, "edge to the auto-detected hub must be excluded"


def test_missing_graph_emits_warning(tmp_path):
    rule = _rule(_base_config() | {'graph_path': 'graphify-out/graph.json'}, tmp_path)
    result = rule.check(tmp_path)
    assert result.status == RuleStatus.OK
    assert len(result.violations) == 1
    assert result.violations[0].severity == Severity.WARNING
    assert 'graphify' in result.violations[0].message.lower()


def test_reads_real_graph_file(tmp_path):
    nodes, links = _sample_graph()
    graph_dir = tmp_path / 'graphify-out'
    graph_dir.mkdir()
    (graph_dir / 'graph.json').write_text(
        json.dumps({'directed': True, 'nodes': nodes, 'links': links}), encoding='utf-8')

    rule = _rule(_base_config() | {'graph_path': 'graphify-out/graph.json'}, tmp_path)
    result = rule.check(tmp_path)
    assert result.status == RuleStatus.OK
    fanout = [v for v in result.violations if '[fan-out]' in v.message]
    assert any(v.file_path == 'b.php' for v in fanout)
    assert all(v.file_path != 'a.php' for v in fanout), "hub spared from fan-out finding"
