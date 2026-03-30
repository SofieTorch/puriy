"""DBSCAN-based route reconstruction from pooled clean trip vertices.

Algorithm
---------
1. Pool all vertices from each Trip.computed_path across all trips.
2. Run DBSCAN with haversine distance on the raw (lat, lon) vertices.
3. Select the largest non-noise cluster — this is the main road.
4. Order those vertices along the route using PCA on the first principal
   component (robust to slight curves; handles bidirectionality).
5. Spatially thin the ordered sequence: keep one vertex per ``thin_meters``
   of arc length.
6. The thinned sequence becomes the reconstructed route.

Why the largest cluster is the road
------------------------------------
Because GPS points are very dense (small gaps between consecutive vertices),
road points cluster tightly together and dominate by count.  Noise points
(GPS jumps, bad map-match snaps) are sparse and either form tiny clusters
or are labelled as noise by DBSCAN.

Typical usage
-------------
    result = filter_cluster_route(db, line_id, eps_meters=30.0)
    print(result.n_kept_segments, "vertices kept →", result.n_route_segments, "route segments")
"""

from dataclasses import dataclass, field
from uuid import UUID

import numpy as np
from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import LineString
from sklearn.cluster import DBSCAN
from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import (
    EstimationStatus,
    Line,
    RouteEstimation,
    RouteSegment,
    Trip,
)

from ...telemetry import tracer


_EARTH_RADIUS_M = 6_371_000.0


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class ClusterSegment:
    """A single trip segment (consecutive vertex pair) with its cluster info.

    A segment is considered *kept* when both its start and end vertex
    are in the main (largest) cluster.
    """
    start_lat: float
    start_lon: float
    end_lat: float
    end_lon: float
    cluster_label: int   # label of the start vertex; -1 = noise
    kept: bool           # True if both endpoints are in the main cluster


