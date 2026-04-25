"""DBSCAN-based route reconstruction from pooled resampled trips (pipeline step 5).

Algorithm
---------
1. Pool all ResampledTripPoints for the selected trips into one point cloud.
2. Run DBSCAN with haversine distance (no projection needed, works on WGS-84).
3. For each cluster, compute:
   - centroid (mean lat/lon of member points)
   - mean point_index (used for sequential ordering — see note below)
   - contributing trip count (used for confidence)
4. Sort clusters by mean point_index → gives along-route order because all
   trips were resampled at the same interval going in the same direction:
   point_index 0 is always the start, N is always the end.
5. Build a RouteSegment (LineString) between every pair of consecutive centroids.
6. Persist as a versioned RouteEstimation; supersede any previous estimations.

Typical usage
-------------
    result = cluster_route(db, line_id, interval_meters=20.0, eps_meters=30.0)
    print(result.n_clusters, "clusters →", result.n_segments, "segments")

If the batch contains mixed-direction trips, run direction validation first and
pass only the forward (or reverse) IDs via ``resampled_trip_ids``:

    from geodata.validate import validate_trip_directions
    val = validate_trip_directions(db, line_id, interval_meters=20.0)
    fwd_ids = [t.resampled_trip_id for t in val.forward_trips]
    result = cluster_route(db, line_id, interval_meters=20.0,
                           resampled_trip_ids=fwd_ids)
"""

from dataclasses import dataclass
import math
from uuid import UUID

import numpy as np
from geoalchemy2.shape import from_shape
from shapely.geometry import LineString
from sklearn.cluster import DBSCAN
from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import (
    Line,
    ResampledTrip,
    ResampledTripPoint,
    Route,
    RouteEdge,
    RouteSource,
    RouteStatus,
    Trip,
)

from .geo_math import haversine_m
from .telemetry import tracer


_EARTH_RADIUS_M = 6_371_000.0


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass
class ClusterRouteResult:
    route: Route
    n_trips: int          # trips included in clustering
    n_points_total: int   # pooled points fed to DBSCAN
    n_noise_points: int   # points labelled noise (-1)
    n_clusters: int       # DBSCAN clusters found
    n_segments: int       # RouteEdges saved


@dataclass
class ClusterPreviewResult:
    """Notebook-local clustering result with GeoJSON output."""

    line_id: UUID
    route_coordinates: list[list[float]]
    geojson: dict
    n_traces: int
    n_points_total: int
    n_noise_points: int
    n_clusters: int
    min_samples: int
    ordering_method: str


