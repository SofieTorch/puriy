from fixtures import edge_geometry, make_trace

from routebuilder.config import ConsensusConfig
from routebuilder.graph import (
    build_support_graph,
    compute_localized_support,
    prune_graph,
)
from routebuilder.types import DirectedEdge


def test_build_counts_distinct_traces_not_occurrences():
    traces = [make_trace(f"t{i}", [1, 2, 3]) for i in range(3)]
    graph = build_support_graph(traces)
    assert graph.node_weight(DirectedEdge(2, True)) == 3
    assert graph.arc_support(DirectedEdge(1, True), DirectedEdge(2, True)) == 3


def test_localized_support_is_fair_to_partial_traces():
    # 2 full traces + 4 traces covering only the first half: edges in
    # the second half are supported by 2/2 covering traces (frac 1.0),
    # not 2/6.
    full = [make_trace(f"full{i}", list(range(1, 21))) for i in range(2)]
    partial = [make_trace(f"part{i}", list(range(1, 11))) for i in range(4)]
    graph = build_support_graph(full + partial)
    compute_localized_support(graph, full + partial)

    tail_edge = DirectedEdge(18, True)
    assert graph.node_weight(tail_edge) == 2
    assert graph.coverage[tail_edge] == 2
    assert graph.support_frac[tail_edge] == 1.0


def test_prune_drops_single_trace_cross_street_keeps_shared_detour():
    # 6 traces on the corridor; one has a GPS-jump cross-street (edge
    # 100, off-corridor); three share a real detour (edges 200, 201).
    detour_geo = {
        200: [edge_geometry(5)[1], (edge_geometry(5)[1][0], edge_geometry(5)[1][1] + 0.0009)],
        201: [(edge_geometry(5)[1][0], edge_geometry(5)[1][1] + 0.0009), edge_geometry(6)[1]],
    }
    cross_geo = {100: [edge_geometry(3)[1], (edge_geometry(3)[1][0], edge_geometry(3)[1][1] - 0.0009)]}

    clean = [make_trace(f"c{i}", list(range(1, 11))) for i in range(2)]
    noisy = [make_trace("noisy", [1, 2, 3, 100, 4, 5, 6, 7, 8, 9, 10], geometries=cross_geo)]
    detour = [
        make_trace(f"d{i}", [1, 2, 3, 4, 5, 200, 201, 6, 7, 8, 9, 10], geometries=detour_geo)
        for i in range(3)
    ]
    traces = clean + noisy + detour
    graph = build_support_graph(traces)
    compute_localized_support(graph, traces)
    pruned, diag = prune_graph(graph)

    assert DirectedEdge(100, True) not in pruned.nodes  # cross-street died
    assert DirectedEdge(200, True) in pruned.nodes      # shared detour survived
    assert DirectedEdge(201, True) in pruned.nodes
    assert diag["pruned_count"] == 1


def test_prune_respects_min_support_abs():
    config = ConsensusConfig(min_support_abs=2, support_frac_min=0.5)
    traces = [
        make_trace("a", [1, 2, 3, 4, 5, 6]),
        make_trace("b", [1, 2, 3, 4, 5, 6]),
        make_trace("c", [1, 2, 99, 3, 4, 5, 6], geometries={99: edge_geometry(2)}),
    ]
    graph = build_support_graph(traces)
    compute_localized_support(graph, traces, config)
    pruned, _ = prune_graph(graph, config)
    assert DirectedEdge(99, True) not in pruned.nodes
    assert DirectedEdge(3, True) in pruned.nodes
