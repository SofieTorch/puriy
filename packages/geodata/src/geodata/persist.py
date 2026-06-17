"""Save generated tracks to the database."""

from datetime import datetime
from uuid import UUID

from geoalchemy2.shape import from_shape
from shapely.geometry import LineString, Point
from sqlalchemy.orm import Session

from database.devices import ensure_device
from database.models import SessionStatus, TripSession, TripSessionPoint

from .telemetry import tracer


def save_tracks_to_db(
    db: Session,
    tracks: list[dict],
    line_id: UUID,
    device_id: str | None = None,
    notes: str | None = None,
) -> list[TripSession]:
    """Persist generated track records as TripSessions + TripSessionPoints.

    Parameters
    ----------
    db : sqlalchemy Session
    tracks : list of dict
        Output from ``generate_tracks`` — each dict has track_id,
        point_index, timestamp, longitude, latitude.
    line_id : UUID
        The Line ID to associate with each TripSession.
    notes : str, optional
        Notes to attach to each session (e.g. "simulated").

    Returns
    -------
    list of TripSession
        The created sessions (already committed).
    """
    with tracer.start_as_current_span(
        "save_tracks_to_db",
        attributes={"line_id": str(line_id), "tracks.total_points": len(tracks)},
    ) as span:
        grouped: dict[int, list[dict]] = {}
        for rec in tracks:
            grouped.setdefault(rec["track_id"], []).append(rec)

        sessions: list[TripSession] = []
        for track_id in sorted(grouped):
            points = sorted(grouped[track_id], key=lambda r: r["point_index"])

            timestamps = [datetime.fromisoformat(p["timestamp"]) for p in points]
            coords = [(p["longitude"], p["latitude"]) for p in points]

            # trip_sessions.device_id is FK-constrained to devices.id; register the
            # synthetic device before flushing so callers don't have to.
            session_device_id = device_id or f"simulator-{track_id}"
            ensure_device(db, session_device_id)

            session = TripSession(
                line_id=line_id,
                device_id=session_device_id,
                status=SessionStatus.COMPLETED,
                started_at=timestamps[0],
                ended_at=timestamps[-1],
                last_activity_at=timestamps[-1],
                notes=notes or "simulated",
                device_model="simulator",
                computed_path=from_shape(LineString(coords), srid=4326)
                if len(coords) >= 2
                else None,
            )
            db.add(session)
            db.flush()  # get session.id

            for p in points:
                ts = datetime.fromisoformat(p["timestamp"])
                loc = TripSessionPoint(
                    session_id=session.id,
                    timestamp=ts,
                    latitude=p["latitude"],
                    longitude=p["longitude"],
                    point=from_shape(
                        Point(p["longitude"], p["latitude"]), srid=4326
                    ),
                )
                db.add(loc)

            sessions.append(session)

        db.commit()

        span.set_attribute("sessions.created", len(sessions))

        return sessions
