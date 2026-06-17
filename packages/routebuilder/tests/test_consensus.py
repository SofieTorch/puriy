import pytest
from fixtures import corridor_point, edge_geometry, make_trace

from routebuilder.config import ConsensusConfig
from routebuilder.consensus import (
    assert_connected,
    consensus_for_cluster,
)
from routebuilder.types import ConsensusEdge, DirectedEdge


def test_clean_traces_reconstruct_exact_corridor():
    traces = [make_trace(f"t{i}", list(range(1, 21))) for i in range(4)]
    routes, diag = consensus_for_cluster(traces)
    assert len(routes) == 1
    route = routes[0]
    assert route.edge_keys == [DirectedEdge(i, True) for i in range(1, 21)]
    assert all(ce.confidence == 1.0 for ce in route.edges)
    assert route.geometry[0] == corridor_point(0)
    assert route.geometry[-1] == corridor_point(20)


def test_spurious_cross_street_is_rejected():
    # The failure mode from the old strategy: one trace's GPS jump
    # onto a cross-street must not appear in the consensus.
    cross_geo = {
        100: [edge_geometry(5)[1], (edge_geometry(5)[1][0], edge_geometry(5)[1][1] - 0.0009)],
        101: [(edge_geometry(5)[1][0], edge_geometry(5)[1][1] - 0.0009), edge_geometry(6)[1]],
    }
    clean = [make_trace(f"c{i}", list(range(1, 16))) for i in range(5)]
    noisy = make_trace(
        "noisy", [1, 2, 3, 4, 5, 100, 101, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15],
        geometries=cross_geo,
    )
    routes, _ = consensus_for_cluster(clean + [noisy])
    assert len(routes) == 1
    edge_ids = {ce.edge.edge_id for ce in routes[0].edges}
    assert 100 not in edge_ids and 101 not in edge_ids
    assert edge_ids == set(range(1, 16))


def test_shared_branch_outvotes_trunk_when_majority_uses_it():
    # 4 of 6 traces take a parallel block (edges 200-201) instead of
    # edges 5-6: the consensus should follow the majority.
    branch_geo = {
        200: [edge_geometry(4)[1], (corridor_point(5)[0], corridor_point(5)[1] + 0.0009)],
        201: [(corridor_point(5)[0], corridor_point(5)[1] + 0.0009), edge_geometry(7)[0]],
    }
    majority = [
        make_trace(f"m{i}", [1, 2, 3, 4, 200, 201, 7, 8, 9, 10], geometries=branch_geo)
        for i in range(4)
    ]
    minority = [make_trace(f"n{i}", list(range(1, 11))) for i in range(2)]
    routes, _ = consensus_for_cluster(majority + minority)
    assert len(routes) == 1
    edge_ids = [ce.edge.edge_id for ce in routes[0].edges]
    assert 200 in edge_ids and 201 in edge_ids
    assert 5 not in edge_ids and 6 not in edge_ids


def test_partial_traces_extend_to_full_supported_extent():
    # 2 traces cover the full route, 2 cover the first half, 2 the
    # second half: consensus must span the whole corridor.
    full = [make_trace(f"f{i}", list(range(1, 21))) for i in range(2)]
    head = [make_trace(f"h{i}", list(range(1, 11))) for i in range(2)]
    tail = [make_trace(f"l{i}", list(range(10, 21))) for i in range(2)]
    routes, _ = consensus_for_cluster(full + head + tail)
    assert len(routes) == 1
    edge_ids = [ce.edge.edge_id for ce in routes[0].edges]
    assert edge_ids == list(range(1, 21))


def test_disconnected_evidence_splits_into_fragments_not_fake_geometry():
    # Two trace groups on far-apart corridors with no connecting
    # evidence and no bridge function: emit fragments, never invent a
    # connection (the old strategy's blind-concatenation bug).
    near = [make_trace(f"a{i}", list(range(1, 8))) for i in range(3)]
    far = [make_trace(f"b{i}", list(range(50, 58))) for i in range(3)]
    # Force them into one cluster artificially by calling consensus on
    # the union — there is no arc between edge 7 and 50.
    routes, diag = consensus_for_cluster(near + far)
    # Either consensus fails cleanly, or every emitted fragment is
    # internally connected — geometry is never fabricated.
    if routes:
        for route in routes:
            assert_connected(route)
        assert len(routes) >= 2
    else:
        assert diag["failure"] in ("no_path", "no_endpoints")