@dataclass
class _ClusterCoreResult:
    """Pure cluster statistics reused by preview and persistence flows."""

    cluster_stats: list[dict]
    n_points_total: int
    n_noise_points: int
    n_clusters: int
    min_samples: int
    ordering_method: str


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def cluster_route(
    db: Session,
    line_id: UUID,
    interval_meters: float,
    *,
    min_match_score: float | None = None,
    resampled_trip_ids: list[UUID] | None = None,
    eps_meters: float = 30.0,
    min_samples: int | None = None,
) -> ClusterRouteResult:
    """Run DBSCAN on pooled resampled trips and persist a RouteEstimation.

    Parameters
    ----------
    db:
        SQLAlchemy session.
    line_id:
        Line to reconstruct.
    interval_meters:
        Must match an existing ResampledTrip batch (e.g. 20.0).
    min_match_score:
        Match-score filter — mirrors the notebook dropdown.  Ignored when
        ``resampled_trip_ids`` is provided.
    resampled_trip_ids:
        Explicit allowlist of ResampledTrip IDs to include.  Use this to pass
        only the forward (or reverse) trips after direction validation.
        When None, all trips for the given (line, interval, score) are used.
    eps_meters:
        DBSCAN neighbourhood radius in metres.  30 m works well for 20 m
        resampling; tighten to ~15 m on grids with closely-spaced parallel
        roads.
    min_samples:
        DBSCAN core-point threshold.  Defaults to ``max(2, n_trips // 3)``.
        A point must appear in at least this many trips to anchor a cluster.

    Returns
    -------
    ClusterRouteResult
        The persisted RouteEstimation and summary statistics.

    Raises
    ------
    ValueError
        If the line is not found, no points are available, or fewer than two
        clusters are produced (all points noise or single cluster).
    """
    with tracer.start_as_current_span(
        "cluster_route",
        attributes={
            "line_id": str(line_id),
            "interval_meters": interval_meters,
            "eps_meters": eps_meters,
        },
    ) as span:
        line = db.get(Line, line_id)
        if not line:
            raise ValueError(f"Line {line_id} not found")

        # ------------------------------------------------------------------
        # 1. Load resampled trips
        # ------------------------------------------------------------------
        if resampled_trip_ids is not None:
            resampled_trips = db.execute(
                select(ResampledTrip).where(
                    ResampledTrip.id.in_(resampled_trip_ids)
                )
            ).scalars().all()
        else:
            score_filter = (
                ResampledTrip.match_score.is_(None)
                if min_match_score is None
                else ResampledTrip.match_score == min_match_score
            )
            resampled_trips = db.execute(
                select(ResampledTrip)
                .join(Trip, ResampledTrip.trip_id == Trip.id)
                .where(
                    Trip.line_id == line_id,
                    ResampledTrip.interval_meters == interval_meters,
                    score_filter,
                )
            ).scalars().all()

        n_trips = len(resampled_trips)
        span.set_attribute("trips.total", n_trips)

        if n_trips == 0:
            raise ValueError(
                f"No resampled trips found for line {line_id} "
                f"at interval={interval_meters} m"
            )

        # ------------------------------------------------------------------
        # 2. Pool all points
        # ------------------------------------------------------------------
        # Each row: [lat, lon, point_index, resampled_trip_id_index]
        rows: list[tuple[float, float, int, int]] = []
        trip_index: dict[UUID, int] = {rt.id: i for i, rt in enumerate(resampled_trips)}

        for rt in resampled_trips:
            pts = db.execute(
                select(ResampledTripPoint)
                .where(ResampledTripPoint.resampled_trip_id == rt.id)
                .order_by(ResampledTripPoint.point_index)
            ).scalars().all()
            for p in pts:
                rows.append((p.latitude, p.longitude, p.point_index, trip_index[rt.id]))

        if len(rows) < 2:
            raise ValueError(
                f"Not enough points for line {line_id} after pooling "
                f"({len(rows)} points total)"
            )

        core = _cluster_rows(
            rows,
            n_traces=n_trips,
            eps_meters=eps_meters,
            min_samples=min_samples,
        )

        span.set_attributes({
            "dbscan.eps_meters": eps_meters,
            "dbscan.min_samples": core.min_samples,
            "dbscan.n_points": core.n_points_total,
            "dbscan.n_clusters": core.n_clusters,
            "dbscan.n_noise": core.n_noise_points,
        })

        # ------------------------------------------------------------------
        # 6. Supersede any previous estimations for this line
        # ------------------------------------------------------------------
        previous = db.execute(
            select(Route)
            .where(
                Route.line_id == line_id,
                Route.status != RouteStatus.SUPERSEDED,
            )
        ).scalars().all()

        next_version = 1
        for prev in previous:
            if prev.version >= next_version:
                next_version = prev.version + 1
            prev.status = RouteStatus.SUPERSEDED
            db.add(prev)

        # ------------------------------------------------------------------
        # 7. Persist Route + RouteEdges
        # ------------------------------------------------------------------
        route = Route(
            line_id=line_id,
            version=next_version,
            source=RouteSource.COMPUTED,
            status=RouteStatus.PENDING,
            trip_count=n_trips,
        )
        db.add(route)
        db.flush()

        n_segments = 0
        for seq, (cs_a, cs_b) in enumerate(
            zip(core.cluster_stats[:-1], core.cluster_stats[1:])
        ):
            confidence = min(cs_a["distinct_trips"], cs_b["distinct_trips"]) / n_trips
            path = from_shape(
                LineString([
                    (cs_a["centroid_lon"], cs_a["centroid_lat"]),
                    (cs_b["centroid_lon"], cs_b["centroid_lat"]),
                ]),
                srid=4326,
            )
            db.add(RouteEdge(
                route_id=route.id,
                sequence=seq,
                path=path,
                confidence=confidence,
            ))
            n_segments += 1

        # Migrate votes from superseded routes
        db.flush()
        for prev in previous:
            from .migrate_votes import migrate_votes_to_new_route

            migrate_votes_to_new_route(db, prev.id, route.id)

        db.commit()

        span.set_attributes({
            "route.id": str(route.id),
            "route.version": next_version,
            "segments.saved": n_segments,
        })

        return ClusterRouteResult(
            route=route,
            n_trips=n_trips,
            n_points_total=core.n_points_total,
            n_noise_points=core.n_noise_points,
            n_clusters=core.n_clusters,
            n_segments=n_segments,
        )


