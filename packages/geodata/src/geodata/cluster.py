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
from uuid import UUID

import numpy as np
from geoalchemy2.shape import from_shape
from shapely.geometry import LineString
from sklearn.cluster import DBSCAN
from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import (
    EstimationStatus,
    Line,
    ResampledTrip,
    ResampledTripPoint,
    RouteEstimation,
    RouteSegment,
    Trip,
)

from .telemetry import tracer


_EARTH_RADIUS_M = 6_371_000.0


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass
class ClusterRouteResult:
    estimation: RouteEstimation
    n_trips: int          # trips included in clustering
    n_points_total: int   # pooled points fed to DBSCAN
    n_noise_points: int   # points labelled noise (-1)
    n_clusters: int       # DBSCAN clusters found
    n_segments: int       # RouteSegments saved


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

        arr = np.array(rows)          # shape (N, 4)
        coords = arr[:, :2]           # (lat, lon) in degrees
        point_indices = arr[:, 2]     # point_index per point
        trip_idx_col = arr[:, 3]      # which trip each point came from

        # ------------------------------------------------------------------
        # 3. Run DBSCAN with haversine distance (input must be in radians)
        # ------------------------------------------------------------------
        effective_min_samples = min_samples if min_samples is not None else max(2, n_trips // 3)
        eps_rad = eps_meters / _EARTH_RADIUS_M

        span.set_attributes({
            "dbscan.eps_meters": eps_meters,
            "dbscan.min_samples": effective_min_samples,
            "dbscan.n_points": len(rows),
        })

        labels = DBSCAN(
            eps=eps_rad,
            min_samples=effective_min_samples,
            algorithm="ball_tree",
            metric="haversine",
        ).fit_predict(np.radians(coords))

        n_noise = int(np.sum(labels == -1))
        unique_labels = sorted(lbl for lbl in set(labels) if lbl != -1)
        n_clusters = len(unique_labels)

        span.set_attributes({
            "dbscan.n_clusters": n_clusters,
            "dbscan.n_noise": n_noise,
        })

        if n_clusters < 2:
            raise ValueError(
                f"DBSCAN produced {n_clusters} cluster(s) — need at least 2 to "
                f"form a route.  Try increasing eps_meters or reducing min_samples."
            )

        # ------------------------------------------------------------------
        # 4. Compute per-cluster statistics
        # ------------------------------------------------------------------
        cluster_stats: list[dict] = []
        for lbl in unique_labels:
            mask = labels == lbl
            cluster_coords = coords[mask]          # (k, 2) lat/lon
            cluster_pidx = point_indices[mask]     # point_index values
            cluster_trips = trip_idx_col[mask]     # trip indices

            centroid_lat = float(np.mean(cluster_coords[:, 0]))
            centroid_lon = float(np.mean(cluster_coords[:, 1]))
            mean_pidx = float(np.mean(cluster_pidx))
            distinct_trips = len(np.unique(cluster_trips))

            cluster_stats.append({
                "label": lbl,
                "centroid_lat": centroid_lat,
                "centroid_lon": centroid_lon,
                "mean_point_index": mean_pidx,
                "distinct_trips": distinct_trips,
            })

        # ------------------------------------------------------------------
        # 5. Order clusters along the route by mean point_index
        # ------------------------------------------------------------------
        cluster_stats.sort(key=lambda c: c["mean_point_index"])

        # ------------------------------------------------------------------
        # 6. Supersede any previous estimations for this line
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

        n_segments = 0
        for seq, (cs_a, cs_b) in enumerate(
            zip(cluster_stats[:-1], cluster_stats[1:])
        ):
            confidence = min(cs_a["distinct_trips"], cs_b["distinct_trips"]) / n_trips
            path = from_shape(
                LineString([
                    (cs_a["centroid_lon"], cs_a["centroid_lat"]),
                    (cs_b["centroid_lon"], cs_b["centroid_lat"]),
                ]),
                srid=4326,
            )
            db.add(RouteSegment(
                estimation_id=estimation.id,
                sequence=seq,
                path=path,
                confidence=confidence,
            ))
            n_segments += 1

        db.commit()

        span.set_attributes({
            "estimation.id": str(estimation.id),
            "estimation.version": next_version,
            "segments.saved": n_segments,
        })

        return ClusterRouteResult(
            estimation=estimation,
            n_trips=n_trips,
            n_points_total=len(rows),
            n_noise_points=n_noise,
            n_clusters=n_clusters,
            n_segments=n_segments,
        )