def test_bridge_fn_repairs_small_gaps_as_inferred_edges():
    # Trace edges 1-5 and 7-10 observed, edge 6 missing from all
    # traces (e.g. tunnel): bridge function supplies it.
    traces = [
        make_trace(f"t{i}", [1, 2, 3, 4, 5, 7, 8, 9, 10]) for i in range(3)
    ]

    def bridge(gap_start, gap_end):
        return [ConsensusEdge(
            edge=DirectedEdge(6, True),
            geometry=[gap_start, gap_end],
            confidence=0.0,
            inferred=True,
        )]

    routes, _ = consensus_for_cluster(traces, bridge_fn=bridge)
    assert len(routes) == 1
    route = routes[0]
    inferred = [ce for ce in route.edges if ce.inferred]
    assert len(inferred) == 1
    assert inferred[0].edge.edge_id == 6
    assert_connected(route)


def test_connectivity_invariant_raises_on_bad_route():
    traces = [make_trace("t", [1, 2, 3, 4, 5, 9, 10])]  # gap 5->9, no bridge
    config = ConsensusConfig(min_support_abs=1, support_frac_min=0.0)
    routes, _ = consensus_for_cluster(traces, config=config)
    # Without a bridge the route must come out as 2 fragments, each
    # internally connected.
    assert len(routes) == 2
    for route in routes:
        assert_connected(route)
    labels = [r.ramal_label for r in routes]
    assert labels == ["main.1", "main.2"]


def test_low_trace_count_regime_three_traces():
    traces = [make_trace(f"t{i}", list(range(1, 11))) for i in range(3)]
    routes, _ = consensus_for_cluster(traces)
    assert len(routes) == 1
    assert [ce.edge.edge_id for ce in routes[0].edges] == list(range(1, 11))


def test_empty_cluster():
    routes, diag = consensus_for_cluster([])
    assert routes == []


def test_noise_cycle_is_broken_by_backtrack_constraint():
    # One trace doubles back (edges ... 5, 6, 5R-ish noise modelled as
    # jumping back to edge 3 then forward again). The consensus path
    # must remain monotonic along the corridor.
    weird = make_trace("w", [1, 2, 3, 4, 5, 6, 3, 4, 5, 6, 7, 8, 9, 10])
    clean = [make_trace(f"c{i}", list(range(1, 11))) for i in range(3)]
    routes, _ = consensus_for_cluster(clean + [weird])
    assert len(routes) == 1
    edge_ids = [ce.edge.edge_id for ce in routes[0].edges]
    assert edge_ids == list(range(1, 11))


if __name__ == "__main__":
    pytest.main([__file__, "-q"])


def test_straight_weld_merges_small_gaps_into_one_fragment():
    import math

    from routebuilder.consensus import assemble_routes
    from routebuilder.graph import SupportGraph

    # Two edges with a ~25m gap between A's end and B's start.
    lat = -17.3935
    dx = 25 / (111_320 * math.cos(math.radians(lat)))  # ~25m in lon degrees
    a = DirectedEdge(1, True)
    b = DirectedEdge(2, True)
    graph = SupportGraph()
    graph.geometries[a] = [(-66.157, lat), (-66.156, lat)]
    graph.geometries[b] = [(-66.156 + dx, lat), (-66.155, lat)]
    graph.support_frac = {a: 1.0, b: 1.0}

    # weld limit below the gap → fragments into two.
    split = assemble_routes([a, b], graph, config=ConsensusConfig(max_weld_gap_m=15.0))
    assert len(split) == 2

    # weld limit above the gap → one connected route.
    merged = assemble_routes([a, b], graph, config=ConsensusConfig(max_weld_gap_m=30.0))
    assert len(merged) == 1
    assert merged[0].diagnostics["welded_gaps"]  # recorded the weld
    assert_connected(merged[0], ConsensusConfig(max_weld_gap_m=30.0))


def test_merge_close_fragments_joins_nearby_same_ramal_pieces():
    import math

    from routebuilder.config import ConsensusConfig as CC
    from routebuilder.engine import merge_close_fragments
    from routebuilder.types import ConsensusRoute as CR

    lat = -17.3935
    def mk(label, x0, x1):
        return CR(ramal_label=label, direction_group=0, edges=[],
                  geometry=[(x0, lat), (x1, lat)], trace_count=3, trace_ids=["a","b","c"])
    # Two fragments 8m apart (8m ≈ 7.5e-5 deg lon), same ramal family.
    g = 8 / (111_320 * math.cos(math.radians(lat)))
    a = mk("main.1", -66.157, -66.156)
    b = mk("main.2", -66.156 + g, -66.155)
    far = mk("main.3", -66.150, -66.149)   # 600m away → stays separate
    merged, log = merge_close_fragments([a, b, far], CC(max_weld_gap_m=30.0))
    labels = sorted(r.ramal_label for r in merged)
    # main.1 + main.2 merge; main.3 stays → 2 routes
    assert len(merged) == 2, labels
    big = max(merged, key=lambda r: len(r.geometry))
    assert len(big.geometry) == 4  # both fragments' points concatenated
    assert log and log[0]["fragments"] == 2


