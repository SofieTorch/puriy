from fixtures import corridor_point, edge_geometry, make_trace

from routebuilder.config import ConsensusConfig, RamalConfig, ReconstructionConfig
from routebuilder.consensus import run_cluster_consensus
from routebuilder.engine import reconstruct_from_matched
from routebuilder.graph import build_support_graph, compute_localized_support, prune_graph
from routebuilder.ramales import cluster_ramales, detect_divergence, split_by_divergence


def _branch_geometries(offset_north: int = 2):
    """Edges 200-202: leave the corridor at node 5, run one block
    north for two blocks, rejoin at node 8."""
    p5 = corridor_point(5)
    p8 = corridor_point(8)
    n5 = (p5[0], p5[1] + offset_north * 0.0009)
    n7 = (corridor_point(7)[0], corridor_point(7)[1] + offset_north * 0.0009)
    return {
        200: [p5, n5],
        201: [n5, n7],
        202: [n7, p8],
    }


BRANCH_IDS = [1, 2, 3, 4, 5, 200, 201, 202, 9, 10, 11, 12]
TRUNK_IDS = list(range(1, 13))


def test_far_apart_variants_cluster_separately():
    # Variant A on the corridor, variant B parallel 6 blocks north
    # (~540m, beyond the 200m Fréchet threshold).
    north_geo = {i: [
        (edge_geometry(i)[0][0], edge_geometry(i)[0][1] + 6 * 0.0009),
        (edge_geometry(i)[1][0], edge_geometry(i)[1][1] + 6 * 0.0009),
    ] for i in range(100, 113)}
    a = [make_trace(f"a{i}", list(range(1, 13))) for i in range(3)]
    b = [make_trace(f"b{i}", list(range(100, 113)), geometries=north_geo) for i in range(3)]
    groups = cluster_ramales(a + b)
    assert len(groups) == 2
    assert sorted(len(g.traces) for g in groups) == [3, 3]


def test_small_regime_lowers_min_cluster_size():
    a = [make_trace(f"a{i}", list(range(1, 13))) for i in range(2)]
    groups = cluster_ramales(a, RamalConfig(min_cluster_size=3))
    assert len(groups) == 1
    assert len(groups[0].traces) == 2


def test_clustering_never_returns_empty_for_nonempty_input():
    only = [make_trace("solo", list(range(1, 13)))]
    groups = cluster_ramales(only)
    assert len(groups) == 1
    assert groups[0].label == "main"


def test_divergence_detected_for_shared_trunk_variants():
    # 3 trunk traces + 3 branch traces sharing ~75% of the path:
    # Fréchet distance is small (~180m) so they may cluster together,
    # but the support graph shows two competing branches.
    geo = _branch_geometries()
    trunk = [make_trace(f"t{i}", TRUNK_IDS) for i in range(3)]
    branch = [make_trace(f"b{i}", BRANCH_IDS, geometries=geo) for i in range(3)]
    traces = trunk + branch

    config = ConsensusConfig()
    graph = build_support_graph(traces)
    compute_localized_support(graph, traces, config)
    pruned, _ = prune_graph(graph, config)
    result = run_cluster_consensus(traces, config=config)
    assert result.path is not None

    divergence = detect_divergence(pruned, result.path, traces, config)
    assert divergence is not None
    trunk_split, branch_split = split_by_divergence(traces, divergence)
    # With 3 traces on each variant the consensus path may follow
    # either side; the split must cleanly separate the two populations.
    sides = {
        frozenset(t.trace_id for t in trunk_split),
        frozenset(t.trace_id for t in branch_split),
    }
    assert sides == {frozenset({"t0", "t1", "t2"}), frozenset({"b0", "b1", "b2"})}


def test_no_divergence_for_single_noisy_trace():
    geo = _branch_geometries()
    trunk = [make_trace(f"t{i}", TRUNK_IDS) for i in range(5)]
    noisy = [make_trace("n0", BRANCH_IDS, geometries=geo)]
    traces = trunk + noisy

    config = ConsensusConfig()
    graph = build_support_graph(traces)
    compute_localized_support(graph, traces, config)
    pruned, _ = prune_graph(graph, config)
    result = run_cluster_consensus(traces, config=config)
    divergence = detect_divergence(pruned, result.path, traces, config)
    assert divergence is None  # 1 branch trace < divergence_min_traces


