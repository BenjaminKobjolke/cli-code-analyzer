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
    flagged = {v.file_path for v in violations}

    assert 'b.php' in flagged, "greedy consumer must be flagged"
    assert 'a.php' not in flagged, "high fan-in hub must be spared"
    assert 'd.php' not in flagged, "balanced (ratio >= max) must be spared"
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
    assert any(v.file_path == 'b.php' for v in result.violations)
    assert all(v.file_path != 'a.php' for v in result.violations)
