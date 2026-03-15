"""Resample cleaned Trip points to uniform distance intervals (pipeline step 4).

Only trips whose ``match_score`` meets the minimum threshold are resampled.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID

from geoalchemy2.shape import from_shape
from shapely.geometry import Point
from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import Line, ResampledTrip, ResampledTripPoint, Trip, TripPoint

from .geo_math import haversine_m
from .telemetry import tracer


# ---------------------------------------------------------------------------
# Pure resampling logic
# ---------------------------------------------------------------------------


@dataclass
class ResampledPoint:
    timestamp: datetime
    latitude: float
    longitude: float


def resample_points(
    points: list[TripPoint],
    interval_meters: float,
    simplify_tolerance_m: float = 0.0,
) -> list[ResampledPoint]:
    """Resample a list of TripPoints to uniform distance intervals.

    A uniform grid is built from 0 to the total arc-length of the path, with
    steps of ``interval_meters``.  Latitude, longitude, and timestamp are all
    linearly interpolated between the two surrounding original points.

    Parameters
    ----------
    points : list[TripPoint]
        Cleaned trip points sorted by timestamp.
    interval_meters : float
        Desired spacing between output points in metres (e.g. 10, 20).
    simplify_tolerance_m : float
        Douglas-Peucker simplification tolerance in metres applied before
        resampling.  Jogs shorter than this value are removed.  Default 0
        (no simplification).

    Returns
    -------
    list[ResampledPoint]
        Uniformly-spaced points from the start to the end of the path.
    """
    if len(points) < 2:
        return [
            ResampledPoint(
                timestamp=points[0].timestamp,
                latitude=points[0].latitude,
                longitude=points[0].longitude,
            )
        ] if points else []

    sorted_pts = sorted(points, key=lambda p: p.timestamp)

    # Optional: remove small jogs before resampling (Douglas-Peucker).
    # Shapely simplify keeps the original vertices, so we can match back by
    # coordinate to preserve timestamps.
    if simplify_tolerance_m > 0 and len(sorted_pts) >= 3:
        from shapely.geometry import LineString as _LS
        _tolerance_deg = simplify_tolerance_m / 111_320.0
        _simplified = _LS(
            [(p.longitude, p.latitude) for p in sorted_pts]
        ).simplify(_tolerance_deg, preserve_topology=False)
        _kept = set(map(tuple, _simplified.coords))
        _filtered = [p for p in sorted_pts if (p.longitude, p.latitude) in _kept]
        if len(_filtered) >= 2:
            sorted_pts = _filtered

    # Cumulative arc-length at each original point
    cum: list[float] = [0.0]
    for i in range(1, len(sorted_pts)):
        prev, cur = sorted_pts[i - 1], sorted_pts[i]
        cum.append(cum[-1] + haversine_m(prev.longitude, prev.latitude, cur.longitude, cur.latitude))

    total = cum[-1]
    if total <= 0:
        return []

    # Build uniform distance grid, then merge backbone positions in so that
    # every simplified/structural point appears exactly in the output.
    grid: list[float] = []
    d = 0.0
    while d <= total + 1e-6:
        grid.append(d)
        d += interval_meters

    # Merge + sort, then remove positions closer than 0.5 m to their predecessor
    # (handles floating-point near-duplicates and grid/backbone collisions).
    _merged = sorted(set(grid + cum))
    grid = [_merged[0]]
    for _pos in _merged[1:]:
        if _pos - grid[-1] > 0.5:
            grid.append(_pos)

    orig_ts = [p.timestamp.timestamp() for p in sorted_pts]
    orig_lat = [p.latitude for p in sorted_pts]
    orig_lon = [p.longitude for p in sorted_pts]

    result: list[ResampledPoint] = []
    j = 0  # cursor into cum[] — avoids O(n²)

    for target_d in grid:
        while j < len(cum) - 2 and cum[j + 1] < target_d:
            j += 1

        d0, d1 = cum[j], cum[j + 1]
        span = d1 - d0
        frac = (target_d - d0) / span if span > 1e-9 else 0.0
        frac = max(0.0, min(1.0, frac))

        lat = orig_lat[j] + frac * (orig_lat[j + 1] - orig_lat[j])
        lon = orig_lon[j] + frac * (orig_lon[j + 1] - orig_lon[j])
        ts = orig_ts[j] + frac * (orig_ts[j + 1] - orig_ts[j])

        result.append(
            ResampledPoint(
                timestamp=datetime.fromtimestamp(ts, tz=timezone.utc),
                latitude=lat,
                longitude=lon,
            )
        )

    return result


# ---------------------------------------------------------------------------
# Single-trip entry point
# ---------------------------------------------------------------------------


@dataclass
class ResampleResult:
    resampled_trip: ResampledTrip
    point_count: int
    interval_meters: float
    was_existing: bool = False


def resample_trip(
    db: Session,
    trip_id: UUID,
    interval_meters: float,
    simplify_tolerance_m: float | None = None,
) -> ResampleResult:
    """Resample a single Trip to uniform distance intervals and persist the result.

    If a ``ResampledTrip`` for this trip at the same interval already exists,
    it is returned as-is without re-running the resampling.

    Parameters
    ----------
    db : Session
        SQLAlchemy session.
    trip_id : UUID
        ID of the cleaned Trip to resample.
    interval_meters : float
        Distance between output points in metres (e.g. 10, 20).
    simplify_tolerance_m : float | None
        Douglas-Peucker tolerance before resampling.  Defaults to half the
        interval, which removes jogs smaller than the sampling resolution.

    Returns
    -------
    ResampleResult
        The persisted ``ResampledTrip`` and summary statistics.
    """
    with tracer.start_as_current_span(
        "resample_trip",
        attributes={"trip_id": str(trip_id), "interval_meters": interval_meters},
    ) as span:
        existing = db.execute(
            select(ResampledTrip).where(
                ResampledTrip.trip_id == trip_id,
                ResampledTrip.interval_meters == interval_meters,
            )
        ).scalars().first()
        if existing:
            span.set_attribute("was_existing", True)
            return ResampleResult(
                resampled_trip=existing,
                point_count=existing.point_count,
                interval_meters=interval_meters,
                was_existing=True,
            )

        trip = db.get(Trip, trip_id)
        if not trip:
            raise ValueError(f"Trip {trip_id} not found")

        raw_points = (
            db.execute(
                select(TripPoint)
                .where(TripPoint.trip_id == trip_id)
                .order_by(TripPoint.timestamp)
            )
            .scalars()
            .all()
        )

        if len(raw_points) < 2:
            raise ValueError(f"Trip {trip_id} has fewer than 2 points — cannot resample")

        tolerance = simplify_tolerance_m if simplify_tolerance_m is not None else interval_meters * 0.5
        resampled = resample_points(raw_points, interval_meters, simplify_tolerance_m=tolerance)

        rt = ResampledTrip(
            trip_id=trip_id,
            interval_meters=interval_meters,
            match_score=trip.match_score or 0.0,
            point_count=len(resampled),
        )
        db.add(rt)
        db.flush()

        for i, rp in enumerate(resampled):
            db.add(
                ResampledTripPoint(
                    resampled_trip_id=rt.id,
                    point_index=i,
                    timestamp=rp.timestamp,
                    latitude=rp.latitude,
                    longitude=rp.longitude,
                    point=from_shape(Point(rp.longitude, rp.latitude), srid=4326),
                )
            )

        db.commit()

        span.set_attributes({
            "points.input": len(raw_points),
            "points.output": len(resampled),
            "resampled_trip.id": str(rt.id),
        })

        return ResampleResult(
            resampled_trip=rt,
            point_count=len(resampled),
            interval_meters=interval_meters,
        )


# ---------------------------------------------------------------------------
# Batch entry point
# ---------------------------------------------------------------------------


@dataclass
class BatchResampleResult:
    resampled: list[ResampleResult] = field(default_factory=list)
    skipped: list[UUID] = field(default_factory=list)   # below min_match_score
    failed: list[tuple[UUID, str]] = field(default_factory=list)


def resample_line(
    db: Session,
    line_id: UUID,
    interval_meters: float,
    min_match_score: float = 0.0,
    simplify_tolerance_m: float | None = None,
) -> BatchResampleResult:
    """Resample all eligible Trips for a line.

    Only trips with ``match_score >= min_match_score`` are resampled.
    Trips that fail are recorded in ``result.failed`` and do not interrupt
    the rest of the batch.

    Parameters
    ----------
    db : Session
        SQLAlchemy session.
    line_id : UUID
        ID of the Line whose trips to resample.
    interval_meters : float
        Distance between output points in metres.
    min_match_score : float
        Minimum match score threshold (0.0–1.0). Trips below this are skipped.

    Returns
    -------
    BatchResampleResult
        Summary with resampled, skipped, and failed trip IDs.
    """
    with tracer.start_as_current_span(
        "resample_line",
        attributes={
            "line_id": str(line_id),
            "interval_meters": interval_meters,
            "min_match_score": min_match_score,
        },
    ) as span:
        line = db.get(Line, line_id)
        if not line:
            raise ValueError(f"Line {line_id} not found")

        trips = (
            db.execute(
                select(Trip)
                .where(Trip.line_id == line_id)
                .order_by(Trip.processed_at)
            )
            .scalars()
            .all()
        )

        result = BatchResampleResult()

        for trip in trips:
            score = trip.match_score or 0.0
            if score < min_match_score:
                result.skipped.append(trip.id)
                continue

            try:
                result.resampled.append(resample_trip(db, trip.id, interval_meters, simplify_tolerance_m))
            except (ValueError, RuntimeError) as e:
                result.failed.append((trip.id, str(e)))

        span.set_attributes({
            "trips.total": len(trips),
            "trips.resampled": len(result.resampled),
            "trips.skipped": len(result.skipped),
            "trips.failed": len(result.failed),
        })

        return result