def cluster_traces_preview(
    line_id: UUID,
    traces: list,
    *,
    eps_meters: float = 30.0,
    min_samples: int | None = None,
) -> ClusterPreviewResult:
    """Preview a DBSCAN consensus route from in-memory grouped traces."""

    rows: list[tuple[float, float, int, int]] = []
    for trace_idx, trace in enumerate(traces):
        points = getattr(trace, "points", [])
        for fallback_idx, point in enumerate(points):
            latitude = float(getattr(point, "latitude"))
            longitude = float(getattr(point, "longitude"))
            point_index = int(getattr(point, "point_index", fallback_idx))
            rows.append((latitude, longitude, point_index, trace_idx))

    core = _cluster_rows(
        rows,
        n_traces=len(traces),
        eps_meters=eps_meters,
        min_samples=min_samples,
    )
    route_coordinates = [
        [cluster["centroid_lon"], cluster["centroid_lat"]]
        for cluster in core.cluster_stats
    ]
    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "strategy": "DBSCAN consensus (preview)",
                    "line_id": str(line_id),
                    "trace_count": len(traces),
                    "point_count": core.n_points_total,
                    "cluster_count": core.n_clusters,
                    "ordering_method": core.ordering_method,
                },
                "geometry": {
                    "type": "LineString",
                    "coordinates": route_coordinates,
                },
            }
        ],
    }
    return ClusterPreviewResult(
        line_id=line_id,
        route_coordinates=route_coordinates,
        geojson=geojson,
        n_traces=len(traces),
        n_points_total=core.n_points_total,
        n_noise_points=core.n_noise_points,
        n_clusters=core.n_clusters,
        min_samples=core.min_samples,
        ordering_method=core.ordering_method,
    )


