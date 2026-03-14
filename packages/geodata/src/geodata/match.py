"""Map-match raw GPS traces to the OSM road network via Valhalla (Meili HMM)."""

import os
from dataclasses import dataclass
from uuid import UUID

import httpx
from geoalchemy2.shape import from_shape
from opentelemetry import trace

from .telemetry import tracer
from shapely.geometry import LineString, Point
from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import (
    Line,
    ProcessingStatus,
    SessionStatus,
    Trip,
    TripPoint,
    TripSession,
    TripSessionPoint,
    TripStatus,
)

VALHALLA_URL = os.environ.get("VALHALLA_URL", "http://localhost:8002")


@dataclass
class MatchResult:
    """Result of map-matching a trip session."""

    trip: Trip
    points_before: int
    points_after: int
    confidence: float


def _decode_polyline6(encoded: str) -> list[tuple[float, float]]:
    """Decode a Valhalla polyline6-encoded string into (lat, lon) pairs."""
    coords: list[tuple[float, float]] = []
    index = 0
    lat = 0
    lng = 0

    while index < len(encoded):
        for is_lng in (False, True):
            shift = 0
            result = 0
            while True:
                byte = ord(encoded[index]) - 63
                index += 1
                result |= (byte & 0x1F) << shift
                shift += 5
                if byte < 0x20:
                    break
            delta = ~(result >> 1) if (result & 1) else (result >> 1)
            if is_lng:
                lng += delta
            else:
                lat += delta

        coords.append((lat / 1e6, lng / 1e6))

    return coords


def _interpolate_timestamps(
    original_points: list[TripSessionPoint],
    matched_coords: list[tuple[float, float]],
) -> list[float]:
    """Assign timestamps to matched points by interpolating from originals.

    For each matched point, find the nearest original point (by index proportion
    along the path) and linearly interpolate its timestamp.
    """
    if not original_points or not matched_coords:
        return []

    orig_ts = [p.timestamp.timestamp() for p in original_points]
    n_orig = len(orig_ts)
    n_matched = len(matched_coords)

    timestamps: list[float] = []
    for i in range(n_matched):
        frac = i / max(n_matched - 1, 1)
        pos = frac * (n_orig - 1)
        lo = int(pos)
        hi = min(lo + 1, n_orig - 1)
        t = pos - lo
        ts = orig_ts[lo] + t * (orig_ts[hi] - orig_ts[lo])
        timestamps.append(ts)

    return timestamps


def trace_match(
    points: list[dict],
    *,
    costing: str = "auto",
    search_radius: int = 50,
    gps_accuracy: int = 20,
) -> list[tuple[float, float]]:
    """Send raw GPS points to Valhalla trace_route and return matched (lat, lon) pairs.

    Parameters
    ----------
    points : list of dict
        Each dict must have "lat" and "lon" keys, and optionally "time" (unix epoch).
    costing : str
        Valhalla costing model ("auto", "bus", "pedestrian", etc.)
    search_radius : int
        Search radius in meters for candidate matching.
    gps_accuracy : int
        Expected GPS accuracy in meters.

    Returns
    -------
    list of (lat, lon) tuples — the snapped path on the road network.
    """
    shape = []
    for p in points:
        entry: dict = {"lat": p["lat"], "lon": p["lon"]}
        if "time" in p:
            entry["time"] = p["time"]
        shape.append(entry)

    body = {
        "shape": shape,
        "costing": costing,
        "shape_match": "map_snap",
        "trace_options": {
            "search_radius": search_radius,
            "gps_accuracy": gps_accuracy,
        },
    }

    with tracer.start_as_current_span(
        "valhalla.trace_route",
        attributes={"valhalla.costing": costing, "valhalla.num_points": len(shape)},
    ):
        resp = httpx.post(f"{VALHALLA_URL}/trace_route", json=body, timeout=30.0)
        resp.raise_for_status()
        data = resp.json()

    encoded_shape = data["trip"]["legs"][0]["shape"]
    return _decode_polyline6(encoded_shape)