def _origin_b_geometries(north_blocks: int = 3):
    """Origin B of a head fork: starts `north_blocks` north of node 0, runs
    east, then drops onto the corridor at node 4 — where origin A's edges 1-4
    also arrive. Edges 100-103."""
    off = north_blocks * 0.0009
    def n(i):
        p = corridor_point(i)
        return (p[0], p[1] + off)
    return {
        100: [n(0), n(1)],
        101: [n(1), n(2)],
        102: [n(2), n(3)],
        103: [n(3), corridor_point(4)],
    }


def test_divergence_mode_two_complete_colinear_ramales():
    """Top-down ("divergence") discovery on two ~co-linear lines.

    Lines A and B have distinct origins (A: corridor edges 1-4; B: edges
    100-103 from the north) that merge at node 4 and then share the whole trunk
    + destination (edges 5-20). Coverage is *partial* — no single trace spans a
    full line — and some riders cover only the shared trunk, exactly the case
    bottom-up clustering over-fragments. The fix (top-down split + corridor
    spine + overlapping membership) must emit 2 ramales, each *complete*:
    reaching its own origin AND the shared destination.

    This mirrors the real "120 Univalle / Tiquipaya to UMSS" pair; keep it green
    when adding routes so the over-fragmentation / truncation can't regress.
    """
    geo_b = _origin_b_geometries()
    a_origin = [make_trace(f"a{i}", list(range(1, 13))) for i in range(3)]   # 1..12
    b_origin = [make_trace(f"b{i}", [100, 101, 102, 103] + list(range(5, 13)),
                           geometries=geo_b) for i in range(3)]              # origin B + 5..12
    shared = [make_trace(f"s{i}", list(range(8, 21))) for i in range(3)]     # 8..20 trunk+dest
    traces = a_origin + b_origin + shared

    config = ReconstructionConfig()
    config.ramales.discovery = "divergence"
    output = reconstruct_from_matched(traces, config=config, infer_direction=False)

    # Aggregate edges per ramal family (a split route may come back fragmented).
    by_label: dict[str, set[int]] = {}
    for r in output.routes:
        base = r.ramal_label.split(".")[0]
        by_label.setdefault(base, set()).update(ce.edge.edge_id for ce in r.edges)
    assert len(by_label) == 2, list(by_label)

    dest = {18, 19, 20}
    a_ram = [lab for lab, ids in by_label.items() if {1, 2, 3, 4} <= ids]
    b_ram = [lab for lab, ids in by_label.items() if {100, 101, 102, 103} <= ids]
    assert len(a_ram) == 1 and len(b_ram) == 1 and a_ram[0] != b_ram[0]
    # The crux: BOTH ramales ride the shared corridor all the way to the end,
    # not just the one whose traces happened to span furthest.
    assert dest <= by_label[a_ram[0]], f"A truncated: {sorted(by_label[a_ram[0]])}"
    assert dest <= by_label[b_ram[0]], f"B truncated: {sorted(by_label[b_ram[0]])}"


def test_engine_emits_two_ramales_for_divergent_cluster():
    geo = _branch_geometries()
    trunk = [make_trace(f"t{i}", TRUNK_IDS) for i in range(3)]
    branch = [make_trace(f"b{i}", BRANCH_IDS, geometries=geo) for i in range(3)]

    output = reconstruct_from_matched(trunk + branch, config=ReconstructionConfig())
    labels = sorted({r.ramal_label for r in output.routes})
    assert len(labels) == 2

    by_label = {r.ramal_label: r for r in output.routes}
    edge_sets = {label: {ce.edge.edge_id for ce in r.edges} for label, r in by_label.items()}
    # One variant uses the branch edges, the other the trunk edges.
    has_branch = [label for label, ids in edge_sets.items() if {200, 201, 202} <= ids]
    has_trunk = [label for label, ids in edge_sets.items() if {6, 7, 8} <= ids]
    assert len(has_branch) == 1
    assert len(has_trunk) == 1
    assert has_branch[0] != has_trunk[0]


