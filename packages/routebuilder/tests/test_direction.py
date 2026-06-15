from fixtures import make_trace

from routebuilder.direction import split_by_direction
from routebuilder.types import DirectedEdge, MatchedTrace


def test_all_same_direction_is_one_group():
    traces = [make_trace(f"t{i}", list(range(1, 11))) for i in range(4)]
    groups = split_by_direction(traces)
    assert len(groups) == 1
    assert len(groups[0]) == 4


def test_forward_and_reverse_runs_split_into_two_groups():
    forward = [make_trace(f"f{i}", list(range(1, 11))) for i in range(3)]
    reverse = [make_trace(f"r{i}", list(range(1, 11)), forward=False) for i in range(2)]
    groups = split_by_direction(forward + reverse)
    assert len(groups) == 2
    assert sorted(len(g) for g in groups) == [2, 3]
    for group in groups:
        ids = {t.trace_id[0] for t in group}
        assert ids in ({"f"}, {"r"})


def test_one_way_loop_reverse_runs_are_separate_components():
    # Outbound and return use disjoint edge ids (one-way streets):
    # the pairs are unrelated, so they form separate groups.
    out = [make_trace(f"o{i}", list(range(1, 11))) for i in range(2)]
    back = [make_trace(f"b{i}", list(range(20, 30))) for i in range(2)]
    groups = split_by_direction(out + back)
    assert len(groups) == 2
    for group in groups:
        ids = {t.trace_id[0] for t in group}
        assert ids in ({"o"}, {"b"})


def test_partial_traces_connected_by_spanning_trace_stay_together():
    first_half = make_trace("a", list(range(1, 8)))
    second_half = make_trace("b", list(range(8, 15)))
    spanning = make_trace("c", list(range(1, 15)))
    groups = split_by_direction([first_half, second_half, spanning])
    assert len(groups) == 1
    assert len(groups[0]) == 3


def test_below_overlap_threshold_pairs_are_unrelated():
    a = make_trace("a", list(range(1, 11)))
    b = make_trace("b", list(range(9, 19)))  # only 2 shared edges
    groups = split_by_direction([a, b])
    assert len(groups) == 2


def test_single_trace_and_empty_input():
    assert split_by_direction([]) == []
    only = make_trace("a", list(range(1, 11)))
    assert split_by_direction([only]) == [[only]]


def test_partition_invariant():
    traces = [
        make_trace("a", list(range(1, 11))),
        make_trace("b", list(range(1, 11)), forward=False),
        make_trace("c", list(range(3, 13))),
        make_trace("d", list(range(40, 50))),
    ]
    groups = split_by_direction(traces)
    flat = [t.trace_id for g in groups for t in g]
    assert sorted(flat) == ["a", "b", "c", "d"]


def test_mixed_direction_edge_sets_majority_wins():
    # A trace that shares 6 same-direction edges and 1 flipped edge
    # with another still counts as same direction.
    base = make_trace("base", list(range(1, 8)))
    edges = [DirectedEdge(i, True) for i in range(1, 7)] + [DirectedEdge(7, False)]
    odd = MatchedTrace(
        trace_id="odd",
        edges=edges,
        edge_geometries={},
        matched_polyline=[],
        match_quality=1.0,
    )
    groups = split_by_direction([base, odd])
    assert len(groups) == 1


def test_cache_safe_id_changes_with_content():
    from routebuilder.cleaning import cache_safe_id

    a = [{"lat": -17.39, "lon": -66.15, "time": 100}, {"lat": -17.391, "lon": -66.151, "time": 102}]
    b = [{"lat": -17.39, "lon": -66.15, "time": 100}, {"lat": -17.392, "lon": -66.151, "time": 102}]
    same = cache_safe_id("trip:1", a)
    assert cache_safe_id("trip:1", a) == same          # deterministic
    assert cache_safe_id("trip:1", b) != same          # different points → different key
    assert cache_safe_id("trip:2", a) != same          # different trip → different key
    assert same.startswith("trip:1@")


def test_infer_direction_false_makes_one_group():
    from routebuilder.engine import reconstruct_from_matched
    from fixtures import make_trace

    fwd = [make_trace(f"f{i}", list(range(1, 11))) for i in range(3)]
    rev = [make_trace(f"r{i}", list(range(1, 11)), forward=False) for i in range(2)]
    # With inference, forward+reverse split into 2 direction groups.
    inferred = reconstruct_from_matched(fwd + rev)
    assert inferred.diagnostics["direction_groups"] == 2
    # Trusting the caller, everything is one group.
    trusted = reconstruct_from_matched(fwd + rev, infer_direction=False)
    assert trusted.diagnostics["direction_groups"] == 1
