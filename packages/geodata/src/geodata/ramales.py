"""Group reconstruction traces into ramales (route variants).

A *ramal* is a variant of a transit line that shares the line's
identifier but follows a meaningfully different geometry — e.g. line
230 in Cochabamba has a "directo" ramal down Av. América and a
"vía Simón Lopez" ramal that detours through Av. Melchor Pérez.

Clustering uses pairwise discrete Fréchet distance (in metres) +
**complete-linkage hierarchical agglomerative** clustering. Complete
linkage is chosen over single-linkage / connected-components because it
avoids the "chaining" problem: a single noisy trace bridging two real
ramales would otherwise merge them.

When `existing_ramales` is provided, each cluster's medoid is matched
against existing polylines using a best-match-wins rule so labels stay
stable across pipeline runs (a cluster that recognisably continues an
existing ramal inherits its label; novel clusters get fresh `r{n}`
labels).
"""

from __future__ import annotations

from dataclasses import dataclass

from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import squareform

from .evaluate import discrete_frechet_distance_m
from .geo_math import haversine_m
from .reconstruction.base import ReconstructionTrace


@dataclass(frozen=True)
class RamalCluster:
    """One detected ramal: a label and the traces assigned to it."""

    label: str
    trace_ids: list[str]
    medoid_trace_id: str
    medoid_coords: list[list[float]]


def cluster_traces_into_ramales(
    traces: list[ReconstructionTrace],
    *,
    distance_threshold_m: float = 200.0,
    min_cluster_size: int = 3,
    resample_interval_m: float = 25.0,
    existing_ramales: list[tuple[str, list[list[float]]]] | None = None,
) -> list[RamalCluster]:
    """Group traces into ramales using pairwise Fréchet + complete linkage.

    Parameters
    ----------
    traces
        Cleaned traces for a single line.
    distance_threshold_m
        Two traces in the same cluster must be within this Fréchet
        distance of each other (complete linkage). Also the maximum
        distance for a cluster to inherit an `existing_ramales` label.
    min_cluster_size
        Clusters with fewer than this many traces are dropped (their
        traces are treated as noise and excluded from the result).
    resample_interval_m
        Each trace's coordinate sequence is resampled to this spacing
        before the pairwise Fréchet matrix is computed (the algorithm
        is O(n*m) per pair). 25m is roughly a quarter-block in
        Cochabamba — fine enough to preserve geometry, coarse enough
        to keep the matrix tractable.
    existing_ramales
        Optional `(label, polyline)` pairs from previously-published
        Routes for this line. Used for label stability: each new
        cluster picks the closest existing label within
        `distance_threshold_m` (best-match-wins). Conflicts (two new
        clusters wanting the same existing label) are resolved by
        nearest distance; the loser gets a fresh label.

    Returns
    -------
    list[RamalCluster]
        Sorted by descending cluster size (largest ramal first).
    """

    if len(traces) < min_cluster_size:
        return []

    coords_per_trace = [_resample_trace(t, resample_interval_m) for t in traces]

    # Pre-compute each trace's lon/lat bounding box (cheap) so we can
    # skip the O(n*m) Fréchet computation entirely when two traces'
    # bboxes don't even come within `distance_threshold_m` of each
    # other. The Fréchet distance between two polylines is bounded
    # below by the closest distance between their bounding boxes, so
    # if the bbox separation already exceeds the threshold, the
    # Fréchet distance does too — we can use a sentinel "above
    # threshold" value instead of computing it.
    bboxes = [_polyline_bbox(coords) for coords in coords_per_trace]
    threshold_deg = distance_threshold_m / 111_000.0  # ~m → degrees latitude

    # Pairwise Fréchet matrix. Symmetric, zero diagonal. Pairs whose
    # bboxes are obviously too far apart skip the heavy computation
    # and use 2× threshold as the recorded distance — well outside
    # the cluster cut, so they end up in different clusters either way.
    n = len(traces)
    pairwise = [[0.0] * n for _ in range(n)]
    far_value = distance_threshold_m * 2
    for i in range(n):
        for j in range(i + 1, n):
            if _bboxes_separated(bboxes[i], bboxes[j], threshold_deg):
                pairwise[i][j] = pairwise[j][i] = far_value
                continue
            d = discrete_frechet_distance_m(coords_per_trace[i], coords_per_trace[j])
            pairwise[i][j] = d
            pairwise[j][i] = d

    if n == 1:
        # Single-trace edge case: one cluster if it meets min_cluster_size.
        labels_arr = [1]
    else:
        condensed = squareform(pairwise, checks=False)
        link = linkage(condensed, method="complete")
        labels_arr = fcluster(link, t=distance_threshold_m, criterion="distance")

    # Group trace indices by cluster id.
    groups: dict[int, list[int]] = {}
    for idx, cid in enumerate(labels_arr):
        groups.setdefault(int(cid), []).append(idx)

    # Drop clusters below the size floor; pick a medoid for each kept cluster.
    kept: list[tuple[list[int], int]] = []  # (trace indices, medoid index)
    for indices in groups.values():
        if len(indices) < min_cluster_size:
            continue
        medoid_idx = _pick_medoid(indices, pairwise)
        kept.append((indices, medoid_idx))

    # Sort by size descending so the largest ramal is first.
    kept.sort(key=lambda item: -len(item[0]))

    # Existing polylines must be resampled at the same interval before
    # being compared against the (resampled) cluster medoids — otherwise
    # discrete Fréchet inflates because a dense resampled polyline can't
    # find matches for its intermediate points in a sparse one.
    resampled_existing = [
        (label, _resample_polyline(coords, resample_interval_m))
        for label, coords in (existing_ramales or [])
    ]

    # Assign labels: existing-best-match where possible, then r2, r3, ...
    assigned_labels = _assign_labels(
        kept,
        coords_per_trace,
        resampled_existing,
        distance_threshold_m,
    )

    return [
        RamalCluster(
            label=assigned_labels[i],
            trace_ids=[traces[idx].trace_id for idx in indices],
            medoid_trace_id=traces[medoid_idx].trace_id,
            medoid_coords=coords_per_trace[medoid_idx],
        )
        for i, (indices, medoid_idx) in enumerate(kept)
    ]