def test_engine_single_ramal_for_agreeing_traces():
    traces = [make_trace(f"t{i}", list(range(1, 13))) for i in range(4)]
    output = reconstruct_from_matched(traces)
    assert len(output.routes) == 1
    assert output.routes[0].ramal_label == "main"
    assert output.diagnostics["direction_groups"] == 1


def test_terminal_fork_clusters_separately():
    # Two ramales share a trunk (edges 1-10) and fork at the end:
    # one continues east (11-16), the other turns north (300-305).
    # The fork is at the traces' ends — the old bounded-excursion
    # rule ignored it and merged them into one ramal.
    north_geo = {}
    base = corridor_point(10)
    for i in range(6):
        north_geo[300 + i] = [
            (base[0], base[1] + i * 0.0009),
            (base[0], base[1] + (i + 1) * 0.0009),
        ]
    east = [make_trace(f"e{i}", list(range(1, 17))) for i in range(3)]
    north = [make_trace(f"n{i}", list(range(1, 11)) + list(range(300, 306)),
                        geometries=north_geo) for i in range(3)]
    groups = cluster_ramales(east + north)
    assert len(groups) == 2
    members = sorted((frozenset(t.trace_id for t in g.traces) for g in groups), key=min)
    assert members == [frozenset({"e0", "e1", "e2"}), frozenset({"n0", "n1", "n2"})]


def test_partial_extent_is_not_a_fork():
    # One trace covers the full corridor, another only the first half:
    # same route, different extents — must stay one cluster.
    full = [make_trace(f"f{i}", list(range(1, 21))) for i in range(2)]
    half = [make_trace(f"h{i}", list(range(1, 11))) for i in range(2)]
    groups = cluster_ramales(full + half)
    assert len(groups) == 1
    assert len(groups[0].traces) == 4


def test_parallel_carriageway_split_is_rejected():
    # Two trace populations on parallel paths only ~30m apart (the two
    # carriageways of one avenue): competing branches with disjoint
    # trace sets, but NOT two ramales — the split must be rejected.
    near_geo = {}
    for i in range(4, 9):
        g = edge_geometry(i)
        near_geo[400 + i] = [
            (g[0][0], g[0][1] + 0.00027),  # ~30m north
            (g[1][0], g[1][1] + 0.00027),
        ]
    south = [make_trace(f"s{i}", list(range(1, 13))) for i in range(3)]
    north_ids = [1, 2, 3, 404, 405, 406, 407, 408, 9, 10, 11, 12]
    north = [make_trace(f"q{i}", north_ids, geometries=near_geo) for i in range(3)]

    output = reconstruct_from_matched(south + north, config=ReconstructionConfig())
    labels = {r.ramal_label for r in output.routes}
    assert labels == {"main"}, labels


def _route_from(label, edge_ids, traces, direction_group=0, geometries=None):
    from routebuilder.consensus import consensus_for_cluster

    routes, _ = consensus_for_cluster(
        traces, ramal_label=label, direction_group=direction_group
    )
    return routes[0]


def test_validation_drops_tiny_ramal():
    from routebuilder.engine import validate_ramales

    long_traces = [make_trace(f"l{i}", list(range(1, 21))) for i in range(3)]
    stub_traces = [make_trace(f"s{i}", [30, 31]) for i in range(3)]  # ~200m stub
    long_route = _route_from("main", None, long_traces)
    stub = _route_from("r2", None, stub_traces)

    config = ReconstructionConfig()
    traces_by_id = {t.trace_id: t for t in long_traces + stub_traces}
    kept, discarded = validate_ramales([long_route, stub], traces_by_id, config)
    assert [r.ramal_label for r in kept] == ["main"]
    assert discarded[0]["reason"] == "too_short"


def test_validation_never_empties_a_group():
    from routebuilder.engine import validate_ramales

    stub_traces = [make_trace(f"s{i}", [30, 31]) for i in range(2)]
    stub = _route_from("main", None, stub_traces)
    config = ReconstructionConfig()
    kept, discarded = validate_ramales([stub], {t.trace_id: t for t in stub_traces}, config)
    assert len(kept) == 1 and not discarded


