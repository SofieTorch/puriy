"""Tests for `geodata.ramales` — ramal detection via complete-linkage
hierarchical clustering on pairwise discrete Fréchet distance.
"""

from datetime import datetime


from geodata.ramales import cluster_traces_into_ramales
from geodata.reconstruction.base import ReconstructionPoint, ReconstructionTrace


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

# Cochabamba-ish coordinates around Plaza Colón (~17.39°S 66.16°W).
# 0.001° lat ≈ 111m; 0.001° lon ≈ 106m at this latitude.

def _trace(trace_id: str, polyline: list[list[float]]) -> ReconstructionTrace:
    """Build a ReconstructionTrace from a `[[lon, lat], ...]` polyline."""
    points = [
        ReconstructionPoint(
            longitude=lon, latitude=lat, point_index=i,
            timestamp=datetime(2026, 1, 1),
        )
        for i, (lon, lat) in enumerate(polyline)
    ]
    return ReconstructionTrace(trace_id=trace_id, points=points)


def _shifted(polyline: list[list[float]], dlon: float, dlat: float) -> list[list[float]]:
    return [[lon + dlon, lat + dlat] for lon, lat in polyline]


# Two distinct ramales sharing the same start (Beijing) and end (Sacaba)
# but diverging in the middle.
RAMAL_A = [
    [-66.160, -17.390],  # Beijing
    [-66.155, -17.390],  # straight east on América
    [-66.150, -17.390],
    [-66.145, -17.390],  # Sacaba
]
RAMAL_B = [
    [-66.160, -17.390],  # Beijing
    [-66.158, -17.395],  # detour south via Simón Lopez
    [-66.150, -17.395],  # Pacata
    [-66.145, -17.390],  # Sacaba
]


# ------------------------------------------------------------------
# Single-ramal cases
# ------------------------------------------------------------------

def test_single_ramal_when_all_traces_overlap() -> None:
    """5 traces of the same ramal (small jitter) → one cluster labelled `main`."""
    traces = [
        _trace(f"t{i}", _shifted(RAMAL_A, 0.0, i * 0.000005))  # < 1m jitter
        for i in range(5)
    ]
    clusters = cluster_traces_into_ramales(traces, distance_threshold_m=200.0)
    assert len(clusters) == 1
    assert clusters[0].label == "main"
    assert sorted(clusters[0].trace_ids) == [f"t{i}" for i in range(5)]


def test_below_min_cluster_size_returns_empty() -> None:
    traces = [_trace(f"t{i}", RAMAL_A) for i in range(2)]
    clusters = cluster_traces_into_ramales(traces, min_cluster_size=3)
    assert clusters == []


def test_isolated_outlier_dropped_as_noise() -> None:
    """4 cohesive traces + 1 outlier → one cluster of 4, outlier dropped."""
    cohort = [_trace(f"t{i}", RAMAL_A) for i in range(4)]
    outlier = _trace("outlier", _shifted(RAMAL_A, 0.0, -0.005))  # ~550m off
    clusters = cluster_traces_into_ramales(
        cohort + [outlier], distance_threshold_m=200.0, min_cluster_size=3,
    )
    assert len(clusters) == 1
    assert "outlier" not in clusters[0].trace_ids
    assert len(clusters[0].trace_ids) == 4


# ------------------------------------------------------------------
# Multi-ramal cases
# ------------------------------------------------------------------

def test_two_distinct_ramales_split_correctly() -> None:
    """3 traces of A + 3 of B (~550m apart at the divergence) → 2 clusters."""
    traces = (
        [_trace(f"a{i}", RAMAL_A) for i in range(3)]
        + [_trace(f"b{i}", RAMAL_B) for i in range(3)]
    )
    clusters = cluster_traces_into_ramales(traces, distance_threshold_m=200.0)
    assert len(clusters) == 2
    # Largest first; both clusters are size 3, so order is implementation-defined.
    cluster_ids = {c.label: set(c.trace_ids) for c in clusters}
    assert {"main", "r2"} == set(cluster_ids.keys())
    a_ids = {f"a{i}" for i in range(3)}
    b_ids = {f"b{i}" for i in range(3)}
    assert any(ids == a_ids for ids in cluster_ids.values())
    assert any(ids == b_ids for ids in cluster_ids.values())


