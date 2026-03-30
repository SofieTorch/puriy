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


@dataclass
class _TraceOutput:
    shape_coords: list[tuple[float, float]]   # dense road geometry (lat, lon)
    matched_points: list[dict]                # one entry per input GPS point
    match_score: float                        # fraction of non-unmatched points (0–1)
    mean_snap_distance: float                 # mean GPS-to-road distance in metres


def trace_match(
    points: list[dict],
    *,
    costing: str = "bus",
    search_radius: int = 60,
    gps_accuracy: int = 20,
) -> _TraceOutput:
    """Send raw GPS points to Valhalla trace_attributes and return match results.

    Parameters
    ----------
    points : list of dict
        Each dict must have "lat" and "lon" keys, and optionally "time" (unix epoch).
    costing : str
        Valhalla costing model ("bus", "auto", "pedestrian", etc.)
    search_radius : int
        Search radius in meters for candidate road matching.
    gps_accuracy : int
        Expected GPS accuracy in meters.

    Returns
    -------
    _TraceOutput
        Dense matched path, per-point match data, and quality metrics.
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
        "valhalla.trace_attributes",
        attributes={"valhalla.costing": costing, "valhalla.num_points": len(shape)},
    ) as span:
        resp = httpx.post(f"{VALHALLA_URL}/trace_attributes", json=body, timeout=30.0)
        resp.raise_for_status()
        data = resp.json()

    shape_coords = _decode_polyline6(data["shape"])
    matched_points: list[dict] = data.get("matched_points", [])

    if matched_points:
        strictly_matched = [p for p in matched_points if p.get("type") == "matched"]
        match_score = len(strictly_matched) / len(matched_points)
        snap_distances = [p.get("distance_from_trace_point", 0.0) for p in strictly_matched]
        mean_snap = sum(snap_distances) / len(snap_distances) if snap_distances else 0.0
    else:
        match_score = 1.0
        mean_snap = 0.0

    span.set_attributes({
        "match.score": match_score,
        "match.mean_snap_distance": mean_snap,
        "match.shape_points": len(shape_coords),
    })

    return _TraceOutput(
        shape_coords=shape_coords,
        matched_points=matched_points,
        match_score=match_score,
        mean_snap_distance=mean_snap,
    )


def match_session(
    db: Session,
    session_id: UUID,
    *,
    costing: str = "bus",
    search_radius: int = 60,
    gps_accuracy: int = 20,
) -> MatchResult:
    """Map-match a TripSession and save the result as a Trip + TripPoints.

    Steps:
    1. Load raw TripSessionPoints
    2. Send to Valhalla trace_attributes (HMM map-matching)
    3. Create Trip with matched geometry, match_score, and mean snap distance
    4. Create TripPoints from matched GPS positions with exact timestamps
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

        shape = []
        for p in raw_points:
            entry: dict = {
                "lat": p.latitude,
                "lon": p.longitude,
                "time": int(p.timestamp.timestamp()),
            }
            if p.horizontal_accuracy is not None:
                entry["accuracy"] = p.horizontal_accuracy
            shape.append(entry)

        try:
            result = trace_match(
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

        # Build the matched path geometry from the snapped point positions,
        # not the routing shape — the routing shape can take detours via
        # turn restrictions between consecutive edges.
        valid_matched = [mp for mp in result.matched_points if mp.get("type") != "unmatched"]
        line_coords = [(mp["lon"], mp["lat"]) for mp in valid_matched]
        matched_path = from_shape(LineString(line_coords), srid=4326) if len(line_coords) >= 2 else None

        trip = Trip(
            session_id=session_id,
            line_id=session.line_id,
            status=TripStatus.CLEAN,
            match_score=result.match_score,
            frechet_distance=result.mean_snap_distance,
            computed_path=matched_path,
        )
        db.add(trip)
        db.flush()

        # TripPoints: one per GPS input, snapped to road, with exact timestamp
        points_saved = 0
        for i, mp in enumerate(result.matched_points):
            if mp.get("type") == "unmatched":
                continue
            tp = TripPoint(
                trip_id=trip.id,
                point_index=points_saved,
                timestamp=raw_points[i].timestamp,
                latitude=mp["lat"],
                longitude=mp["lon"],
                point=from_shape(Point(mp["lon"], mp["lat"]), srid=4326),
            )
            db.add(tp)
            points_saved += 1

        session.processing_status = ProcessingStatus.PROCESSED
        db.commit()

        span.set_attributes({
            "points.matched": points_saved,
            "match.score": result.match_score,
            "match.mean_snap_distance": result.mean_snap_distance,
            "trip.id": str(trip.id),
        })

        return MatchResult(
            trip=trip,
            points_before=len(raw_points),
            points_after=points_saved,
            confidence=result.match_score,
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
    costing: str = "bus",
    search_radius: int = 60,
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