def match_session(
    db: Session,
    session_id: UUID,
    *,
    costing: str = "auto",
    search_radius: int = 50,
    gps_accuracy: int = 20,
) -> MatchResult:
    """Map-match a TripSession and save the result as a Trip + TripPoints.

    Steps:
    1. Load raw TripSessionPoints
    2. Send to Valhalla trace_route (HMM map-matching)
    3. Create Trip with matched geometry
    4. Create TripPoints with interpolated timestamps
    5. Update TripSession.processing_status
    """
    with tracer.start_as_current_span(
        "match_session",
        attributes={"session_id": str(session_id)},
    ) as span:
        session = db.get(TripSession, session_id)
        if not session:
            raise ValueError(f"TripSession {session_id} not found")

        if not session.line_id:
            raise ValueError(f"TripSession {session_id} has no line_id assigned")

        raw_points = (
            db.execute(
                select(TripSessionPoint)
                .where(TripSessionPoint.session_id == session_id)
                .order_by(TripSessionPoint.timestamp)
            )
            .scalars()
            .all()
        )

        if len(raw_points) < 2:
            raise ValueError(f"TripSession {session_id} has fewer than 2 points")

        span.set_attribute("points.raw", len(raw_points))
        session.processing_status = ProcessingStatus.PROCESSING
        db.flush()

        shape = [{"lat": p.latitude, "lon": p.longitude} for p in raw_points]

        try:
            matched_coords = trace_match(
                shape,
                costing=costing,
                search_radius=search_radius,
                gps_accuracy=gps_accuracy,
            )
        except httpx.HTTPStatusError as e:
            session.processing_status = ProcessingStatus.FAILED
            db.flush()
            span.set_status(trace.StatusCode.ERROR, str(e))
            span.record_exception(e)
            raise RuntimeError(
                f"Valhalla map-matching failed: {e.response.status_code} — {e.response.text}"
            ) from e

        timestamps = _interpolate_timestamps(raw_points, matched_coords)

        # Build the matched path geometry
        line_coords = [(lon, lat) for lat, lon in matched_coords]
        matched_path = from_shape(LineString(line_coords), srid=4326) if len(line_coords) >= 2 else None

        # Compute a simple confidence: ratio of matched points to original
        confidence = len(matched_coords) / len(raw_points) if raw_points else 0.0

        trip = Trip(
            session_id=session_id,
            line_id=session.line_id,
            status=TripStatus.CLEAN,
            match_score=min(confidence, 1.0),
            computed_path=matched_path,
        )
        db.add(trip)
        db.flush()

        from datetime import datetime, timezone

        for i, (lat, lon) in enumerate(matched_coords):
            tp = TripPoint(
                trip_id=trip.id,
                point_index=i,
                timestamp=datetime.fromtimestamp(timestamps[i], tz=timezone.utc),
                latitude=lat,
                longitude=lon,
                point=from_shape(Point(lon, lat), srid=4326),
            )
            db.add(tp)

        session.processing_status = ProcessingStatus.PROCESSED
        db.commit()

        span.set_attributes({
            "points.matched": len(matched_coords),
            "match.confidence": min(confidence, 1.0),
            "trip.id": str(trip.id),
        })

        return MatchResult(
            trip=trip,
            points_before=len(raw_points),
            points_after=len(matched_coords),
            confidence=min(confidence, 1.0),
        )


# ---------------------------------------------------------------------------
# Batch map-matching
# ---------------------------------------------------------------------------

@dataclass
class BatchMatchResult:
    """Summary of a batch map-matching run."""

    matched: list[MatchResult]
    failed: list[tuple[UUID, str]]
    skipped: int


def match_line(
    db: Session,
    line_id: UUID,
    *,
    costing: str = "auto",
    search_radius: int = 50,
    gps_accuracy: int = 20,
) -> BatchMatchResult:
    """Map-match all RAW trip sessions for a given line.

    Fetches all TripSessions with processing_status=RAW and status=COMPLETED
    for the given line, and runs match_session on each.
    Sessions that fail are marked FAILED and collected in the result.
    """
    with tracer.start_as_current_span(
        "match_line",
        attributes={"line_id": str(line_id)},
    ) as span:
        line = db.get(Line, line_id)
        if not line:
            raise ValueError(f"Line {line_id} not found")

        sessions = (
            db.execute(
                select(TripSession)
                .where(
                    TripSession.line_id == line_id,
                    TripSession.processing_status == ProcessingStatus.RAW,
                    TripSession.status == SessionStatus.COMPLETED,
                )
                .order_by(TripSession.started_at)
            )
            .scalars()
            .all()
        )

        span.set_attribute("sessions.total", len(sessions))

        if not sessions:
            return BatchMatchResult(matched=[], failed=[], skipped=0)

        matched: list[MatchResult] = []
        failed: list[tuple[UUID, str]] = []
        skipped = 0

        for session in sessions:
            try:
                result = match_session(
                    db,
                    session.id,
                    costing=costing,
                    search_radius=search_radius,
                    gps_accuracy=gps_accuracy,
                )
                matched.append(result)
            except (ValueError, RuntimeError) as e:
                failed.append((session.id, str(e)))
            except Exception as e:
                failed.append((session.id, str(e)))

        span.set_attributes({
            "sessions.matched": len(matched),
            "sessions.failed": len(failed),
        })

        return BatchMatchResult(matched=matched, failed=failed, skipped=skipped)
