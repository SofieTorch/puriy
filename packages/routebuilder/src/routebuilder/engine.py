"""Top-level orchestration: raw or matched traces → consensus routes.

Pipeline per line:
  1. clean (Valhalla HMM map matching, quality gates)
  2. split by direction (directed-edge agreement)
  3. cluster into ramales per direction (Fréchet + complete linkage)
  4. consensus per cluster (support graph → widest path → assembly)
  5. divergence refinement: when a cluster hides two competing
     branches, partition its traces and re-run consensus per side
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from geodata.geo_math import haversine_m

from .cleaning import clean_trace
from .config import ConsensusConfig, ReconstructionConfig
from .consensus import BridgeFn, run_cluster_consensus
from .direction import split_by_direction
from .ramales import RamalGroup, cluster_ramales, detect_divergence, split_by_divergence
from .types import ConsensusRoute, MatchedTrace, RawPoint, ReconstructionOutput


def reconstruct_from_raw(
    raw_traces: dict[str, list[RawPoint]],
    *,
    config: ReconstructionConfig | None = None,
    bridge_fn: BridgeFn | None = None,
    device_ids: dict[str, str] | None = None,
) -> ReconstructionOutput:
    """Reconstruct from raw GPS traces (requires Valhalla)."""
    config = config or ReconstructionConfig()
    matched: list[MatchedTrace] = []
    dropped: list[str] = []
    for trace_id, points in raw_traces.items():
        trace = clean_trace(
            trace_id,
            points,
            config.cleaning,
            device_id=(device_ids or {}).get(trace_id),
        )
        if trace is None:
            dropped.append(trace_id)
        else:
            matched.append(trace)

    output = reconstruct_from_matched(matched, config=config, bridge_fn=bridge_fn)
    output.dropped_traces = dropped + output.dropped_traces
    output.diagnostics["raw_traces"] = len(raw_traces)
    output.diagnostics["cleaned_traces"] = len(matched)
    return output


def reconstruct_from_matched(
    traces: list[MatchedTrace],
    *,
    config: ReconstructionConfig | None = None,
    bridge_fn: BridgeFn | None = None,
    existing_ramales: list[tuple[str, list[list[float]]]] | None = None,
    infer_direction: bool = True,
    strategy: str = "support_graph",
) -> ReconstructionOutput:
    """Reconstruct consensus routes from already-matched traces.

    When the caller already knows the traces all run one direction
    (e.g. a simulator that generates one-directional trips per route),
    pass ``infer_direction=False`` to skip geometric direction
    inference — which can mis-split a route that doubles back on itself
    into phantom direction groups.

    ``strategy`` selects the per-cluster consensus algorithm:
    "support_graph" (native) or "edge_overlap" (legacy geodata
    edge-sequence assembly, via strategies.reconstruct_edge_overlap).
    """
    config = config or ReconstructionConfig()
    routes: list[ConsensusRoute] = []
    diagnostics: dict[str, Any] = {
        "direction_groups": 0, "clusters": [], "strategy": strategy,
    }

    groups = (
        split_by_direction(traces, config.direction)
        if infer_direction
        else [list(traces)]
    )
    diagnostics["direction_groups"] = len(groups)

    top_down = config.ramales.discovery == "divergence"
    diagnostics["discovery"] = config.ramales.discovery

    for group_index, group in enumerate(groups):
        if top_down:
            # Top-down: the whole corridor is one cluster; divergences carve it.
            clusters = [_single_cluster(group)] if group else []
            max_depth = max(1, config.ramales.max_divergence_depth)
        else:
            clusters = cluster_ramales(
                group, config.ramales, existing_ramales=existing_ramales)
            max_depth = 1
        used_labels = {c.label for c in clusters}

        for cluster in clusters:
            if strategy == "edge_overlap":
                from .strategies import reconstruct_edge_overlap

                cluster_routes, cluster_diag = reconstruct_edge_overlap(
                    cluster.traces,
                    config=config.consensus,
                    ramal_label=cluster.label,
                    direction_group=group_index,
                )
            else:
                cluster_routes, cluster_diag = _consensus_with_divergence(
                    cluster,
                    group_index,
                    config,
                    bridge_fn,
                    used_labels,
                    max_depth=max_depth,
                    # Shared-trunk traces feed both ramales so each is a complete
                    # route (the common corridor reaches its terminus in both),
                    # not a hard partition that truncates one side. Paired with
                    # the corridor spine, both reach their distinct ends, so
                    # they're no longer "contained" duplicates.
                    overlap=top_down,
                )
            routes.extend(cluster_routes)
            cluster_diag["direction_group"] = group_index
            diagnostics["clusters"].append(cluster_diag)

    trace_lines = [t.matched_polyline for t in traces if len(t.matched_polyline) >= 2]

    # Clean backtrack stubs (e.g. a backward first matched point) before
    # merging — a stub corrupts a fragment endpoint and blocks the stitch
    # that would rejoin it.
    pre_spikes = sum(_smooth_backtracks(r) for r in routes)

    # De-drift: snap consensus stretches that strayed off the trace
    # band (snap-spike doglegs onto cross streets) back onto the band,
    # before merging — this also un-corrupts fragment endpoints so the
    # merge can anchor to them.
    if trace_lines and config.consensus.max_offband_m > 0:
        index = _BandIndex(trace_lines, config.consensus.max_offband_m, trace_lines[0][0][1])
        drifts = sum(_snap_route_to_band(r, index, config.consensus, trace_lines)
                     for r in routes)
        diagnostics["dedrift_repairs"] = drifts

    # Stitch fragments of the same ramal whose endpoints are close —
    # this catches gaps the in-path weld can't (fragments from separate
    # clusters, or a split path). A wider gap is filled with the road
    # geometry of a trace that drove through it; a tiny one with a
    # straight weld.
    routes, merged = merge_close_fragments(routes, config.consensus, trace_lines)
    diagnostics["merged_fragments"] = merged

    traces_by_id = {t.trace_id: t for t in traces}
    routes, discarded = validate_ramales(routes, traces_by_id, config)
    diagnostics["discarded_ramales"] = discarded

    # Final cleanup: drop short backtrack spikes left by stitching a
    # noisy trace through a corner or by joining two slightly overlapping
    # fragments — a transit route never reverses over a few tens of metres.
    spikes = pre_spikes + sum(_smooth_backtracks(r) for r in routes)
    diagnostics["despiked_points"] = spikes

    return ReconstructionOutput(routes=routes, dropped_traces=[], diagnostics=diagnostics)


def _gap_m(a, b) -> float:
    return haversine_m(a[0], a[1], b[0], b[1])


def _smooth_backtracks(
    route: ConsensusRoute, min_turn_deg: float = 120.0, max_spike_len_m: float = 80.0
) -> int:
    """Remove short backtrack spikes from a route's geometry in place.

    A vertex whose incoming and outgoing segments reverse by more than
    min_turn_deg, with both segments shorter than max_spike_len_m, is an
    artifact (a stitched noisy corner, an overlapping fragment join), not
    a real switchback — drop it. Returns the number of points removed.
    """
    geom = route.geometry
    if len(geom) < 3:
        return 0
    removed = 0
    changed = True
    while changed and len(geom) >= 3:
        changed = False
        out = [geom[0]]
        i = 1
        while i < len(geom) - 1:
            a, b, c = out[-1], geom[i], geom[i + 1]
            turn = _angle_diff(_planar_bearing(a, b), _planar_bearing(b, c))
            # A near-reversal whose shorter arm is a stub is an artifact
            # (a backward first point, an overlapping merge join) — drop
            # it. The other arm may be long (the real route continuing).
            if (turn >= min_turn_deg
                    and min(_gap_m(a, b), _gap_m(b, c)) <= max_spike_len_m):
                removed += 1
                changed = True
                i += 1
                continue
            out.append(b)
            i += 1
        out.append(geom[-1])
        geom = out
    route.geometry = geom
    return removed


class _BandIndex:
    """Coarse spatial grid of trace points for fast 'is this point near
    the trace band?' queries."""

    def __init__(self, trace_lines, cell_m, ref_lat):
        from collections import defaultdict
        self.cell = cell_m
        self.ref_lat = ref_lat
        self.grid: dict = defaultdict(list)
        for line in trace_lines:
            for p in line:
                x, y = _proj(p, ref_lat)
                self.grid[(int(x // cell_m), int(y // cell_m))].append((x, y))

    def near(self, p, radius) -> bool:
        x, y = _proj(p, self.ref_lat)
        cx, cy = int(x // self.cell), int(y // self.cell)
        r2 = radius * radius
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for (px, py) in self.grid.get((cx + dx, cy + dy), ()):
                    if (px - x) ** 2 + (py - y) ** 2 <= r2:
                        return True
        return False


def _snap_route_to_band(route: ConsensusRoute, index: "_BandIndex",
                        config: ConsensusConfig, trace_lines: list[list]) -> int:
    """Replace consensus stretches that drifted off the trace band with
    the band's own path. Returns the number of off-band stretches
    repaired.

    The traces are ground truth; where the route strays farther than
    max_offband_m from every trace (a snap-spike dogleg onto a cross
    street), splice in a trace that runs through that span instead.
    """
    if config.max_offband_m <= 0 or len(route.geometry) < 3 or not trace_lines:
        return 0
    off = config.max_offband_m
    geom = route.geometry
    on_band = [index.near(p, off) for p in geom]
    if all(on_band):
        return 0

    new_geom: list = []
    repaired = 0
    i, n = 0, len(geom)
    while i < n:
        if on_band[i]:
            new_geom.append(geom[i])
            i += 1
            continue
        j = i
        while j < n and not on_band[j]:
            j += 1
        before = new_geom[-1] if new_geom else None
        after = geom[j] if j < n else None
        if before is not None and after is not None:
            stitch = _trace_stitch(before, after, _gap_m(before, after),
                                   config, trace_lines, tol=off)
            if stitch:
                for p in stitch:
                    if _gap_m(new_geom[-1], p) > 0:
                        new_geom.append(p)
            # The replacement (before → stitch → after) is an inferred
            # bridge that filled the drifted stretch.
            route.bridges.append([before, *(stitch or []), after])
            repaired += 1
        # off-band stretch at the very start/end (no anchor) is dropped
        i = j

    if len(new_geom) >= 2:
        route.geometry = new_geom
        # Drop edges whose geometry sits off the band (the spurious
        # cross-street edges the snap produced).
        route.edges = [
            ce for ce in route.edges
            if not ce.geometry
            or index.near(ce.geometry[len(ce.geometry) // 2], off)
        ]
    return repaired


def _label_family(label: str) -> str:
    head, _, tail = label.rpartition(".")
    return head if head and tail.isdigit() else label


def merge_close_fragments(
    routes: list[ConsensusRoute],
    config: ConsensusConfig,
    trace_lines: list[list] | None = None,
) -> tuple[list[ConsensusRoute], list[dict]]:
    """Merge same-ramal fragments separated by a fillable gap into one
    connected route.

    Two fragments are joined when the gap between their nearest ends is
    either tiny (straight weld, ≤ max_weld_gap_m) or wider but crossed
    by a supporting trace whose road geometry fills it (≤
    max_stitch_gap_m). The latter is the real fix for the common case
    where the traces run continuously through a point but the
    widest-path skipped its connector edge.
    """
    from collections import defaultdict

    trace_lines = trace_lines or []
    # Group by travel direction only — fragments that abut end-to-end are
    # the same physical route even when ramal clustering split them into
    # different sub-labels (e.g. partial-coverage trips clustered apart as
    # "main" and "r2"). _chain_fragments connects only genuine
    # continuations (touch / collinear bridge / trace stitch), and the
    # continuity guard keeps parallel variants that merely share a
    # terminus from being joined.
    groups: dict[int, list[ConsensusRoute]] = defaultdict(list)
    for route in routes:
        groups[route.direction_group].append(route)

    out: list[ConsensusRoute] = []
    merged_log: list[dict] = []
    for direction_group, frags in groups.items():
        chains = _chain_fragments(frags, config, trace_lines)
        # Longest chains first so the trunk keeps the bare family label
        # and shorter leftovers take the numbered suffixes.
        chains.sort(key=lambda c: sum(len(f.geometry) for f in c), reverse=True)
        used: set[str] = set()
        for chain in chains:
            label = _unique_label(_chain_family(chain), used)
            used.add(label)
            if len(chain) == 1:
                chain[0].ramal_label = label
                out.append(chain[0])
                continue
            merged = _concat_chain(chain, label, direction_group, config, trace_lines)
            merged_log.append({
                "ramal_label": merged.ramal_label,
                "fragments": len(chain),
                "stitched": merged.diagnostics.get("stitch", 0),
                "bridged": merged.diagnostics.get("bridge", 0),
                "welded": merged.diagnostics.get("weld", 0),
            })
            out.append(merged)
    return out, merged_log


def _chain_family(chain: list[ConsensusRoute]) -> str:
    """Label family for a merged chain: prefer a ``main`` family if any
    fragment carries one, else the family of the longest fragment."""
    families = [_label_family(f.ramal_label) for f in chain]
    for fam in families:
        if fam == "main" or fam.rsplit("/", 1)[-1] == "main":
            return fam
    longest = max(chain, key=lambda f: len(f.geometry))
    return _label_family(longest.ramal_label)


def _unique_label(family: str, used: set[str]) -> str:
    if family not in used:
        return family
    n = 2
    while f"{family}.{n}" in used:
        n += 1
    return f"{family}.{n}"


def _endpoints(route: ConsensusRoute) -> tuple:
    return route.geometry[0], route.geometry[-1]


def _connector(a_geom, b_geom, config: ConsensusConfig, trace_lines: list[list]):
    """Geometry connecting a_geom's end → b_geom's start (intermediate
    points only), or None if the gap cannot be filled.

    Order: touching → unambiguous straight bridge (collinear + traces
    confirm no detour) → trace stitch (follow a trace's road geometry,
    for curves) → straight weld (tiny gap) → no connection.
    """
    start, end = a_geom[-1], b_geom[0]
    gap = _gap_m(start, end)
    # Bare-proximity joins (touch / weld) trust geometry alone, so they
    # only fire when the route stays nearly straight through the gap — a
    # sharp turn there means two variants meeting at a shared terminus,
    # not one continuing route. Trace-backed stitches and collinear
    # bridges carry their own evidence and may turn a real corner.
    nearly_straight = _is_continuation(a_geom, b_geom, _TOUCH_MAX_TURN_DEG)
    continues = _is_continuation(a_geom, b_geom, config.max_merge_turn_deg)
    if gap <= config.connect_tolerance_m and nearly_straight:
        return [], "touch"
    if _straight_bridge_ok(a_geom, b_geom, config, trace_lines):
        return [], "bridge"
    if not continues:
        return None, None
    stitched = _trace_stitch(start, end, gap, config, trace_lines)
    if stitched is not None:
        return stitched, "stitch"
    # No single trace spans the gap densely — try the cross-trace median
    # (partial-coverage corridor that the union of traces covers).
    cross = _cross_trace_bridge(start, end, config, trace_lines)
    if cross is not None:
        return cross, "cross"
    if gap <= config.max_weld_gap_m and nearly_straight:
        return [], "weld"
    return None, None


# A touch/weld join may absorb at most this much apparent turn; beyond it
# the proximity is a terminus where distinct variants meet, not a
# continuation. Corners with trace evidence go through stitch instead.
_TOUCH_MAX_TURN_DEG = 45.0


def _is_continuation(a_geom, b_geom, max_turn_deg: float) -> bool:
    """True when the route leaving b's start heads the same way as the
    route approaching a's end (within max_turn_deg). Headings are taken
    over ~30m to stay robust to junction noise."""
    h_in = _heading_at(a_geom, True, 30.0)
    h_out = _heading_at(b_geom, False, 30.0)
    if h_in is None or h_out is None:
        return True
    return _angle_diff(h_in, h_out) <= max_turn_deg


def _proj(p, ref_lat):
    import math
    return (p[0] * 111_320 * math.cos(math.radians(ref_lat)), p[1] * 111_320)


def _planar_bearing(p, q):
    import math
    ref_lat = p[1]
    east = (q[0] - p[0]) * 111_320 * math.cos(math.radians(ref_lat))
    north = (q[1] - p[1]) * 111_320
    return math.degrees(math.atan2(east, north)) % 360


def _angle_diff(a, b):
    d = abs(a - b) % 360
    return min(d, 360 - d)


def _heading_at(geom, at_end: bool, span_m: float):
    """Bearing of the route approaching the end (or leaving the start)
    of a fragment, measured over ~span_m for robustness to noise."""
    if len(geom) < 2:
        return None
    if at_end:
        anchor = geom[-1]
        for k in range(len(geom) - 2, -1, -1):
            if _gap_m(geom[k], anchor) >= span_m:
                return _planar_bearing(geom[k], anchor)
        return _planar_bearing(geom[0], anchor)
    anchor = geom[0]
    for k in range(1, len(geom)):
        if _gap_m(geom[k], anchor) >= span_m:
            return _planar_bearing(anchor, geom[k])
    return _planar_bearing(anchor, geom[-1])


def _point_seg_dist_m(p, a, b):
    seg = (b[0] - a[0], b[1] - a[1])
    L2 = seg[0] ** 2 + seg[1] ** 2
    if L2 == 0:
        return ((p[0] - a[0]) ** 2 + (p[1] - a[1]) ** 2) ** 0.5
    t = max(0.0, min(1.0, ((p[0] - a[0]) * seg[0] + (p[1] - a[1]) * seg[1]) / L2))
    proj = (a[0] + t * seg[0], a[1] + t * seg[1])
    return ((p[0] - proj[0]) ** 2 + (p[1] - proj[1]) ** 2) ** 0.5


def _straight_bridge_ok(a_geom, b_geom, config: ConsensusConfig, trace_lines: list[list]):
    """A gap is straight-bridgeable when the two fragments point at
    each other (no turn) AND a supporting trace crosses it hugging the
    straight line (no block detour). Snap-spikes near the junction stay
    under the deviation cap; a go-around-the-block bulges past it."""
    start, end = a_geom[-1], b_geom[0]
    gap = _gap_m(start, end)
    if gap > config.max_stitch_gap_m:
        return False
    tol_deg = config.straight_bridge_max_turn_deg
    bear_gap = _planar_bearing(start, end)
    h_a = _heading_at(a_geom, True, 30.0)
    h_b = _heading_at(b_geom, False, 30.0)
    if h_a is None or h_b is None:
        return False
    if (_angle_diff(h_a, bear_gap) > tol_deg or _angle_diff(h_b, bear_gap) > tol_deg
            or _angle_diff(h_a, h_b) > tol_deg):
        return False

    ref_lat = start[1]
    sp, ep = _proj(start, ref_lat), _proj(end, ref_lat)
    tol_m = max(config.max_weld_gap_m, config.connect_tolerance_m)
    crossing = 0
    for line in trace_lines:
        if len(line) < 2:
            continue
        i = min(range(len(line)), key=lambda k: _gap_m(line[k], start))
        j = min(range(len(line)), key=lambda k: _gap_m(line[k], end))
        if _gap_m(line[i], start) > tol_m or _gap_m(line[j], end) > tol_m:
            continue
        lo, hi = (i, j) if i <= j else (j, i)
        max_dev = max(
            (_point_seg_dist_m(_proj(line[k], ref_lat), sp, ep) for k in range(lo, hi + 1)),
            default=0.0,
        )
        if max_dev > config.straight_bridge_max_trace_dev_m:
            return False  # a detour bulges off the straight line
        crossing += 1
    return crossing >= 1


# A stitched trace segment must keep its own points closer than this, so
# it follows the road through the gap instead of jumping straight across.
_MAX_STITCH_POINT_GAP_M = 80.0


def _trace_stitch(start, end, gap, config: ConsensusConfig, trace_lines: list[list],
                  tol: float | None = None):
    """Sub-segment of a supporting trace that runs from near `start` to
    near `end`, or None. The chosen trace must pass within `tol` of both
    points and span them.

    The gate is the straight-line gap (the consensus jump we're
    repairing), not the segment length — the actual road through the
    gap may bend and be longer. The segment is allowed up to a
    multiple of the straight gap so a real bend is followed but a trace
    that loops far around is not."""
    if gap > config.max_trace_bridge_gap_m or not trace_lines:
        return None
    if tol is None:
        tol = max(config.max_weld_gap_m, config.connect_tolerance_m)
    # Cap the followed segment so a trace that loops far around (rather
    # than driving roughly straight through) is rejected.
    max_seg_len = max(config.max_stitch_gap_m, 3.0 * gap)
    best = None
    best_score = float("inf")
    for line in trace_lines:
        if len(line) < 2:
            continue
        i = min(range(len(line)), key=lambda k: _gap_m(line[k], start))
        j = min(range(len(line)), key=lambda k: _gap_m(line[k], end))
        if i == j:
            continue
        d_start = _gap_m(line[i], start)
        d_end = _gap_m(line[j], end)
        if d_start > tol or d_end > tol:
            continue
        seg = list(line[i : j + 1]) if i < j else list(reversed(line[j : i + 1]))
        seg_len = sum(_gap_m(seg[k], seg[k + 1]) for k in range(len(seg) - 1))
        if seg_len > max_seg_len:
            continue
        # Require the trace to actually trace the road through the gap, not
        # jump across it: reject a segment with a long internal hole (its
        # own points too far apart to follow a bend).
        if any(_gap_m(seg[k], seg[k + 1]) > _MAX_STITCH_POINT_GAP_M
               for k in range(len(seg) - 1)):
            continue
        score = d_start + d_end + abs(seg_len - gap)
        if score < best_score:
            best, best_score = seg, score
    return best


def _resample_line(line: list, step_m: float) -> list:
    """Evenly spaced points along a polyline (n+1 points, ~step_m apart)."""
    if len(line) < 2:
        return list(line)
    cum = [0.0]
    for a, b in zip(line, line[1:]):
        cum.append(cum[-1] + _gap_m(a, b))
    total = cum[-1]
    if total == 0:
        return [line[0]]
    n = max(1, int(total // step_m))
    out, seg = [], 0
    for i in range(n + 1):
        target = total * i / n
        while seg < len(cum) - 2 and cum[seg + 1] < target:
            seg += 1
        d = cum[seg + 1] - cum[seg]
        t = 0.0 if d == 0 else (target - cum[seg]) / d
        a, b = line[seg], line[seg + 1]
        out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    return out


def _median_point(pts: list):
    import statistics
    return (statistics.median(p[0] for p in pts), statistics.median(p[1] for p in pts))


def _cross_trace_bridge(start, end, config: ConsensusConfig, trace_lines: list[list]):
    """Rebuild a gap from the MEDIAN of all traces' points, not a single
    one. For partial-coverage corridors: no one trace spans the gap, but
    the union does. A backbone trace (closest to both ends) sets the
    rough path/order; each resampled anchor is then snapped to the median
    of nearby points across traces. Bins with fewer than
    cross_bridge_min_traces agreeing points keep the backbone — the
    agreement requirement filters noise (a lone spike is outvoted)."""
    gap = _gap_m(start, end)
    if (gap > config.max_trace_bridge_gap_m
            or len(trace_lines) < config.cross_bridge_min_traces):
        return None
    half_w = config.cross_bridge_corridor_m
    tol = max(config.max_weld_gap_m, config.connect_tolerance_m)

    # Backbone: the trace whose ends are closest to start and end (it sets
    # the corridor's shape and direction, even if gappy in the middle).
    backbone, best_score = None, float("inf")
    for line in trace_lines:
        if len(line) < 2:
            continue
        i = min(range(len(line)), key=lambda k: _gap_m(line[k], start))
        j = min(range(len(line)), key=lambda k: _gap_m(line[k], end))
        if i == j:
            continue
        ds, de = _gap_m(line[i], start), _gap_m(line[j], end)
        if ds > tol or de > tol:
            continue
        if ds + de < best_score:
            best_score = ds + de
            backbone = list(line[i : j + 1]) if i < j else list(reversed(line[j : i + 1]))
    if backbone is None:
        return None

    anchors = _resample_line([start, *backbone, end], 15.0)
    out: list = []
    contributing: set[int] = set()
    for a in anchors:
        near = []
        for ti, line in enumerate(trace_lines):
            p = min(line, key=lambda q: _gap_m(q, a))
            if _gap_m(p, a) <= half_w:
                near.append(p)
                contributing.add(ti)
        out.append(_median_point(near) if len(near) >= config.cross_bridge_min_traces else a)
    if len(contributing) < config.cross_bridge_min_traces:
        return None
    return out


def _chain_fragments(
    frags: list[ConsensusRoute], config: ConsensusConfig, trace_lines: list[list]
) -> list[list[ConsensusRoute]]:
    """Group fragments into chains connected by a fillable gap, each
    chain ordered head-to-tail."""
    remaining = list(frags)
    chains: list[list[ConsensusRoute]] = []
    while remaining:
        chain = [remaining.pop(0)]
        extended = True
        while extended:
            extended = False
            tail = chain[-1].geometry
            head = chain[0].geometry
            for i, frag in enumerate(remaining):
                fwd = frag.geometry
                rev = list(reversed(fwd))
                if _connector(tail, fwd, config, trace_lines)[0] is not None:
                    chain.append(remaining.pop(i))
                elif _connector(tail, rev, config, trace_lines)[0] is not None:
                    _reverse_route(frag)
                    chain.append(remaining.pop(i))
                elif _connector(fwd, head, config, trace_lines)[0] is not None:
                    chain.insert(0, remaining.pop(i))
                elif _connector(rev, head, config, trace_lines)[0] is not None:
                    _reverse_route(frag)
                    chain.insert(0, remaining.pop(i))
                else:
                    continue
                extended = True
                break
        chains.append(chain)
    return chains


def _reverse_route(route: ConsensusRoute) -> None:
    route.geometry = list(reversed(route.geometry))
    route.edges = list(reversed(route.edges))


def _concat_chain(
    chain: list[ConsensusRoute], label: str, direction_group: int,
    config: ConsensusConfig, trace_lines: list[list],
) -> ConsensusRoute:
    geometry: list = []
    edges: list = []
    trace_ids: list[str] = []
    bridges: list[list] = []
    joins: dict[str, int] = {"stitch": 0, "bridge": 0, "weld": 0, "cross": 0}
    for frag in chain:
        bridges.extend(frag.bridges)   # keep each fragment's own connectors
        if geometry:
            a_end = geometry[-1]
            connector, kind = _connector(geometry, frag.geometry, config, trace_lines)
            if kind in joins:
                joins[kind] += 1
            for p in connector:   # only "stitch" carries intermediate points
                if _gap_m(geometry[-1], p) > 0:
                    geometry.append(p)
            # The connector itself (a_end → intermediate points → frag start)
            # is an inferred bridge between two fragments.
            bridges.append([a_end, *connector, frag.geometry[0]])
        for p in frag.geometry:
            if not geometry or _gap_m(geometry[-1], p) > 0:
                geometry.append(p)
        edges.extend(frag.edges)
        trace_ids.extend(frag.trace_ids)
    return ConsensusRoute(
        ramal_label=label,
        direction_group=direction_group,
        edges=edges,
        geometry=geometry,
        trace_count=max((f.trace_count for f in chain), default=0),
        trace_ids=list(dict.fromkeys(trace_ids)),
        bridges=bridges,
        diagnostics={"merged_from": len(chain), **joins},
    )


def validate_ramales(
    routes: list[ConsensusRoute],
    traces_by_id: dict[str, MatchedTrace],
    config: ReconstructionConfig,
) -> tuple[list[ConsensusRoute], list[dict]]:
    """Plausibility filter for emitted ramales (per direction group).

    A ramal is a variant of the line, so it must be substantial:
    - tiny routes (length / trace support below the floor) are noise;
    - a route fully contained in a longer sibling's corridor (the A→B
      candidate of an A→C line) is kept only when its traces
      consistently span it end-to-end — otherwise it is partial riding
      around a popular stop, already represented by the sibling.

    The longest route of each direction group is always kept, so a
    group never validates down to nothing.
    """
    rc = config.ramales
    kept: list[ConsensusRoute] = []
    discarded: list[dict] = []

    by_group: dict[int, list[ConsensusRoute]] = {}
    for route in routes:
        by_group.setdefault(route.direction_group, []).append(route)

    def family(label: str) -> str:
        head, _, tail = label.rpartition(".")
        return head if head and tail.isdigit() else label

    for group_routes in by_group.values():
        ordered = sorted(group_routes, key=lambda r: -_length_m(r.geometry))
        group_kept: list[ConsensusRoute] = []
        for index, route in enumerate(ordered):
            length = _length_m(route.geometry)
            entry = {
                "label": route.ramal_label,
                "direction_group": route.direction_group,
                "length_m": round(length),
                "trace_count": route.trace_count,
            }
            if index == 0:  # group anchor: never discard everything
                group_kept.append(route)
                continue

            kept_families = {family(other.ramal_label) for other in group_kept}
            if family(route.ramal_label) in kept_families:
                # A fragment of an already-kept ramal: honest partial
                # evidence (unbridged gap), not a ramal candidate.
                if length < rc.min_fragment_length_m:
                    discarded.append({**entry, "reason": "fragment_debris"})
                    continue
                group_kept.append(route)
                continue

            if length < rc.min_ramal_length_m:
                discarded.append({**entry, "reason": "too_short"})
                continue
            if route.trace_count < rc.min_ramal_traces:
                discarded.append({**entry, "reason": "too_few_traces"})
                continue
            container = next(
                (
                    other for other in group_kept
                    if _contained_within(route.geometry, other.geometry, rc.distance_threshold_m)
                ),
                None,
            )
            if container is not None and not _terminus_consistent(route, traces_by_id, rc):
                discarded.append({
                    **entry,
                    "reason": "contained_without_consistent_termini",
                    "contained_in": container.ramal_label,
                })
                continue
            group_kept.append(route)
        kept.extend(group_kept)

    return kept, discarded


def _length_m(geometry: list) -> float:
    from geodata.geo_math import haversine_m

    return sum(
        haversine_m(a[0], a[1], b[0], b[1])
        for a, b in zip(geometry, geometry[1:])
    )


def _contained_within(geometry: list, container: list, tolerance_m: float) -> bool:
    """True when every point of `geometry` lies within tolerance of the
    container polyline — i.e. it adds no divergent stretch."""
    if len(geometry) < 2 or len(container) < 2:
        return False
    import shapely
    from shapely.geometry import LineString

    from .graph import _project_m

    ref_lat = container[0][1]
    line = LineString([_project_m(p, ref_lat) for p in container])
    points = shapely.points([_project_m(p, ref_lat) for p in geometry])
    return float(shapely.distance(line, points).max()) <= tolerance_m


def _terminus_consistent(
    route: ConsensusRoute,
    traces_by_id: dict[str, MatchedTrace],
    rc,
) -> bool:
    """Do this route's traces consistently span it end-to-end?

    Counts the share of supporting traces whose polyline starts within
    tolerance of one route endpoint and ends within tolerance of the
    other (either orientation). High share = a real sub-route variant
    whose buses genuinely terminate there.
    """
    from geodata.geo_math import haversine_m

    polylines = [
        traces_by_id[tid].matched_polyline
        for tid in route.trace_ids
        if tid in traces_by_id and len(traces_by_id[tid].matched_polyline) >= 2
    ]
    if len(polylines) < rc.min_ramal_traces:
        return False

    a, b = route.geometry[0], route.geometry[-1]

    def near(p, q) -> bool:
        return haversine_m(p[0], p[1], q[0], q[1]) <= rc.terminus_tolerance_m

    spanning = sum(
        1 for line in polylines
        if (near(line[0], a) and near(line[-1], b))
        or (near(line[0], b) and near(line[-1], a))
    )
    return spanning / len(polylines) >= rc.terminus_consistency_min_share


def _single_cluster(traces: list[MatchedTrace]) -> RamalGroup:
    """All traces as one corridor (top-down mode) — the longest trace seeds the
    reference geometry; divergences carve out the ramales."""
    longest = max(traces, key=lambda t: len(t.matched_polyline))
    return RamalGroup(
        label="main", traces=list(traces),
        medoid_polyline=longest.matched_polyline,
    )


def _corridor_spine(
    polylines: list[list],
    join_tol_m: float = 40.0,
    min_gain_m: float = 100.0,
    max_iters: int = 30,
) -> list:
    """A reference polyline spanning the *whole* corridor, stitched from the
    traces. The consensus projects edges onto its reference (arc_positions),
    which clamps anything beyond the reference's ends — so a single (partial)
    trace truncates the route at its own extent. Here we grow the longest trace
    by repeatedly grafting on the trace that passes near an end and reaches
    furthest beyond it, until nothing extends either end.
    """
    polys = [p for p in polylines if len(p) >= 2]
    if not polys:
        return []
    spine = list(max(polys, key=_length_m))

    def nearest(poly, pt):
        best_i, best_d = 0, float("inf")
        for i, v in enumerate(poly):
            d = haversine_m(pt[0], pt[1], v[0], v[1])
            if d < best_d:
                best_d, best_i = d, i
        return best_i, best_d

    for _ in range(max_iters):
        extended = False
        # Grow the END forward: a trace that passes near spine[-1] and continues.
        start, end = spine[0], spine[-1]
        best_tail, best_reach = None, _gap_m(start, end) + min_gain_m
        for p in polys:
            i, d = nearest(p, end)
            if d <= join_tol_m and i < len(p) - 1:
                tail = p[i + 1:]
                reach = _gap_m(start, tail[-1])
                if reach > best_reach:
                    best_reach, best_tail = reach, tail
        if best_tail:
            spine = spine + best_tail
            extended = True
        # Grow the START backward: a trace whose later portion passes near spine[0].
        start, end = spine[0], spine[-1]
        best_head, best_reach = None, _gap_m(end, start) + min_gain_m
        for p in polys:
            i, d = nearest(p, start)
            if d <= join_tol_m and i > 0:
                head = p[:i]
                reach = _gap_m(end, head[0])
                if reach > best_reach:
                    best_reach, best_head = reach, head
        if best_head:
            spine = best_head + spine
            extended = True
        if not extended:
            break
    return spine


def _consensus_with_divergence(
    cluster: RamalGroup,
    group_index: int,
    config: ReconstructionConfig,
    bridge_fn: BridgeFn | None,
    used_labels: set[str],
    max_depth: int = 1,
    overlap: bool = False,
) -> tuple[list[ConsensusRoute], dict]:
    """Consensus for one cluster, splitting at divergences.

    ``max_depth`` bounds how many times a branch may itself be split:
    1 = the classic single split (bottom-up "components" mode), higher =
    recursive top-down splitting ("divergence" mode), where the cluster starts
    as the whole corridor and is carved at each evidenced junction in turn.

    ``overlap`` (top-down) gives both sides of a split the *shared-trunk* traces
    — a trace that rides neither divergent branch supports both ramales — so the
    common trunk keeps full support in each instead of being starved by a hard
    partition.
    """
    routes, diags = _divergence_consensus(
        cluster.traces, cluster.label, cluster.medoid_polyline,
        group_index, config, bridge_fn, used_labels, max_depth, overlap,
        build_spine=overlap or max_depth > 1,
    )
    diag = diags[0]
    if len(diags) > 1:
        diag["splits"] = diags[1:]
    return routes, diag


def _divergence_consensus(
    traces: list[MatchedTrace],
    label: str,
    reference_polyline: list | None,
    group_index: int,
    config: ReconstructionConfig,
    bridge_fn: BridgeFn | None,
    used_labels: set[str],
    max_depth: int,
    overlap: bool = False,
    depth: int = 0,
    build_spine: bool = False,
) -> tuple[list[ConsensusRoute], list[dict]]:
    # Top-down: a single trace can't span the corridor, so stitch a full-span
    # reference from all the cluster's traces (else the route truncates at the
    # longest trace's reach). Other modes keep the longest-trace reference.
    if build_spine:
        spine = _corridor_spine([t.matched_polyline for t in traces])
        if len(spine) >= 2:
            reference_polyline = spine
    result = run_cluster_consensus(
        traces,
        config=config.consensus,
        reference_polyline=reference_polyline,
        bridge_fn=bridge_fn,
        ramal_label=label,
        direction_group=group_index,
    )
    diag = {"label": label, "depth": depth, **result.diagnostics}

    if depth >= max_depth or result.pruned is None or result.path is None:
        return result.routes, [diag]

    divergence = detect_divergence(
        result.pruned, result.path, traces, config.consensus
    )
    if divergence is None:
        return result.routes, [diag]

    if overlap:
        # Overlapping membership: a side gets every trace that doesn't ride the
        # *other* side's distinct edges — so shared-trunk traces (which ride
        # neither) feed both, keeping the common trunk fully supported.
        branch_users = set(divergence.branch_trace_ids)
        bypassed_users: set[str] = set()
        for edge in divergence.bypassed_edges:
            bypassed_users |= result.pruned.nodes.get(edge, set())
        trunk_traces = [t for t in traces if t.trace_id not in branch_users]
        branch_traces = [t for t in traces if t.trace_id not in bypassed_users]
    else:
        trunk_traces, branch_traces = split_by_divergence(traces, divergence)
    if not trunk_traces or not branch_traces:
        return result.routes, [diag]

    # Reject the split when the two competing variants are only a carriageway
    # apart: compare them where they truly differ — the branch chain vs the
    # path segment it bypasses.
    separation = _variant_separation_m(
        _ordered_geometry(divergence.branch_edges, result.pruned),
        _ordered_geometry(divergence.bypassed_edges, result.pruned),
    )
    if separation < config.consensus.divergence_min_separation_m:
        diag["divergence_rejected"] = {
            "reason": "parallel_carriageway",
            "max_separation_m": round(separation, 1),
        }
        return result.routes, [diag]

    branch_label = _next_label(used_labels)
    used_labels.add(branch_label)
    diag["divergence"] = {
        "branch_label": branch_label,
        "branch_traces": sorted(divergence.branch_trace_ids),
        "trunk_traces": sorted(divergence.trunk_trace_ids),
        "branch_edge_count": len(divergence.branch_edges),
        "max_separation_m": round(separation, 1),
    }

    # Recurse: each side may itself fork further (trunk-only/middle traces
    # carry no branch edges, so they stay with the trunk and never spawn a
    # ramal of their own).
    routes: list[ConsensusRoute] = []
    diags: list[dict] = [diag]
    for sub_label, subset in ((label, trunk_traces), (branch_label, branch_traces)):
        sub_routes, sub_diags = _divergence_consensus(
            subset, sub_label, None, group_index, config, bridge_fn,
            used_labels, max_depth, overlap, depth + 1, build_spine,
        )
        routes.extend(sub_routes)
        diags.extend(sub_diags)
    return routes, diags


def _primary_geometry(routes: list[ConsensusRoute]) -> list:
    if not routes:
        return []
    return max(routes, key=lambda r: len(r.edges)).geometry


def _ordered_geometry(edges: list, graph) -> list:
    """Concatenate the edges' geometries in sequence order."""
    coords: list = []
    for edge in edges:
        coords.extend(graph.geometries.get(edge, []))
    return coords


def _variant_separation_m(chain: list, bypassed: list) -> float:
    """Distance between the arc-length midpoints of two variants (m)."""
    if len(chain) < 2 or len(bypassed) < 2:
        return float("inf")  # missing evidence can't veto the split
    import math

    from .graph import _project_m

    ref_lat = chain[0][1]

    def midpoint(coords: list) -> tuple[float, float]:
        pts = [_project_m(p, ref_lat) for p in coords]
        cumulative = [0.0]
        for a, b in zip(pts, pts[1:]):
            cumulative.append(cumulative[-1] + math.dist(a, b))
        half = cumulative[-1] / 2
        for i in range(1, len(cumulative)):
            if cumulative[i] >= half:
                seg = cumulative[i] - cumulative[i - 1] or 1.0
                t = (half - cumulative[i - 1]) / seg
                return (
                    pts[i - 1][0] + t * (pts[i][0] - pts[i - 1][0]),
                    pts[i - 1][1] + t * (pts[i][1] - pts[i - 1][1]),
                )
        return pts[-1]

    return math.dist(midpoint(chain), midpoint(bypassed))


def _next_label(used: set[str]) -> str:
    n = 2
    while f"r{n}" in used:
        n += 1
    return f"r{n}"


# ---------------------------------------------------------------------------
# GeoJSON output
# ---------------------------------------------------------------------------

def output_to_geojson(output: ReconstructionOutput) -> dict[str, Any]:
    """One Feature per consensus edge, plus one per full route —
    properties carry confidence/inferred so viewers can style them."""
    features: list[dict[str, Any]] = []
    for route in output.routes:
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": [[lon, lat] for lon, lat in route.geometry],
            },
            "properties": {
                "kind": "route",
                "ramal_label": route.ramal_label,
                "direction_group": route.direction_group,
                "trace_count": route.trace_count,
                "edge_count": len(route.edges),
            },
        })
        for ce in route.edges:
            if not ce.geometry:
                continue
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[lon, lat] for lon, lat in ce.geometry],
                },
                "properties": {
                    "kind": "edge",
                    "ramal_label": route.ramal_label,
                    "direction_group": route.direction_group,
                    "edge_id": ce.edge.edge_id,
                    "forward": ce.edge.forward,
                    "confidence": round(ce.confidence, 3),
                    "inferred": ce.inferred,
                },
            })
    return {"type": "FeatureCollection", "features": features}


def save_output(output: ReconstructionOutput, path: str | Path) -> None:
    Path(path).write_text(json.dumps(output_to_geojson(output)))