def test_complete_linkage_resists_chaining() -> None:
    """Three groups A, B, C where A↔B and B↔C are 165m (within threshold)
    but A↔C is 333m (above). Single-linkage would chain all three into
    one cluster; complete-linkage keeps C separate from the {A,B} merge.
    Asserting ≥ 2 clusters (not 1) is what proves the algorithm choice."""
    a = RAMAL_A
    b = _shifted(RAMAL_A, 0.0, -0.0015)         # ~165m south of A
    c = _shifted(RAMAL_A, 0.0, -0.0030)         # ~333m south of A
    traces = (
        [_trace(f"a{i}", a) for i in range(3)]
        + [_trace(f"b{i}", b) for i in range(3)]
        + [_trace(f"c{i}", c) for i in range(3)]
    )
    clusters = cluster_traces_into_ramales(traces, distance_threshold_m=200.0)
    assert len(clusters) >= 2, (
        f"expected at least 2 clusters (complete-linkage rejects A+C "
        f"merge at 333m); got {len(clusters)} — this is the chain"
    )
    # The C group (333m from A) cannot be in the same cluster as the A group.
    a_ids = {f"a{i}" for i in range(3)}
    c_ids = {f"c{i}" for i in range(3)}
    for cluster in clusters:
        ids = set(cluster.trace_ids)
        assert not (a_ids & ids and c_ids & ids), (
            "A and C ended up in the same cluster — looks like single linkage"
        )


# ------------------------------------------------------------------
# Label stability across runs (existing_ramales)
# ------------------------------------------------------------------

def test_existing_label_inherited_when_geometry_matches() -> None:
    """Cluster that recognisably continues an existing ramal keeps its label."""
    traces = [_trace(f"t{i}", RAMAL_A) for i in range(4)]
    clusters = cluster_traces_into_ramales(
        traces,
        distance_threshold_m=200.0,
        existing_ramales=[("main", RAMAL_A)],
    )
    assert len(clusters) == 1
    assert clusters[0].label == "main"


def test_new_ramal_gets_fresh_label_when_existing_doesnt_match() -> None:
    """A new cluster geometrically dissimilar from existing gets r2 (not main)."""
    traces = [_trace(f"t{i}", RAMAL_B) for i in range(4)]
    clusters = cluster_traces_into_ramales(
        traces,
        distance_threshold_m=200.0,
        existing_ramales=[("main", RAMAL_A)],
    )
    assert len(clusters) == 1
    # 'main' is reserved for the existing route (no new cluster matched it),
    # so the new cluster gets a fresh label.
    assert clusters[0].label == "r2"


def test_split_resolved_by_best_match_wins() -> None:
    """When two new clusters both want to inherit 'main', the closer one
    wins; the other gets a fresh label. (Decision: best-match-wins.)

    Geometry: existing main is at midpoint between two new clusters X
    and Y. X is shifted slightly less than Y, so X is closer to main.
    X↔Y must exceed threshold so they don't merge into one cluster.
    """
    existing_main = RAMAL_A
    cluster_x = [_trace(f"x{i}", _shifted(RAMAL_A, 0.0, +0.00050)) for i in range(3)]   # ~55m N
    cluster_y = [_trace(f"y{i}", _shifted(RAMAL_A, 0.0, -0.00170)) for i in range(3)]   # ~189m S
    # X↔Y ≈ 245m (above threshold → no merge).
    # X↔main ≈ 55m, Y↔main ≈ 189m → X is best-match for "main".

    traces = cluster_x + cluster_y
    clusters = cluster_traces_into_ramales(
        traces,
        distance_threshold_m=200.0,
        existing_ramales=[("main", existing_main)],
    )
    assert len(clusters) == 2
    by_label = {c.label: c for c in clusters}
    assert "main" in by_label
    # The cluster closest to existing main (X — only ~55m off) keeps "main".
    x_ids = {f"x{i}" for i in range(3)}
    assert set(by_label["main"].trace_ids) == x_ids
    # The other cluster gets a fresh label.
    other_labels = [lbl for lbl in by_label if lbl != "main"]
    assert other_labels and other_labels[0] != "main"