def test_merge_keeps_far_fragments_separate():
    from routebuilder.config import ConsensusConfig as CC
    from routebuilder.engine import merge_close_fragments
    from routebuilder.types import ConsensusRoute as CR

    lat = -17.3935
    a = CR(ramal_label="main.1", direction_group=0, edges=[],
           geometry=[(-66.157, lat), (-66.156, lat)], trace_count=3)
    b = CR(ramal_label="main.2", direction_group=0, edges=[],
           geometry=[(-66.150, lat), (-66.149, lat)], trace_count=3)  # ~600m gap
    merged, log = merge_close_fragments([a, b], CC(max_weld_gap_m=30.0))
    assert len(merged) == 2 and not log


def _ll(dx_m, dy_m, lat=-17.3935):
    import math
    return (-66.157 + dx_m / (111_320 * math.cos(math.radians(lat))),
            lat + dy_m / 111_320)


def test_trace_stitch_follows_a_curved_gap():
    from routebuilder.config import ConsensusConfig as CC
    from routebuilder.engine import merge_close_fragments
    from routebuilder.types import ConsensusRoute as CR

    # An L-bend: fragment A heads east and stops; B starts to the north
    # and heads north. Non-collinear → straight-bridge must NOT fire;
    # the trace that drove the corner provides the geometry.
    a = CR(ramal_label="main.1", direction_group=0, edges=[],
           geometry=[_ll(0, 0), _ll(40, 0), _ll(80, 0)], trace_count=3, trace_ids=["t"])
    b = CR(ramal_label="main.2", direction_group=0, edges=[],
           geometry=[_ll(120, 40), _ll(120, 80), _ll(120, 120)], trace_count=3, trace_ids=["t"])
    corner = [_ll(0, 0), _ll(80, 0), _ll(120, 0), _ll(120, 40), _ll(120, 120)]
    merged, log = merge_close_fragments([a, b], CC(), trace_lines=[corner])
    assert len(merged) == 1
    # Follows the corner via the trace's elbow point (120, 0), not a
    # straight diagonal cut.
    assert any(abs(p[0] - _ll(120, 0)[0]) < 1e-9 and abs(p[1] - _ll(120, 0)[1]) < 1e-9
               for p in merged[0].geometry)
    assert log[0]["stitched"] == 1


def test_straight_bridge_connects_clear_gap_but_not_a_detour():
    from routebuilder.config import ConsensusConfig as CC
    from routebuilder.engine import merge_close_fragments
    from routebuilder.types import ConsensusRoute as CR

    # Collinear fragments along a straight east-west line, 60m gap.
    a = CR(ramal_label="main.1", direction_group=0, edges=[],
           geometry=[_ll(0, 0), _ll(40, 0), _ll(80, 0)], trace_count=3, trace_ids=["t"])
    b = CR(ramal_label="main.2", direction_group=0, edges=[],
           geometry=[_ll(140, 0), _ll(180, 0), _ll(220, 0)], trace_count=3, trace_ids=["t"])

    # A trace hugging the straight line (snap-spike < dev cap) → bridge.
    straight = [_ll(0, 0), _ll(80, 0), _ll(110, 15), _ll(140, 0), _ll(220, 0)]
    merged, log = merge_close_fragments([a, b], CC(), trace_lines=[straight])
    assert len(merged) == 1
    assert log[0]["bridged"] == 1 and log[0]["stitched"] == 0

    # A trace that detours ~120m off the line (around a block) → NOT
    # bridged, and no clean stitch endpoint either → stays split.
    a2 = CR(ramal_label="main.1", direction_group=0, edges=[],
            geometry=[_ll(0, 0), _ll(40, 0), _ll(80, 0)], trace_count=3, trace_ids=["t"])
    b2 = CR(ramal_label="main.2", direction_group=0, edges=[],
            geometry=[_ll(140, 0), _ll(180, 0), _ll(220, 0)], trace_count=3, trace_ids=["t"])
    detour = [_ll(80, 0), _ll(110, 120), _ll(140, 0)]
    merged2, _ = merge_close_fragments([a2, b2], CC(max_weld_gap_m=30.0), trace_lines=[detour])
    assert len(merged2) == 2


