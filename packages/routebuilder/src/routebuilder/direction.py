"""Split a line's traces into direction groups (forward vs reverse runs).

Valhalla GraphIds identify *directed* edges — the two directions of a
street are different edge ids — so opposite runs cannot be recognized
by flipped edge flags (and incidental same-id overlap at connectors
actively misleads). Direction is instead read geometrically: project a
trace's matched polyline onto a reference polyline (the longest trace)
and look at the sign of its travel along the reference arc. Traces that
don't overlap the reference (one-way loop return legs, disjoint
corridors) are grouped by directed-edge overlap instead — sharing
directed edges is, by construction, same-direction evidence.
"""

from __future__ import annotations

import math

from .config import DirectionConfig
from .graph import _project_m
from .types import MatchedTrace

# A trace must travel at least this far along the reference (in either
# direction) for the geometric verdict to count.
MIN_TRAVEL_M = 150.0
# ... and have at least this fraction of its points near the reference.
MIN_NEAR_FRACTION = 0.3
CORRIDOR_TOLERANCE_M = 60.0


def split_by_direction(
    traces: list[MatchedTrace],
    config: DirectionConfig | None = None,
) -> list[list[MatchedTrace]]:
    """Partition traces into direction groups.

    Returns groups sorted by descending size (ties broken by first
    trace id for determinism). Every input trace appears in exactly
    one group.
    """
    config = config or DirectionConfig()
    n = len(traces)
    if n == 0:
        return []
    if n == 1:
        return [list(traces)]

    reference = max(traces, key=lambda t: _polyline_length_m(t.matched_polyline))
    ref_line = reference.matched_polyline

    forward: list[MatchedTrace] = []
    backward: list[MatchedTrace] = []
    unknown: list[MatchedTrace] = []
    for trace in traces:
        verdict = _travel_along_reference(trace, ref_line)
        if verdict is None:
            unknown.append(trace)
        elif verdict:
            forward.append(trace)
        else:
            backward.append(trace)

    groups = [g for g in (forward, backward) if g]
    if not groups:
        groups = []

    # Attach unknowns by directed-edge overlap (same-direction signal);
    # leftovers form their own groups, merged among themselves the same
    # way (covers one-way loop return legs).
    for trace in unknown:
        target = _best_overlap_group(trace, groups, config)
        if target is not None:
            target.append(trace)
        else:
            groups.append([trace])

    return sorted(groups, key=lambda g: (-len(g), min(t.trace_id for t in g)))


def _travel_along_reference(
    trace: MatchedTrace,
    reference: list[tuple[float, float]],
) -> bool | None:
    """True/False = travels with/against the reference; None = unrelated."""
    points = trace.matched_polyline
    if len(points) < 2 or len(reference) < 2:
        return None

    ref_lat = reference[0][1]
    ref_m = [_project_m(p, ref_lat) for p in reference]
    cumulative = [0.0]
    for a, b in zip(ref_m, ref_m[1:]):
        cumulative.append(cumulative[-1] + math.dist(a, b))

    # Sample up to ~50 points for speed.
    step = max(1, len(points) // 50)
    sampled = points[::step]
    arc_positions: list[float] = []
    near = 0
    for p in sampled:
        pm = _project_m(p, ref_lat)
        best_d = math.inf
        best_pos = 0.0
        for i, (a, b) in enumerate(zip(ref_m, ref_m[1:])):
            seg = (b[0] - a[0], b[1] - a[1])
            seg_len_sq = seg[0] ** 2 + seg[1] ** 2
            if seg_len_sq == 0:
                continue
            t = ((pm[0] - a[0]) * seg[0] + (pm[1] - a[1]) * seg[1]) / seg_len_sq
            t = max(0.0, min(1.0, t))
            proj = (a[0] + t * seg[0], a[1] + t * seg[1])
            d = math.dist(pm, proj)
            if d < best_d:
                best_d = d
                best_pos = cumulative[i] + t * math.sqrt(seg_len_sq)
        if best_d <= CORRIDOR_TOLERANCE_M:
            near += 1
            arc_positions.append(best_pos)

    if not sampled or near / len(sampled) < MIN_NEAR_FRACTION or len(arc_positions) < 2:
        return None
    delta = arc_positions[-1] - arc_positions[0]
    if abs(delta) < MIN_TRAVEL_M:
        return None
    return delta > 0


def _best_overlap_group(
    trace: MatchedTrace,
    groups: list[list[MatchedTrace]],
    config: DirectionConfig,
) -> list[MatchedTrace] | None:
    edge_set = trace.edge_set()
    if not edge_set:
        return None
    best_group = None
    best_overlap = 0
    for group in groups:
        overlap = max(
            (len(edge_set & other.edge_set()) for other in group), default=0
        )
        if overlap > best_overlap:
            best_overlap = overlap
            best_group = group
    shorter = max(len(edge_set), 1)
    if (
        best_overlap >= config.min_common_edges
        or best_overlap / shorter >= config.min_overlap_fraction
    ):
        return best_group
    return None


def _polyline_length_m(polyline: list[tuple[float, float]]) -> float:
    if len(polyline) < 2:
        return 0.0
    ref_lat = polyline[0][1]
    pts = [_project_m(p, ref_lat) for p in polyline]
    return sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))