def _cluster_rows(
    rows: list[tuple[float, float, int, int]],
    *,
    n_traces: int,
    eps_meters: float,
    min_samples: int | None,
) -> _ClusterCoreResult:
    """Cluster pooled trace points and return ordered cluster statistics."""

    if n_traces <= 0:
        raise ValueError("At least one trace is required for reconstruction")
    if len(rows) < 2:
        raise ValueError("At least 2 pooled points are required for reconstruction")

    arr = np.array(rows)
    coords = arr[:, :2]
    point_indices = arr[:, 2]
    trip_idx_col = arr[:, 3]

    effective_min_samples = min_samples if min_samples is not None else max(2, n_traces // 3)
    eps_rad = eps_meters / _EARTH_RADIUS_M

    labels = DBSCAN(
        eps=eps_rad,
        min_samples=effective_min_samples,
        algorithm="ball_tree",
        metric="haversine",
    ).fit_predict(np.radians(coords))

    n_noise = int(np.sum(labels == -1))
    unique_labels = sorted(lbl for lbl in set(labels) if lbl != -1)
    n_clusters = len(unique_labels)

    if n_clusters < 2:
        raise ValueError(
            f"DBSCAN produced {n_clusters} cluster(s) — need at least 2 to "
            f"form a route. Try increasing eps_meters or reducing min_samples."
        )

    cluster_stats: list[dict] = []
    for lbl in unique_labels:
        mask = labels == lbl
        cluster_coords = coords[mask]
        cluster_pidx = point_indices[mask]
        cluster_trips = trip_idx_col[mask]

        cluster_stats.append(
            {
                "label": lbl,
                "centroid_lat": float(np.mean(cluster_coords[:, 0])),
                "centroid_lon": float(np.mean(cluster_coords[:, 1])),
                "mean_point_index": float(np.mean(cluster_pidx)),
                "distinct_trips": len(np.unique(cluster_trips)),
            }
        )

    cluster_stats, ordering_method = _order_clusters_by_learned_centerline(cluster_stats)
    return _ClusterCoreResult(
        cluster_stats=cluster_stats,
        n_points_total=len(rows),
        n_noise_points=n_noise,
        n_clusters=n_clusters,
        min_samples=effective_min_samples,
        ordering_method=ordering_method,
    )


def _order_clusters_by_learned_centerline(
    cluster_stats: list[dict],
) -> tuple[list[dict], str]:
    """Order centroids by projection onto a learned geometric backbone.

    Mean point index works only when all traces share the same route origin.
    With partial traces starting mid-route, centroid geometry is more reliable
    than local point indices. We therefore learn a centerline from the centroid
    cloud itself:

    1. Build the minimum-spanning tree over centroid distances.
    2. Take the tree diameter as the route backbone.
    3. Project every centroid onto that backbone and sort by arclength.
    """

    if len(cluster_stats) <= 2:
        ordered = sorted(cluster_stats, key=lambda c: c["mean_point_index"])
        return ordered, "mean_point_index_fallback"

    points = [
        (cluster["centroid_lon"], cluster["centroid_lat"])
        for cluster in cluster_stats
    ]
    distance_matrix = _pairwise_centroid_distances(points)
    backbone_indices = _tree_diameter_path(_minimum_spanning_tree(distance_matrix))

    if len(backbone_indices) < 2:
        ordered = sorted(cluster_stats, key=lambda c: c["mean_point_index"])
        return ordered, "mean_point_index_fallback"

    backbone_points = [points[idx] for idx in backbone_indices]
    projections = []
    for idx, cluster in enumerate(cluster_stats):
        arclength_m, lateral_offset_m = _project_onto_polyline(
            points[idx],
            backbone_points,
        )
        projections.append((arclength_m, lateral_offset_m, idx))

    projections.sort(key=lambda item: (item[0], item[1], item[2]))
    ordered = [cluster_stats[idx] for _, _, idx in projections]
    if ordered and ordered[0]["mean_point_index"] > ordered[-1]["mean_point_index"]:
        ordered.reverse()
    return ordered, "learned_centerline_mst_diameter"


def _pairwise_centroid_distances(
    points: list[tuple[float, float]],
) -> list[list[float]]:
    matrix = [[0.0 for _ in points] for _ in points]
    for i in range(len(points)):
        lon_i, lat_i = points[i]
        for j in range(i + 1, len(points)):
            lon_j, lat_j = points[j]
            distance = haversine_m(lon_i, lat_i, lon_j, lat_j)
            matrix[i][j] = distance
            matrix[j][i] = distance
    return matrix


def _minimum_spanning_tree(distance_matrix: list[list[float]]) -> dict[int, list[tuple[int, float]]]:
    node_count = len(distance_matrix)
    adjacency: dict[int, list[tuple[int, float]]] = {idx: [] for idx in range(node_count)}
    visited = {0}
    best_edge: list[tuple[float, int, int]] = []

    def push_edges(source: int) -> None:
        for target, weight in enumerate(distance_matrix[source]):
            if target in visited or source == target:
                continue
            best_edge.append((weight, source, target))

    push_edges(0)
    while len(visited) < node_count and best_edge:
        best_edge.sort(key=lambda item: item[0])
        weight, source, target = best_edge.pop(0)
        if target in visited:
            continue
        visited.add(target)
        adjacency[source].append((target, weight))
        adjacency[target].append((source, weight))
        push_edges(target)
    return adjacency


def _tree_diameter_path(
    adjacency: dict[int, list[tuple[int, float]]],
) -> list[int]:
    start = next(iter(adjacency))
    furthest_from_start, _distance, _parents = _furthest_tree_node(start, adjacency)
    furthest_from_end, _distance, parents = _furthest_tree_node(furthest_from_start, adjacency)

    path = [furthest_from_end]
    current = furthest_from_end
    while current != furthest_from_start:
        current = parents[current]
        path.append(current)
    path.reverse()
    return path


def _furthest_tree_node(
    start: int,
    adjacency: dict[int, list[tuple[int, float]]],
) -> tuple[int, float, dict[int, int]]:
    parents: dict[int, int] = {start: start}
    distances: dict[int, float] = {start: 0.0}
    stack = [start]
    visit_order = [start]

    while stack:
        current = stack.pop()
        for neighbor, weight in adjacency.get(current, []):
            if neighbor in distances:
                continue
            parents[neighbor] = current
            distances[neighbor] = distances[current] + weight
            stack.append(neighbor)
            visit_order.append(neighbor)

    furthest = max(visit_order, key=lambda node: distances[node])
    return furthest, distances[furthest], parents


def _project_onto_polyline(
    point: tuple[float, float],
    polyline: list[tuple[float, float]],
) -> tuple[float, float]:
    """Return (arclength_m, lateral_offset_m) for a point projected to a polyline."""

    if len(polyline) == 1:
        return 0.0, haversine_m(point[0], point[1], polyline[0][0], polyline[0][1])

    reference_lon = sum(lon for lon, _ in polyline) / len(polyline)
    reference_lat = sum(lat for _, lat in polyline) / len(polyline)
    point_xy = _lon_lat_to_xy(point[0], point[1], reference_lon, reference_lat)
    line_xy = [
        _lon_lat_to_xy(lon, lat, reference_lon, reference_lat)
        for lon, lat in polyline
    ]

    best_arclength = 0.0
    best_offset = float("inf")
    cumulative = 0.0
    for start_xy, end_xy in zip(line_xy, line_xy[1:], strict=False):
        segment_dx = end_xy[0] - start_xy[0]
        segment_dy = end_xy[1] - start_xy[1]
        segment_length = math.hypot(segment_dx, segment_dy)
        if segment_length <= 1e-6:
            continue

        rel_x = point_xy[0] - start_xy[0]
        rel_y = point_xy[1] - start_xy[1]
        t = max(0.0, min(1.0, (rel_x * segment_dx + rel_y * segment_dy) / (segment_length ** 2)))
        proj_x = start_xy[0] + t * segment_dx
        proj_y = start_xy[1] + t * segment_dy
        offset = math.hypot(point_xy[0] - proj_x, point_xy[1] - proj_y)
        if offset < best_offset:
            best_offset = offset
            best_arclength = cumulative + t * segment_length
        cumulative += segment_length

    return best_arclength, best_offset


def _lon_lat_to_xy(
    lon: float,
    lat: float,
    reference_lon: float,
    reference_lat: float,
) -> tuple[float, float]:
    ref_lat_rad = math.radians(reference_lat)
    x = math.radians(lon - reference_lon) * _EARTH_RADIUS_M * max(1e-9, math.cos(ref_lat_rad))
    y = math.radians(lat - reference_lat) * _EARTH_RADIUS_M
    return (x, y)
