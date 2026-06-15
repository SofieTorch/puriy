"""Evaluate a consensus route against a ground-truth route geojson.

Metrics:
- frechet_m / coverage: reused from geodata.evaluate (geometric
  similarity and "does the reconstruction trace the whole route").
- edge precision / recall: the consensus directed-edge set vs the
  ground truth's edge set (obtained by map-matching the ground-truth
  polyline once). Precision directly measures the spurious
  cross-street problem; recall measures missing stretches.
- max_junction_gap_m: connectivity (must stay ~0 / below tolerance).
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from geodata.evaluate import coverage_score, discrete_frechet_distance_m
from geodata.geo_math import haversine_m, interpolate_route
from geodata.match import trace_match

from ..cleaning import cache_safe_id
from ..types import ConsensusRoute, DirectedEdge


@dataclass
class EvalResult:
    ramal_label: str
    frechet_m: float            # strict: includes endpoint truncation
    frechet_overlap_m: float    # shape fidelity over the common extent
    start_truncation_m: float   # ground-truth length missing before the route starts
    end_truncation_m: float     # ground-truth length missing after the route ends
    coverage: float
    edge_precision: float | None
    edge_recall: float | None
    max_junction_gap_m: float
    consensus_edges: int
    inferred_edges: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_ground_truth(path: str | Path) -> list[list[float]]:
    """First LineString's coordinates ([lon, lat]) from a geojson file."""
    data = json.loads(Path(path).read_text())
    features = data.get("features", [data] if data.get("type") == "Feature" else [])
    for feature in features:
        geometry = feature.get("geometry", {})
        if geometry.get("type") == "LineString":
            return [list(c[:2]) for c in geometry["coordinates"]]
        if geometry.get("type") == "MultiLineString":
            return [list(c[:2]) for line in geometry["coordinates"] for c in line]
    raise ValueError(f"no LineString found in {path}")


def _clip_truth_to_route(
    dense_truth: list[list[float]],
    dense_candidate: list[list[float]],
) -> tuple[list[list[float]], float, float]:
    """Clip truth to the window between the route endpoints' nearest
    truth samples. Returns (window, start_cut_m, end_cut_m)."""
    from ..graph import _project_m

    ref_lat = dense_truth[0][1]
    truth_m = [_project_m((lon, lat), ref_lat) for lon, lat in dense_truth]
    start_m = _project_m(tuple(dense_candidate[0]), ref_lat)
    end_m = _project_m(tuple(dense_candidate[-1]), ref_lat)

    def nearest_index(p: tuple[float, float]) -> int:
        return min(range(len(truth_m)), key=lambda i: math.dist(truth_m[i], p))

    i0 = nearest_index(start_m)
    i1 = nearest_index(end_m)
    if i0 > i1:
        i0, i1 = i1, i0

    def arc(i: int, j: int) -> float:
        return sum(math.dist(truth_m[k], truth_m[k + 1]) for k in range(i, j))

    return dense_truth[i0 : i1 + 1], arc(0, i0), arc(i1, len(truth_m) - 1)


def matched_ground_truth(
    coordinates: list[list[float]],
    *,
    costing: str = "bus",
    trace_id: str | None = None,
) -> tuple[list[list[float]], set[DirectedEdge]]:
    """Map-match the ground-truth polyline once (requires Valhalla).

    Returns (matchable polyline, directed edge set). Using the matched
    shape as the geometric reference is deliberate: raw ground-truth
    geojsons can include stretches the road network cannot represent
    (terminal loops, unmapped yards) that no trace-based reconstruction
    could ever recover — we evaluate reconstruction quality, not OSM
    completeness.
    """
    dense = interpolate_route([list(c) for c in coordinates], 25.0)
    shape = [{"lat": lat, "lon": lon} for lon, lat in dense]
    output = trace_match(
        shape,
        # Content-hashed id: an edited route geojson under the same
        # path must never reuse the old geometry's cached match.
        trace_id=cache_safe_id(trace_id, shape) if trace_id else None,
        costing=costing,
        search_radius=20,
        gps_accuracy=5,
    )
    # Use the snapped input points, not the routing shape: the
    # trace_attributes shape can take detours through turn
    # restrictions between consecutive edges.
    shape = [
        [float(mp["lon"]), float(mp["lat"])]
        for mp in output.matched_points
        if mp.get("type") == "matched"
    ]
    if len(shape) < 2:
        shape = [[lon, lat] for lat, lon in output.shape_coords]
    edges = {
        DirectedEdge(int(e["id"]), bool(e.get("forward", True)))
        for e in output.edges
    }
    return shape, edges