def _resample_trace(
    trace: ReconstructionTrace, interval_m: float,
) -> list[list[float]]:
    """Resample a trace to uniform `interval_m` spacing as `[[lon, lat], …]`."""
    return _resample_polyline(
        [[p.longitude, p.latitude] for p in trace.points],
        interval_m,
    )


def _resample_polyline(
    polyline: list[list[float]], interval_m: float,
) -> list[list[float]]:
    """Resample `[[lon, lat], …]` polyline to uniform `interval_m` spacing.

    Always includes the first and last points; intermediate points are
    linearly interpolated along the great-circle path.
    """
    if len(polyline) < 2:
        return [list(p) for p in polyline]

    cum = [0.0]
    for i in range(1, len(polyline)):
        cum.append(cum[-1] + haversine_m(
            polyline[i - 1][0], polyline[i - 1][1],
            polyline[i][0], polyline[i][1],
        ))
    total = cum[-1]
    if total == 0.0:
        return [list(polyline[0])]

    out: list[list[float]] = []
    target = 0.0
    j = 1
    while target <= total:
        while j < len(polyline) and cum[j] < target:
            j += 1
        if j >= len(polyline):
            out.append(list(polyline[-1]))
            break
        seg_len = cum[j] - cum[j - 1]
        if seg_len == 0:
            out.append(list(polyline[j]))
        else:
            t = (target - cum[j - 1]) / seg_len
            lon = polyline[j - 1][0] + t * (polyline[j][0] - polyline[j - 1][0])
            lat = polyline[j - 1][1] + t * (polyline[j][1] - polyline[j - 1][1])
            out.append([lon, lat])
        target += interval_m

    last = list(polyline[-1])
    if out[-1] != last:
        out.append(last)
    return out


