"""Raw GPS traces → MatchedTrace, via Valhalla HMM map matching.

Thin wrapper around ``geodata.match.trace_match`` (which already does
spike filtering of matched points, polyline6 decoding and on-disk
caching). This module only converts its output into routebuilder types
and applies quality gates.
"""

from __future__ import annotations

import hashlib
import logging
import math

from geodata.geo_math import haversine_m
from geodata.match import trace_match

from .config import CleaningConfig
from .types import DirectedEdge, LonLat, MatchedTrace, RawPoint

logger = logging.getLogger(__name__)


def cache_safe_id(trace_id: str, shape: list[dict]) -> str:
    """Cache id that changes whenever the input points change.

    The geodata trace cache keys on trace_id alone — a logical id that
    stays the same while its underlying points change (edited scenario,
    same name/seed) would silently serve stale matches. Appending a
    content hash makes that impossible while keeping cache hits for
    genuinely identical inputs.
    """
    digest = hashlib.sha1()
    for p in shape:
        digest.update(f"{p['lat']:.6f},{p['lon']:.6f},{p.get('time', '')};".encode())
    return f"{trace_id}@{digest.hexdigest()[:12]}"

# Pre-match thinning: a bus dwelling at a stop emits dozens of
# near-identical points that bloat the HMM request and get labelled
# "interpolated". Keep a point only if it moved or enough time passed.
THIN_MIN_DISTANCE_M = 5.0
THIN_HEARTBEAT_S = 30.0


def thin_points(points: list[RawPoint]) -> list[RawPoint]:
    if len(points) <= 2:
        return list(points)
    kept = [points[0]]
    for p in points[1:-1]:
        last = kept[-1]
        moved = haversine_m(last.lon, last.lat, p.lon, p.lat) >= THIN_MIN_DISTANCE_M
        waited = (
            p.timestamp is not None
            and last.timestamp is not None
            and (p.timestamp - last.timestamp).total_seconds() >= THIN_HEARTBEAT_S
        )
        if moved or waited:
            kept.append(p)
    kept.append(points[-1])
    return kept


def clean_trace(
    trace_id: str,
    points: list[RawPoint],
    config: CleaningConfig | None = None,
    *,
    device_id: str | None = None,
) -> MatchedTrace | None:
    """Map-match one raw trace. Returns None when the trace fails the
    quality gates (too few points, poor match, too few edges)."""
    config = config or CleaningConfig()

    points = thin_points(points)
    if len(points) < 2:
        logger.info("trace %s dropped: fewer than 2 points", trace_id)
        return None

    shape = []
    for p in points:
        entry: dict = {"lat": p.lat, "lon": p.lon}
        if p.timestamp is not None:
            entry["time"] = int(p.timestamp.timestamp())
        shape.append(entry)

    output = trace_match(
        shape,
        trace_id=cache_safe_id(trace_id, shape),
        costing=config.costing,
        search_radius=config.search_radius_m,
        gps_accuracy=config.gps_accuracy_m,
        turn_penalty_factor=config.turn_penalty_factor,
    )

    # Quality = fraction of points the HMM placed on the road network.
    # "interpolated" points (between matched anchors) are placements
    # too — only truly unmatched points count against the trace.
    if output.matched_points:
        unmatched = sum(
            1 for mp in output.matched_points if mp.get("type") == "unmatched"
        )
        quality = 1.0 - unmatched / len(output.matched_points)
    else:
        quality = output.match_score

    if quality < config.min_match_quality:
        logger.info(
            "trace %s dropped: match quality %.2f < %.2f",
            trace_id, quality, config.min_match_quality,
        )
        return None

    trace = matched_trace_from_valhalla(
        trace_id,
        edges=output.edges,
        shape_coords=output.shape_coords,
        matched_points=output.matched_points,
        match_quality=quality,
        device_id=device_id,
        started_at=points[0].timestamp,
        max_edge_detour_m=config.max_edge_detour_m,
        edge_corner_dev_m=config.edge_corner_dev_m,
    )

    if len(trace.edges) < config.min_edges:
        logger.info(
            "trace %s dropped: %d matched edges < %d",
            trace_id, len(trace.edges), config.min_edges,
        )
        return None

    return trace