def test_contained_subroute_needs_consistent_termini():
    from routebuilder.engine import validate_ramales

    config = ReconstructionConfig()
    # A→C: full corridor. A→B candidate: first half, fully contained.
    full_traces = [make_trace(f"f{i}", list(range(1, 25))) for i in range(4)]
    full = _route_from("main", None, full_traces)

    # Case 1: sub-route whose traces consistently span A→B (a real
    # ramal whose buses terminate at B) → kept.
    spanning = [make_trace(f"a{i}", list(range(1, 13))) for i in range(4)]
    sub_consistent = _route_from("r2", None, spanning)
    traces_by_id = {t.trace_id: t for t in full_traces + spanning}
    kept, discarded = validate_ramales([full, sub_consistent], traces_by_id, config)
    assert {r.ramal_label for r in kept} == {"main", "r2"}, discarded

    # Case 2: same geometry but scattered trace extents (partial rides
    # around a popular stop) → discarded as contained duplicate.
    scattered = [
        make_trace("p0", list(range(1, 13))),
        make_trace("p1", list(range(3, 13))),
        make_trace("p2", list(range(5, 11))),
        make_trace("p3", list(range(2, 9))),
    ]
    sub_scattered = _route_from("r2", None, scattered)
    traces_by_id = {t.trace_id: t for t in full_traces + scattered}
    kept, discarded = validate_ramales([full, sub_scattered], traces_by_id, config)
    assert {r.ramal_label for r in kept} == {"main"}
    assert discarded[0]["reason"] == "contained_without_consistent_termini"
    assert discarded[0]["contained_in"] == "main"


def test_fragments_of_kept_ramal_survive_lenient_floor():
    from routebuilder.engine import validate_ramales

    # main.1 (long) + main.2 (~400m, honest fragment) + main.3 (~100m debris)
    t1 = [make_trace(f"x{i}", list(range(1, 16))) for i in range(3)]
    t2 = [make_trace(f"y{i}", list(range(20, 25))) for i in range(3)]   # 4 edges ≈ 400m
    t3 = [make_trace(f"z{i}", [30, 31]) for i in range(3)]              # ≈ 200m? 2 edges=200m
    f1 = _route_from("main.1", None, t1)
    f2 = _route_from("main.2", None, t2)
    f3 = _route_from("main.3", None, t3)
    # shrink f3 below the 300m debris floor
    f3.geometry = f3.geometry[:2]

    config = ReconstructionConfig()
    traces_by_id = {t.trace_id: t for t in t1 + t2 + t3}
    kept, discarded = validate_ramales([f1, f2, f3], traces_by_id, config)
    assert {r.ramal_label for r in kept} == {"main.1", "main.2"}
    assert discarded[0]["label"] == "main.3"
    assert discarded[0]["reason"] == "fragment_debris"


def _fork_geometries():
    """Leg B (edges 100-106): a second origin leg joining the trunk at
    node 7, far from leg A — a Y-junction, not a mid-path bypass."""
    merge = corridor_point(7)
    pts = [(merge[0] - 0.012 + i * 0.012 / 7, merge[1] - 0.012 + i * 0.012 / 7)
           for i in range(8)]
    pts[-1] = merge
    return {100 + i: [pts[i], pts[i + 1]] for i in range(7)}


FORK_A_IDS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
FORK_B_IDS = [100, 101, 102, 103, 104, 105, 106, 8, 9, 10, 11, 12]


def test_terminal_fork_divergence_detected():
    # Two origin legs sharing a trunk and joining at one node. The
    # branch only JOINS the path (exit, no entry) — the bypass-only
    # detector skipped it; terminal-fork handling must catch it.
    geo = _fork_geometries()
    a = [make_trace(f"a{i}", FORK_A_IDS) for i in range(3)]
    b = [make_trace(f"b{i}", FORK_B_IDS, geometries=geo) for i in range(3)]
    traces = a + b

    config = ConsensusConfig()
    graph = build_support_graph(traces)
    compute_localized_support(graph, traces, config)
    pruned, _ = prune_graph(graph, config)
    result = run_cluster_consensus(traces, config=config)
    assert result.path is not None

    divergence = detect_divergence(pruned, result.path, traces, config)
    assert divergence is not None
    trunk_split, branch_split = split_by_divergence(traces, divergence)
    sides = {
        frozenset(t.trace_id for t in trunk_split),
        frozenset(t.trace_id for t in branch_split),
    }
    assert sides == {frozenset({"a0", "a1", "a2"}), frozenset({"b0", "b1", "b2"})}