def test_dedrift_snaps_route_back_to_band():
    import math

    from routebuilder.config import ConsensusConfig as CC
    from routebuilder.engine import _BandIndex, _snap_route_to_band
    from routebuilder.types import ConsensusRoute as CR

    band = [[_ll(0, y) for y in range(0, 400, 10)] for _ in range(5)]
    geom = [_ll(0, y) for y in range(0, 150, 15)]
    geom += [_ll(-70, 180), _ll(-70, 210)]            # off-band excursion
    geom += [_ll(0, y) for y in range(240, 400, 15)]
    route = CR(ramal_label="main", direction_group=0, edges=[],
               geometry=geom, trace_count=5, trace_ids=["t"])

    index = _BandIndex(band, 35.0, -17.3935)
    repaired = _snap_route_to_band(route, index, CC(), band)
    assert repaired == 1

    def off(p):
        return min(math.dist(p, q) for line in band for q in line) * 111_320
    assert max(off(p) for p in route.geometry) <= 40, max(off(p) for p in route.geometry)


def test_merge_joins_continuation_across_cluster_labels():
    # A partial-coverage cluster split: "main" (west→mid) and "r2"
    # (mid→east) abut end-to-end with a small gap. They are the same
    # physical line and must merge despite different sub-labels.
    from routebuilder.config import ConsensusConfig as CC
    from routebuilder.engine import merge_close_fragments
    from routebuilder.types import ConsensusRoute as CR

    main = CR(ramal_label="120/main", direction_group=0, edges=[],
              geometry=[_ll(0, 0), _ll(50, 0), _ll(100, 0)], trace_count=3, trace_ids=["a"])
    r2 = CR(ramal_label="120/r2", direction_group=0, edges=[],
            geometry=[_ll(112, 0), _ll(160, 0), _ll(220, 0)], trace_count=4, trace_ids=["b"])
    merged, log = merge_close_fragments([main, r2], CC())
    assert len(merged) == 1
    assert merged[0].ramal_label == "120/main"   # trunk keeps the main label
    assert log[0]["fragments"] == 2


def test_merge_does_not_uturn_two_variants_sharing_a_terminus():
    # Two ramal variants that both END at the same terminus (their ends
    # are <15m apart) but approach it from opposite directions. Joining
    # them would double back through the terminus — must stay separate.
    from routebuilder.config import ConsensusConfig as CC
    from routebuilder.engine import merge_close_fragments
    from routebuilder.types import ConsensusRoute as CR

    # Variant A comes from the west heading east into the terminus.
    a = CR(ramal_label="120/main", direction_group=0, edges=[],
           geometry=[_ll(0, 0), _ll(50, 0), _ll(100, 0)], trace_count=3, trace_ids=["a"])
    # Variant B comes from the north heading south into the same terminus.
    b = CR(ramal_label="120/r2", direction_group=0, edges=[],
           geometry=[_ll(108, 200), _ll(106, 100), _ll(104, 5)], trace_count=3, trace_ids=["b"])
    merged, log = merge_close_fragments([a, b], CC())
    assert len(merged) == 2 and not log



def test_cross_trace_bridge_rebuilds_corridor_from_union():
    # No single trace spans the gap densely (each has a different 50m
    # hole), but the union covers it — the cross-trace median must
    # rebuild a clean path along the corridor.
    import math

    from routebuilder.config import ConsensusConfig as CC
    from routebuilder.engine import _cross_trace_bridge

    def corr(skip_lo, skip_hi):
        return [_ll(x, 0) for x in range(0, 301, 25) if not (skip_lo <= x < skip_hi)]
    traces = [corr(100, 150), corr(150, 200), corr(200, 250), corr(50, 100)]
    out = _cross_trace_bridge(_ll(0, 0), _ll(300, 0), CC(), traces)
    assert out is not None and len(out) >= 5
    # the rebuilt path hugs the corridor centreline (y=0)
    lat0 = -17.3935
    def off_m(p):
        return abs(p[1] - lat0) * 111_320
    assert max(off_m(p) for p in out) <= 10, max(off_m(p) for p in out)
    # and it spans the whole gap
    span = (out[-1][0] - out[0][0]) * 111_320 * math.cos(math.radians(lat0))
    assert span >= 250


def test_cross_trace_bridge_needs_enough_traces():
    # A single trace's spike is not a corridor: too few agreeing traces
    # → no bridge (the cross-trace agreement is the noise filter).
    from routebuilder.config import ConsensusConfig as CC
    from routebuilder.engine import _cross_trace_bridge

    one = [[_ll(0, 0), _ll(150, 40), _ll(300, 0)]]  # lone detour
    assert _cross_trace_bridge(_ll(0, 0), _ll(300, 0), CC(), one) is None