def matched_trace_from_valhalla(
    trace_id: str,
    *,
    edges: list[dict],
    shape_coords: list[tuple[float, float]],
    matched_points: list[dict] | None = None,
    match_quality: float = 1.0,
    device_id: str | None = None,
    started_at=None,
    max_edge_detour_m: float = 0.0,
    edge_corner_dev_m: float = 0.0,
) -> MatchedTrace:
    """Build a MatchedTrace from raw Valhalla trace_attributes output.

    ``shape_coords`` is the decoded polyline6 shape in (lat, lon) order;
    each edge dict carries ``id``, ``forward`` and
    ``begin_shape_index``/``end_shape_index`` slicing into that shape.
    The slices are already oriented in travel direction.
    """
    directed: list[DirectedEdge] = []
    geometries: dict[DirectedEdge, list[LonLat]] = {}

    # Clean detour spikes from the edge shapes: the matched points are
    # the ground-truth band (they hug the road); a trace_attributes edge
    # vertex that strays far from them is a routing artifact at an
    # intersection, not where the bus went.
    clean_band = [
        (float(mp["lon"]), float(mp["lat"]))
        for mp in (matched_points or [])
        if mp.get("type") in ("matched", "interpolated") and "lon" in mp and "lat" in mp
    ]
    band = (
        _PointBand(clean_band, max_edge_detour_m)
        if max_edge_detour_m > 0 and len(clean_band) >= 2
        else None
    )

    # Matched GPS points grouped by the edge they were snapped to, in
    # order along that edge — used to rebuild edges whose shape cut a
    # corner the points round.
    pts_by_edge: dict[int, list[LonLat]] = {}
    if edge_corner_dev_m > 0:
        ordered: dict[int, list[tuple[float, LonLat]]] = {}
        for mp in matched_points or []:
            ei = mp.get("edge_index")
            if ei is None or mp.get("type") not in ("matched", "interpolated") or "lon" not in mp:
                continue
            ordered.setdefault(ei, []).append(
                (float(mp.get("distance_along_edge", 0.0)), (float(mp["lon"]), float(mp["lat"])))
            )
        pts_by_edge = {ei: [ll for _, ll in sorted(v)] for ei, v in ordered.items()}

    for idx, edge in enumerate(edges):
        de = DirectedEdge(int(edge["id"]), bool(edge.get("forward", True)))
        begin = edge.get("begin_shape_index")
        end = edge.get("end_shape_index")
        geometry: list[LonLat] = []
        if begin is not None and end is not None and end >= begin:
            geometry = [(lon, lat) for lat, lon in shape_coords[begin : end + 1]]
            geometry = _refine_edge_geometry(
                geometry, pts_by_edge.get(idx, []), edge_corner_dev_m
            )
            geometry = _despike_geometry(geometry, band, max_edge_detour_m)

        # Collapse consecutive repeats of the same directed edge,
        # extending the geometry instead of duplicating the node.
        if directed and directed[-1] == de:
            if geometry:
                existing = geometries.get(de, [])
                geometries[de] = _weld(existing, geometry)
            continue

        directed.append(de)
        if de not in geometries or len(geometry) > len(geometries[de]):
            if geometry:
                geometries[de] = geometry

    if matched_points is not None:
        polyline = [
            (float(mp["lon"]), float(mp["lat"]))
            for mp in matched_points
            if mp.get("type") in ("matched", "interpolated") and "lon" in mp and "lat" in mp
        ]
    else:
        polyline = [(lon, lat) for lat, lon in shape_coords]

    return MatchedTrace(
        trace_id=trace_id,
        edges=directed,
        edge_geometries=geometries,
        matched_polyline=polyline,
        match_quality=match_quality,
        device_id=device_id,
        started_at=started_at,
    )


class _PointBand:
    """Coarse meter-grid of points for ``min_dist_m`` queries.

    Cell size equals the query radius, so a 3x3 neighbourhood is
    guaranteed to contain any point within that radius.
    """

    def __init__(self, points: list[LonLat], cell_m: float):
        ref_lat = points[0][1]
        self.mlon = 111_320 * math.cos(math.radians(ref_lat))
        self.mlat = 110_540
        self.cell = max(cell_m, 1.0)
        self.grid: dict[tuple[int, int], list[LonLat]] = {}
        for p in points:
            self.grid.setdefault(self._key(p), []).append(p)

    def _key(self, p: LonLat) -> tuple[int, int]:
        return (int(p[0] * self.mlon // self.cell), int(p[1] * self.mlat // self.cell))

    def min_dist_m(self, p: LonLat) -> float:
        kx, ky = self._key(p)
        best = float("inf")
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for q in self.grid.get((kx + dx, ky + dy), ()):
                    d = math.hypot((q[0] - p[0]) * self.mlon, (q[1] - p[1]) * self.mlat)
                    if d < best:
                        best = d
        return best


def _seg_dist_m(p, a, b) -> float:
    """Distance (m) from point p to segment a-b, all (lon, lat)."""
    mlon = 111_320 * math.cos(math.radians(p[1]))
    mlat = 110_540
    px, py = p[0] * mlon, p[1] * mlat
    ax, ay = a[0] * mlon, a[1] * mlat
    bx, by = b[0] * mlon, b[1] * mlat
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    if L2 == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _refine_edge_geometry(
    shape_geom: list[LonLat], pt_geom: list[LonLat], dev_thresh_m: float
) -> list[LonLat]:
    """Rebuild an edge's geometry from its matched GPS points when the
    Valhalla shape under-resolved it (cut a corner). The points are kept
    only if they bow more than dev_thresh_m off the shape line; otherwise
    the cleaner shape is used as-is."""
    if dev_thresh_m <= 0 or len(pt_geom) < 2 or len(shape_geom) < 2:
        return shape_geom
    dev = max(
        min(_seg_dist_m(p, shape_geom[k], shape_geom[k + 1])
            for k in range(len(shape_geom) - 1))
        for p in pt_geom
    )
    if dev <= dev_thresh_m:
        return shape_geom
    # Anchor at the edge's nodes, follow the matched points between them.
    out = [shape_geom[0]]
    for p in (*pt_geom, shape_geom[-1]):
        if haversine_m(out[-1][0], out[-1][1], p[0], p[1]) > 0.5:
            out.append(p)
    return out if len(out) >= 2 else shape_geom


def _despike_geometry(
    geometry: list[LonLat], band: "_PointBand | None", max_dev_m: float
) -> list[LonLat]:
    """Drop edge-shape vertices that stray > max_dev_m from the matched
    band (intersection routing detours). Keep the original if filtering
    would leave fewer than 2 points (the whole edge is off-band — let the
    support graph's pruning decide rather than fabricating geometry)."""
    if band is None or max_dev_m <= 0 or len(geometry) < 2:
        return geometry
    kept = [p for p in geometry if band.min_dist_m(p) <= max_dev_m]
    return kept if len(kept) >= 2 else geometry


def _weld(a: list[LonLat], b: list[LonLat]) -> list[LonLat]:
    if not a:
        return list(b)
    if not b:
        return list(a)
    if a[-1] == b[0]:
        return a + b[1:]
    return a + b