def _pick_medoid(indices: list[int], pairwise: list[list[float]]) -> int:
    """Index (within `indices`) whose total distance to the others is smallest."""
    best_idx = indices[0]
    best_sum = float("inf")
    for i in indices:
        s = sum(pairwise[i][j] for j in indices if j != i)
        if s < best_sum:
            best_sum = s
            best_idx = i
    return best_idx


def _assign_labels(
    kept: list[tuple[list[int], int]],
    coords_per_trace: list[list[list[float]]],
    existing: list[tuple[str, list[list[float]]]],
    threshold_m: float,
) -> list[str]:
    """Assign labels best-match-wins.

    For each (cluster, existing) pair compute medoid-vs-existing
    Fréchet. Iterate by ascending distance; assign each existing label
    to its closest unassigned cluster (within threshold). Clusters left
    over get fresh labels `r2`, `r3`, … (skipping `main` and any
    already-used existing labels).
    """
    # Precompute medoid-vs-existing distances.
    candidates: list[tuple[float, int, str]] = []  # (distance, cluster index, existing label)
    for c_idx, (_, medoid_idx) in enumerate(kept):
        for ex_label, ex_coords in existing:
            d = discrete_frechet_distance_m(coords_per_trace[medoid_idx], ex_coords)
            if d <= threshold_m:
                candidates.append((d, c_idx, ex_label))
    candidates.sort()

    assigned: dict[int, str] = {}
    used_labels: set[str] = set()
    for _d, c_idx, ex_label in candidates:
        if c_idx in assigned or ex_label in used_labels:
            continue
        assigned[c_idx] = ex_label
        used_labels.add(ex_label)

    # Backfill unassigned clusters with fresh labels.
    used_labels.update(label for label, _ in existing)
    fresh_counter = 2
    for c_idx in range(len(kept)):
        if c_idx in assigned:
            continue
        # Largest unassigned cluster claims "main" if it's free.
        if "main" not in used_labels:
            assigned[c_idx] = "main"
            used_labels.add("main")
            continue
        while f"r{fresh_counter}" in used_labels:
            fresh_counter += 1
        label = f"r{fresh_counter}"
        assigned[c_idx] = label
        used_labels.add(label)
        fresh_counter += 1

    return [assigned[i] for i in range(len(kept))]


def _polyline_bbox(
    polyline: list[list[float]],
) -> tuple[float, float, float, float]:
    """Return `(min_lon, min_lat, max_lon, max_lat)` — empty polyline
    yields a degenerate (0, 0, 0, 0) bbox which is safe because it'll
    fail the separation check against anything real."""
    if not polyline:
        return (0.0, 0.0, 0.0, 0.0)
    lons = [p[0] for p in polyline]
    lats = [p[1] for p in polyline]
    return (min(lons), min(lats), max(lons), max(lats))


def _bboxes_separated(
    a: tuple[float, float, float, float],
    b: tuple[float, float, float, float],
    threshold_deg: float,
) -> bool:
    """True iff the two bboxes are further apart than `threshold_deg`
    in either lon or lat dimension. Conservative — uses the same
    threshold for both axes, treating 1° lon ≈ 1° lat (true at the
    equator, off by ~5% at Cochabamba's latitude). Good enough as a
    pre-filter; only point is to skip pairs that are obviously far."""
    a_min_lon, a_min_lat, a_max_lon, a_max_lat = a
    b_min_lon, b_min_lat, b_max_lon, b_max_lat = b
    lon_gap = max(0.0, max(a_min_lon - b_max_lon, b_min_lon - a_max_lon))
    lat_gap = max(0.0, max(a_min_lat - b_max_lat, b_min_lat - a_max_lat))
    return lon_gap > threshold_deg or lat_gap > threshold_deg