@dataclass
class FilteredRouteResult:
    estimation: RouteEstimation
    n_trips: int
    n_segments_total: int     # total vertices pooled across all trips
    n_noise_segments: int     # vertices labelled as noise (-1)
    n_clusters: int           # DBSCAN clusters found
    n_small_clusters: int     # clusters that are not the main cluster
    n_kept_segments: int      # vertices in the main cluster
    n_route_segments: int     # RouteSegments saved in the estimation
    cluster_segments: list[ClusterSegment] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _load_trips(
    db: Session,
    line_id: UUID,
    min_match_score: float | None,
    trip_ids: list[UUID] | None,
) -> list[Trip]:
    """Load clean trips, either by explicit IDs or by line + score filter."""
    if trip_ids is not None:
        trips = db.execute(
            select(Trip).where(Trip.id.in_(trip_ids))
        ).scalars().all()
    else:
        q = select(Trip).where(
            Trip.line_id == line_id,
            Trip.computed_path.is_not(None),
        )
        if min_match_score is not None:
            q = q.where(Trip.match_score >= min_match_score)
        trips = db.execute(q).scalars().all()

    if not trips:
        raise ValueError(
            f"No clean trips found for line {line_id}"
            + (f" with match_score >= {min_match_score}" if min_match_score is not None else "")
        )
    return trips


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine distance in metres between two (lat, lon) points."""
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = np.sin(dlat / 2) ** 2 + np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) * np.sin(dlon / 2) ** 2
    return 2 * _EARTH_RADIUS_M * np.arcsin(np.sqrt(a))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def filter_cluster_route(
    db: Session,
    line_id: UUID,
    *,
    min_match_score: float | None = None,
    trip_ids: list[UUID] | None = None,
    eps_meters: float = 30.0,
    min_samples: int | None = None,
    min_cluster_segments: int = 0,
    thin_meters: float | None = None,
) -> FilteredRouteResult:
    """Cluster trip vertices via DBSCAN, select the main road cluster, build route.

    All vertices from every trip's computed_path are pooled and clustered by
    geographic proximity.  The largest non-noise cluster is taken as the main
    road.  Its vertices are ordered along the route using PCA, spatially
    thinned, and persisted as a RouteEstimation.

    Parameters
    ----------
    db:
        SQLAlchemy session.
    line_id:
        Line to reconstruct.
    min_match_score:
        Only include trips with ``match_score >= min_match_score``.
        Ignored when ``trip_ids`` is provided.
    trip_ids:
        Explicit allowlist of Trip IDs.
    eps_meters:
        DBSCAN neighbourhood radius in metres.
    min_samples:
        DBSCAN core-point threshold.  Defaults to ``max(2, n_trips // 3)``.
    min_cluster_segments:
        Kept for API compatibility; not used in the new algorithm.
    thin_meters:
        Spatial thinning step: only keep a vertex when it is at least this
        far from the previous kept vertex.  Defaults to ``eps_meters``.

    Returns
    -------
    FilteredRouteResult
    """
    _thin_meters = thin_meters if thin_meters is not None else eps_meters

    with tracer.start_as_current_span(
        "filter_cluster_route",
        attributes={
            "line_id": str(line_id),
            "eps_meters": eps_meters,
            "thin_meters": _thin_meters,
        },
    ) as span:
        line = db.get(Line, line_id)
        if not line:
            raise ValueError(f"Line {line_id} not found")

        # ------------------------------------------------------------------
        # 1. Load clean trips
        # ------------------------------------------------------------------
        trips = _load_trips(db, line_id, min_match_score, trip_ids)
        n_trips = len(trips)
        span.set_attribute("trips.total", n_trips)

        # ------------------------------------------------------------------
        # 2. Pool all vertices from every trip's computed_path
        # ------------------------------------------------------------------
        points: list[tuple[float, float]] = []    # (lat, lon)
        point_trip_indices: list[int] = []
        trip_vertex_slices: list[tuple[int, int]] = []

        for trip_idx, trip in enumerate(trips):
            geom = to_shape(trip.computed_path)
            coords = list(geom.coords)            # [(lon, lat, ...), ...]
            slice_start = len(points)
            for coord in coords:
                lon, lat = coord[0], coord[1]
                points.append((lat, lon))
                point_trip_indices.append(trip_idx)
            trip_vertex_slices.append((slice_start, len(points)))

        n_total = len(points)
        if n_total < 2:
            raise ValueError(
                f"Not enough vertices for line {line_id} after pooling "
                f"({n_total} vertices total)"
            )

        pts_arr = np.array(points)   # shape (N, 2) — (lat, lon)

        # ------------------------------------------------------------------
        # 3. Run DBSCAN on vertices
        # ------------------------------------------------------------------
        effective_min_samples = (
            min_samples if min_samples is not None else max(2, n_trips // 3)
        )
        eps_rad = eps_meters / _EARTH_RADIUS_M

        labels = DBSCAN(
            eps=eps_rad,
            min_samples=effective_min_samples,
            algorithm="ball_tree",
            metric="haversine",
        ).fit_predict(np.radians(pts_arr))

        n_noise = int(np.sum(labels == -1))
        unique_labels = sorted(lbl for lbl in set(labels) if lbl != -1)
        n_clusters = len(unique_labels)

        span.set_attributes({
            "dbscan.n_clusters": n_clusters,
            "dbscan.n_noise": n_noise,
            "dbscan.n_vertices": n_total,
        })

        if n_clusters == 0:
            raise ValueError(
                f"DBSCAN found no clusters for line {line_id}. "
                f"Try increasing eps_meters or reducing min_samples."
            )

        # ------------------------------------------------------------------
        # 4. Select the largest cluster — this is the main road
        # ------------------------------------------------------------------
        cluster_sizes = {lbl: int(np.sum(labels == lbl)) for lbl in unique_labels}
        main_label = max(cluster_sizes, key=cluster_sizes.__getitem__)
        n_small_clusters = n_clusters - 1   # every other cluster is "small"

        main_mask = labels == main_label
        n_kept = int(main_mask.sum())

        span.set_attributes({
            "filter.main_label": main_label,
            "filter.main_cluster_size": n_kept,
            "filter.small_clusters_removed": n_small_clusters,
        })

        if n_kept < 2:
            raise ValueError(
                f"Main cluster has only {n_kept} vertices. "
                f"Try increasing eps_meters or reducing min_samples."
            )

        # ------------------------------------------------------------------
        # 5. Order main-cluster vertices along the route.
        #
        # Strategy: greedy nearest-neighbour chain.
        #   1. Use PCA to identify one terminus (extreme of PC1).
        #   2. Walk greedily: always step to the nearest unvisited point.
        #
        # This handles curves and L-shaped turns correctly.  PCA alone
        # fails at turns because it projects both arms onto a single axis,
        # mixing their ordering.
        # ------------------------------------------------------------------
        main_pts = pts_arr[main_mask]   # shape (K, 2) — (lat, lon)
        n_main = len(main_pts)

        # PCA — used only to pick the starting terminus
        centroid = main_pts.mean(axis=0)
        centred = main_pts - centroid
        _, _, Vt = np.linalg.svd(centred, full_matrices=False)
        pc1 = Vt[0]
        projections = centred @ pc1
        start_idx = int(np.argmin(projections))   # one extreme end of the route

        # Greedy NN chain from the starting terminus
        main_pts_rad = np.radians(main_pts)       # precompute for haversine
        visited = np.zeros(n_main, dtype=bool)
        chain = np.empty(n_main, dtype=int)
        chain[0] = start_idx
        visited[start_idx] = True

        for step in range(1, n_main):
            prev = chain[step - 1]
            prev_rad = main_pts_rad[prev]
            dlat = main_pts_rad[:, 0] - prev_rad[0]
            dlon = main_pts_rad[:, 1] - prev_rad[1]
            a = (
                np.sin(dlat / 2) ** 2
                + np.cos(prev_rad[0]) * np.cos(main_pts_rad[:, 0]) * np.sin(dlon / 2) ** 2
            )
            dists = 2 * _EARTH_RADIUS_M * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))
            dists[visited] = np.inf
            nearest = int(np.argmin(dists))
            chain[step] = nearest
            visited[nearest] = True

        ordered_pts = main_pts[chain]              # shape (K, 2) — (lat, lon)

        # ------------------------------------------------------------------
        # 6. Spatially thin: keep one vertex per thin_meters
        # ------------------------------------------------------------------
        waypoints: list[tuple[float, float]] = []
        for lat, lon in ordered_pts:
            if not waypoints:
                waypoints.append((lat, lon))
                continue
            prev_lat, prev_lon = waypoints[-1]
            if _haversine_m(prev_lat, prev_lon, lat, lon) >= _thin_meters:
                waypoints.append((lat, lon))

        # Always include the last ordered vertex so the route reaches the end
        last_lat, last_lon = float(ordered_pts[-1, 0]), float(ordered_pts[-1, 1])
        if waypoints[-1] != (last_lat, last_lon):
            waypoints.append((last_lat, last_lon))

        if len(waypoints) < 2:
            raise ValueError("Not enough distinct waypoints to form a route.")

        span.set_attributes({
            "route.waypoints": len(waypoints),
            "route.thin_meters": _thin_meters,
        })

        # ------------------------------------------------------------------
        # 7. Supersede previous estimations
        # ------------------------------------------------------------------
        previous = db.execute(
            select(RouteEstimation)
            .where(
                RouteEstimation.line_id == line_id,
                RouteEstimation.status != EstimationStatus.SUPERSEDED,
            )
        ).scalars().all()

        next_version = 1
        for prev in previous:
            if prev.version >= next_version:
                next_version = prev.version + 1
            prev.status = EstimationStatus.SUPERSEDED
            db.add(prev)

        # ------------------------------------------------------------------
        # 8. Persist RouteEstimation + RouteSegments
        # ------------------------------------------------------------------
        estimation = RouteEstimation(
            line_id=line_id,
            version=next_version,
            status=EstimationStatus.PENDING,
            trip_count=n_trips,
        )
        db.add(estimation)
        db.flush()

        n_route_segments = 0
        for seq, (wp_a, wp_b) in enumerate(zip(waypoints[:-1], waypoints[1:])):
            path = from_shape(
                LineString([
                    (wp_a[1], wp_a[0]),   # (lon, lat)
                    (wp_b[1], wp_b[0]),
                ]),
                srid=4326,
            )
            db.add(RouteSegment(
                estimation_id=estimation.id,
                sequence=seq,
                path=path,
                confidence=n_kept / n_total,
            ))
            n_route_segments += 1

        db.commit()

        span.set_attributes({
            "estimation.id": str(estimation.id),
            "estimation.version": next_version,
            "segments.saved": n_route_segments,
        })

        # ------------------------------------------------------------------
        # Build ClusterSegment list for visualisation
        # ------------------------------------------------------------------
        cluster_segments: list[ClusterSegment] = []
        for trip_idx in range(n_trips):
            sl_start, sl_end = trip_vertex_slices[trip_idx]
            for i in range(sl_start, sl_end - 1):
                j = i + 1
                both_kept = bool(main_mask[i]) and bool(main_mask[j])
                cluster_segments.append(ClusterSegment(
                    start_lat=points[i][0],
                    start_lon=points[i][1],
                    end_lat=points[j][0],
                    end_lon=points[j][1],
                    cluster_label=int(labels[i]) if both_kept else -1,
                    kept=both_kept,
                ))

        return FilteredRouteResult(
            estimation=estimation,
            n_trips=n_trips,
            n_segments_total=n_total,
            n_noise_segments=n_noise,
            n_clusters=n_clusters,
            n_small_clusters=n_small_clusters,
            n_kept_segments=n_kept,
            n_route_segments=n_route_segments,
            cluster_segments=cluster_segments,
        )