def ground_truth_edges(
    coordinates: list[list[float]],
    *,
    costing: str = "bus",
    trace_id: str | None = None,
) -> set[DirectedEdge]:
    """Directed edges of the ground-truth polyline (requires Valhalla)."""
    return matched_ground_truth(coordinates, costing=costing, trace_id=trace_id)[1]


def clip_to_achievable(
    ground_truth: list[list[float]],
    traces: list,
    *,
    min_traces: int = 2,
    tolerance_m: float = 30.0,
    step_m: float = 10.0,
) -> list[list[float]]:
    """Clip the ground truth to the extent observed by enough traces.

    With partial traces (riders boarding/alighting mid-route) the
    stretches no trace covered are unrecoverable by definition;
    evaluating against them measures the data, not the algorithm.
    Returns the contiguous ground-truth window between the first and
    last sample point that at least ``min_traces`` matched traces pass
    within ``tolerance_m`` of.
    """
    import shapely
    from shapely.geometry import LineString

    from ..graph import _project_m

    samples = interpolate_route([list(c) for c in ground_truth], step_m)
    if len(samples) < 2 or not traces:
        return [list(c) for c in ground_truth]

    ref_lat = samples[0][1]
    lines = [
        LineString([_project_m((lon, lat), ref_lat) for lon, lat in t.matched_polyline])
        for t in traces
        if len(t.matched_polyline) >= 2
    ]
    points = shapely.points([_project_m((lon, lat), ref_lat) for lon, lat in samples])
    counts = [0] * len(samples)
    for line in lines:
        distances = shapely.distance(line, points)
        for i, d in enumerate(distances):
            if d <= tolerance_m:
                counts[i] += 1
    covered = [c >= min_traces for c in counts]

    if not any(covered):
        return [list(c) for c in ground_truth]
    first = covered.index(True)
    last = len(covered) - 1 - covered[::-1].index(True)
    return [list(samples[i]) for i in range(first, last + 1)]


def evaluate_route(
    route: ConsensusRoute,
    ground_truth: list[list[float]],
    *,
    truth_edges: set[DirectedEdge] | None = None,
) -> EvalResult:
    """Compare one consensus route against the ground-truth polyline.

    `truth_edges` is optional so the geometric metrics work without a
    running Valhalla; pass it (via ground_truth_edges) for edge P/R.
    """
    candidate = [[lon, lat] for lon, lat in route.geometry]
    # Densify both polylines: discrete Fréchet works vertex-to-vertex,
    # so a sparse vertex on a long straight segment would inflate the
    # distance by half the segment length.
    dense_truth = interpolate_route([list(c) for c in ground_truth], 10.0)
    dense_candidate = interpolate_route(candidate, 10.0)
    frechet = discrete_frechet_distance_m(dense_truth, dense_candidate)

    # Separate shape fidelity from extent: clip the truth to the
    # window between the projections of the route's endpoints, compute
    # Fréchet there, and report what was cut off as truncation.
    overlap_truth, start_trunc, end_trunc = _clip_truth_to_route(
        dense_truth, dense_candidate
    )
    frechet_overlap = (
        discrete_frechet_distance_m(overlap_truth, dense_candidate)
        if len(overlap_truth) >= 2
        else frechet
    )
    coverage = coverage_score(
        dense_truth,
        {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": candidate},
                "properties": {},
            }],
        },
    )

    precision = recall = None
    if truth_edges is not None:
        observed = {ce.edge for ce in route.edges if not ce.inferred}
        if observed:
            precision = len(observed & truth_edges) / len(observed)
        if truth_edges:
            # Recall counts inferred edges too: a bridged edge that the
            # ground truth contains is still route coverage.
            all_edges = {ce.edge for ce in route.edges}
            recall = len(all_edges & truth_edges) / len(truth_edges)

    gaps = [
        haversine_m(a.geometry[-1][0], a.geometry[-1][1], b.geometry[0][0], b.geometry[0][1])
        for a, b in zip(route.edges, route.edges[1:])
        if a.geometry and b.geometry
    ]

    return EvalResult(
        ramal_label=route.ramal_label,
        frechet_m=round(frechet, 1),
        frechet_overlap_m=round(frechet_overlap, 1),
        start_truncation_m=round(start_trunc, 1),
        end_truncation_m=round(end_trunc, 1),
        coverage=round(coverage, 4),
        edge_precision=round(precision, 4) if precision is not None else None,
        edge_recall=round(recall, 4) if recall is not None else None,
        max_junction_gap_m=round(max(gaps, default=0.0), 1),
        consensus_edges=len(route.edges),
        inferred_edges=sum(1 for ce in route.edges if ce.inferred),
    )
