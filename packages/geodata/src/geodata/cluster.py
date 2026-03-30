"""DBSCAN-based route reconstruction from pooled clean trip segments.

Algorithm
---------
1. Decompose each Trip.computed_path into segments (consecutive vertex pairs).
2. Represent each segment by its midpoint.
3. Run DBSCAN with haversine distance on midpoints to cluster segments.
4. ``filter_cluster_route`` discards noise and small clusters, keeps the
   surviving segments per trip in their original order, and merges them
   across trips to produce the final route.

Typical usage
-------------
    result = filter_cluster_route(db, line_id, eps_meters=30.0)
    print(result.n_kept_segments, "segments kept →", result.n_route_segments, "route segments")
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

from .telemetry import tracer


_EARTH_RADIUS_M = 6_371_000.0


# ---------------------------------------------------------------------P------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class ClusterSegment:
    """A single trip segment with its DBSCAN assignment."""
    start_lat: float
    start_lon: float
    end_lat: float
    end_lon: float
    cluster_label: int   # -1 = noise
    kept: bool           # True if it survived filtering


@dataclass
class FilteredRouteResult:
    estimation: RouteEstimation
    n_trips: int
    n_segments_total: int     # total segments pooled across all trips
    n_noise_segments: int     # segments labelled noise (-1)
    n_clusters: int           # DBSCAN clusters found
    n_small_clusters: int     # clusters removed for being too small
    n_kept_segments: int      # segments that survived filtering
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
) -> FilteredRouteResult:
    """Cluster trip segments via DBSCAN, filter outliers, build route.

    Each trip's computed_path is decomposed into segments (consecutive vertex
    pairs).  Segments are clustered by midpoint proximity.  Noise and small
    clusters are discarded.  Surviving segments are kept per trip in order,
    then merged across trips by fractional-position interpolation + averaging.

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
        Clusters with fewer segments than this are discarded.
        Defaults to 0 (keep every non-noise cluster).

    Returns
    -------
    FilteredRouteResult
    """
    with tracer.start_as_current_span(
        "filter_cluster_route",
        attributes={
            "line_id": str(line_id),
            "eps_meters": eps_meters,
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
        # 2. Decompose each trip into segments, compute midpoints
        # ------------------------------------------------------------------
        # For each segment we store:
        #   midpoint (lat, lon) — used for DBSCAN
        #   start/end vertices  — used for visualization and route building
        #   trip index          — which trip it belongs to
        midpoints: list[tuple[float, float]] = []
        seg_starts: list[tuple[float, float]] = []   # (lat, lon)
        seg_ends: list[tuple[float, float]] = []     # (lat, lon)
        trip_indices: list[int] = []
        # Per-trip segment slices: (start_idx, end_idx) into the arrays above
        trip_slices: list[tuple[int, int]] = []

        for trip_idx, trip in enumerate(trips):
            geom = to_shape(trip.computed_path)
            coords_list = list(geom.coords)  # [(lon, lat, ...), ...]
            slice_start = len(midpoints)
            for i in range(len(coords_list) - 1):
                a_lon, a_lat = coords_list[i][0], coords_list[i][1]
                b_lon, b_lat = coords_list[i + 1][0], coords_list[i + 1][1]
                midpoints.append(((a_lat + b_lat) / 2, (a_lon + b_lon) / 2))
                seg_starts.append((a_lat, a_lon))
                seg_ends.append((b_lat, b_lon))
                trip_indices.append(trip_idx)
            trip_slices.append((slice_start, len(midpoints)))

        n_total = len(midpoints)
        if n_total < 2:
            raise ValueError(
                f"Not enough segments for line {line_id} after pooling "
                f"({n_total} segments total)"
            )

        mid_arr = np.array(midpoints)  # shape (N, 2) — (lat, lon)

        # ------------------------------------------------------------------
        # 3. Run DBSCAN on segment midpoints
        # ------------------------------------------------------------------
        effective_min_samples = min_samples if min_samples is not None else max(2, n_trips // 3)
        eps_rad = eps_meters / _EARTH_RADIUS_M

        labels = DBSCAN(
            eps=eps_rad,
            min_samples=effective_min_samples,
            algorithm="ball_tree",
            metric="haversine",
        ).fit_predict(np.radians(mid_arr))

        n_noise = int(np.sum(labels == -1))
        unique_labels = sorted(lbl for lbl in set(labels) if lbl != -1)
        n_clusters = len(unique_labels)

        span.set_attributes({
            "dbscan.n_clusters": n_clusters,
            "dbscan.n_noise": n_noise,
            "dbscan.n_segments": n_total,
        })

        # ------------------------------------------------------------------
        # 4. Filter out noise and small clusters
        # ------------------------------------------------------------------
        cluster_sizes = {lbl: int(np.sum(labels == lbl)) for lbl in unique_labels}
        valid_labels = {lbl for lbl, sz in cluster_sizes.items() if sz >= min_cluster_segments}
        n_small_clusters = n_clusters - len(valid_labels)

        keep_mask = np.array([lbl in valid_labels for lbl in labels])
        n_kept = int(keep_mask.sum())

        span.set_attributes({
            "filter.min_cluster_segments": min_cluster_segments,
            "filter.small_clusters_removed": n_small_clusters,
            "filter.kept_segments": n_kept,
        })

        if n_kept < 1:
            raise ValueError(
                f"No segments survived filtering. "
                f"Try increasing eps_meters, reducing min_samples, or lowering "
                f"min_cluster_segments."
            )

        # ------------------------------------------------------------------
        # 5. Build route: keep each trip's surviving segments in order,
        #    chain vertices, then merge across trips
        # ------------------------------------------------------------------
        filtered_trips: list[np.ndarray] = []
        for slice_start, slice_end in trip_slices:
            trip_keep = keep_mask[slice_start:slice_end]
            if trip_keep.sum() < 1:
                continue
            vertices: list[tuple[float, float]] = []
            for j in range(slice_start, slice_end):
                if keep_mask[j]:
                    if not vertices:
                        vertices.append(seg_starts[j])
                    vertices.append(seg_ends[j])
            if len(vertices) >= 2:
                filtered_trips.append(np.array(vertices))

        if not filtered_trips:
            raise ValueError("No trips with surviving segments after filtering.")

        # Merge across trips: resample each filtered trip at N equal
        # fractional positions, then average.
        n_waypoints = int(np.median([len(ft) for ft in filtered_trips]))
        n_waypoints = max(n_waypoints, 2)
        fractions = np.linspace(0.0, 1.0, n_waypoints)

        def _resample_at_fractions(pts: np.ndarray, fracs: np.ndarray) -> np.ndarray:
            n = len(pts)
            if n == 1:
                return np.tile(pts[0], (len(fracs), 1))
            idx_float = fracs * (n - 1)
            idx_low = np.clip(np.floor(idx_float).astype(int), 0, n - 2)
            t = idx_float - idx_low
            return pts[idx_low] * (1 - t)[:, None] + pts[idx_low + 1] * t[:, None]

        resampled = np.stack([
            _resample_at_fractions(ft, fractions) for ft in filtered_trips
        ])
        waypoints_arr = np.mean(resampled, axis=0)
        waypoints = [(float(wp[0]), float(wp[1])) for wp in waypoints_arr]

        # ------------------------------------------------------------------
        # 6. Supersede previous estimations
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
        # 7. Persist RouteEstimation + RouteSegments
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
                    (wp_a[1], wp_a[0]),  # (lon, lat)
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

        cluster_segments = [
            ClusterSegment(
                start_lat=seg_starts[i][0],
                start_lon=seg_starts[i][1],
                end_lat=seg_ends[i][0],
                end_lon=seg_ends[i][1],
                cluster_label=int(labels[i]),
                kept=bool(keep_mask[i]),
            )
            for i in range(n_total)
        ]

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
