from datetime import datetime, timedelta
from typing import Sequence
from uuid import UUID

from database.models.line import Line, LineStatus
from database.models.trip import (
    TripSessionPoint,
    TripSession,
    SessionStatus,
    TripSensorReading,
)
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from database.connection import get_db
from geodata.reduce import reduce_linestring_from_recording_session
from schemas.recording import (
    AssignDeviceRequest,
    EndSessionRequest,
    TripSessionPointBatch,
    TripSessionPointCreate,
    TripSessionPointRead,
    TripSessionCreate,
    TripSessionRead,
    TripSensorReadingBatch,
    TripSensorReadingCreate,
    TripSensorReadingRead,
)

router = APIRouter(prefix="/recordings", tags=["recordings"])


# ============================================================
# Trip Sessions
# ============================================================

@router.post("/", response_model=TripSessionRead, status_code=201)
def start_recording(
    session_data: TripSessionCreate,
    db: Session = Depends(get_db)
) -> TripSessionRead:
    """
    Start a new trip session.

    The line is not required at start; it will be assigned when the session ends.
    """
    session = TripSession(
        line_id=None,
        direction=session_data.direction,
        device_id=session_data.device_id,
        device_model=session_data.device_model,
        os_version=session_data.os_version,
        notes=session_data.notes,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return TripSessionRead.model_validate(session)


@router.get("/", response_model=list[TripSessionRead])
def list_recordings(
    line_id: UUID | None = None,
    status: SessionStatus | None = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
) -> Sequence[TripSessionRead]:
    """List trip sessions with optional filters."""
    query = select(TripSession)

    if line_id is not None:
        query = query.where(TripSession.line_id == line_id)
    if status is not None:
        query = query.where(TripSession.status == status)

    sessions = db.execute(
        query.order_by(TripSession.started_at.desc())
        .offset(skip).limit(limit)
    ).scalars().all()

    return [TripSessionRead.model_validate(s) for s in sessions]


@router.get("/{session_id}", response_model=TripSessionRead)
def get_recording(session_id: UUID, db: Session = Depends(get_db)) -> TripSessionRead:
    """Get a specific trip session."""
    session = db.get(TripSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Trip session not found")
    return TripSessionRead.model_validate(session)


@router.patch("/{session_id}/device", response_model=TripSessionRead)
def assign_device(
    session_id: UUID,
    body: AssignDeviceRequest,
    db: Session = Depends(get_db),
) -> TripSessionRead:
    """Assign a trip session to a device (testing utility)."""
    session = db.get(TripSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Trip session not found")

    session.device_id = body.device_id
    if body.device_model is not None:
        session.device_model = body.device_model
    if body.os_version is not None:
        session.os_version = body.os_version

    db.commit()
    db.refresh(session)
    return TripSessionRead.model_validate(session)


@router.post("/{session_id}/end", response_model=TripSessionRead)
def end_recording(
    session_id: UUID,
    body: EndSessionRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> TripSessionRead:
    """
    End a trip session.

    - If line_id is provided: assign to that line, status COMPLETED.
    - If line_id is null but line_name is provided: create a new line (PENDING) and assign, status COMPLETED.
    - If both are null: status DISCARDED.
    The computed path is always generated from the collected location points.
    """
    session = db.get(TripSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Trip session not found")

    if session.status != SessionStatus.IN_PROGRESS:
        raise HTTPException(
            status_code=400,
            detail=f"Session is not in progress (current status: {session.status})"
        )

    # Compute path from location points
    points = db.execute(
        select(TripSessionPoint)
        .where(TripSessionPoint.session_id == session_id)
        .order_by(TripSessionPoint.timestamp)
    ).scalars().all()

    if len(points) >= 2:
        coords = [(p.longitude, p.latitude) for p in points]
        linestring = f"SRID=4326;LINESTRING({', '.join(f'{lon} {lat}' for lon, lat in coords)})"
        session.computed_path = func.ST_GeomFromEWKT(linestring)

    line_name_trimmed = (body.line_name or "").strip()

    if body.line_id is not None:
        line = db.get(Line, body.line_id)
        if not line:
            raise HTTPException(status_code=404, detail="Line not found")
        if line.status == LineStatus.MERGED:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot assign merged line. Use line {line.merged_into_id} instead.",
            )
        session.line_id = body.line_id
        session.status = SessionStatus.COMPLETED
    elif line_name_trimmed:
        new_line = Line(
            name=line_name_trimmed,
            status=LineStatus.DRAFT,
        )
        db.add(new_line)
        db.flush()
        session.line_id = new_line.id
        session.status = SessionStatus.COMPLETED
    else:
        session.status = SessionStatus.DISCARDED

    session.ended_at = datetime.utcnow()

    new_detour_id: UUID | None = None
    if body.is_detour and session.line_id and session.computed_path is not None:
        from database.models.detour import Detour

        # Map-match the detour path via Valhalla for a clean road-snapped geometry
        snapped_path = session.computed_path
        try:
            from geodata.match import trace_match
            from geoalchemy2.shape import from_shape, to_shape
            from shapely.geometry import LineString as ShapelyLineString

            raw_shape = to_shape(session.computed_path)
            raw_points = [{"lat": c[1], "lon": c[0]} for c in raw_shape.coords]
            if len(raw_points) >= 2:
                result = trace_match(raw_points, costing="bus")
                matched_coords = [(lon, lat) for lat, lon in result.shape_coords]
                if len(matched_coords) >= 2:
                    snapped_path = from_shape(ShapelyLineString(matched_coords), srid=4326)
        except Exception:
            pass  # Fall back to raw path if Valhalla unavailable

        detour = Detour(
            line_id=session.line_id,
            session_id=session.id,
            reason=body.detour_reason,
            description=body.detour_description,
            path=snapped_path,
        )
        db.add(detour)
        new_detour_id = detour.id

    db.commit()
    db.refresh(session)

    # Notify commute subscribers in the background. The reporting device is
    # excluded so it doesn't get notified about its own detour.
    if new_detour_id is not None and session.line_id is not None:
        from services.push import dispatch_detour_notifications
        background_tasks.add_task(
            dispatch_detour_notifications,
            line_id=session.line_id,
            detour_id=new_detour_id,
            exclude_device_id=session.device_id,
        )

    # Per-trip event trigger for the pipeline (CU-11). Fires `clean_traces`
    # for the just-ended session's line so the new trip becomes visible as
    # a Trip[CLEAN] without waiting for the next cron tick. Heavier steps
    # (reconstruct, resolve, infer_schedules) stay on the cron schedule.
    if (
        session.line_id is not None
        and session.status == SessionStatus.COMPLETED
    ):
        from services.pipeline_trigger import run_clean_traces_for_line
        background_tasks.add_task(run_clean_traces_for_line, session.line_id)

    return TripSessionRead.model_validate(session)


@router.post("/{session_id}/cancel", response_model=TripSessionRead)
def cancel_recording(session_id: UUID, db: Session = Depends(get_db)) -> TripSessionRead:
    """Cancel an in-progress trip session."""
    session = db.get(TripSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Trip session not found")

    if session.status != SessionStatus.IN_PROGRESS:
        raise HTTPException(
            status_code=400,
            detail=f"Session is not in progress (current status: {session.status})"
        )

    session.status = SessionStatus.CANCELLED
    session.ended_at = datetime.utcnow()

    db.commit()
    db.refresh(session)
    return TripSessionRead.model_validate(session)


# ============================================================
# Location Points - Batch Upload
# ============================================================

@router.post("/{session_id}/locations", response_model=TripSessionPointRead, status_code=201)
def add_location_point(
    session_id: UUID,
    point_data: TripSessionPointCreate,
    db: Session = Depends(get_db)
) -> TripSessionPointRead:
    """Add a single location point to a trip session."""
    session = db.get(TripSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Trip session not found")

    if session.status != SessionStatus.IN_PROGRESS:
        raise HTTPException(status_code=400, detail="Session is not in progress")

    # Create PostGIS point
    point_wkt = f"SRID=4326;POINT({point_data.longitude} {point_data.latitude})"

    point = TripSessionPoint(
        session_id=session_id,
        **point_data.model_dump(),
        point=func.ST_GeomFromEWKT(point_wkt)
    )
    db.add(point)
    db.commit()
    db.refresh(point)
    return TripSessionPointRead.model_validate(point)


@router.post("/{session_id}/locations/batch", status_code=201)
def add_location_batch(
    session_id: UUID,
    batch: TripSessionPointBatch,
    db: Session = Depends(get_db)
) -> dict:
    """
    Upload a batch of GPS location points.

    This is the recommended way to upload location data - collect points
    locally on the device and upload in batches every 30-60 seconds.
    """
    session = db.get(TripSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Trip session not found")

    if session.status != SessionStatus.IN_PROGRESS:
        raise HTTPException(status_code=400, detail="Session is not in progress")

    if not batch.points:
        raise HTTPException(status_code=400, detail="Batch cannot be empty")

    points = []
    for p in batch.points:
        point_wkt = f"SRID=4326;POINT({p.longitude} {p.latitude})"
        points.append(TripSessionPoint(
            session_id=session_id,
            **p.model_dump(),
            point=func.ST_GeomFromEWKT(point_wkt)
        ))

    db.add_all(points)

    # Update last activity timestamp
    session.last_activity_at = datetime.utcnow()

    db.commit()

    return {
        "added": len(points),
        "session_id": session_id,
        "first_timestamp": batch.points[0].timestamp.isoformat(),
        "last_timestamp": batch.points[-1].timestamp.isoformat(),
    }


@router.get("/{session_id}/locations", response_model=list[TripSessionPointRead])
def get_location_points(
    session_id: UUID,
    skip: int = 0,
    limit: int = 1000,
    db: Session = Depends(get_db)
) -> Sequence[TripSessionPointRead]:
    """Get all location points for a trip session."""
    session = db.get(TripSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Trip session not found")

    points = db.execute(
        select(TripSessionPoint)
        .where(TripSessionPoint.session_id == session_id)
        .order_by(TripSessionPoint.timestamp)
        .offset(skip).limit(limit)
    ).scalars().all()

    return [TripSessionPointRead.model_validate(p) for p in points]


# ============================================================
# Sensor Readings - Batch Upload
# ============================================================

@router.post("/{session_id}/sensors", response_model=TripSensorReadingRead, status_code=201)
def add_sensor_reading(
    session_id: UUID,
    reading_data: TripSensorReadingCreate,
    db: Session = Depends(get_db)
) -> TripSensorReadingRead:
    """Add a single sensor reading to a trip session."""
    session = db.get(TripSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Trip session not found")

    if session.status != SessionStatus.IN_PROGRESS:
        raise HTTPException(status_code=400, detail="Session is not in progress")

    reading = TripSensorReading(session_id=session_id, **reading_data.model_dump())
    db.add(reading)
    db.commit()
    db.refresh(reading)
    return TripSensorReadingRead.model_validate(reading)


@router.post("/{session_id}/sensors/batch", status_code=201)
def add_sensor_batch(
    session_id: UUID,
    batch: TripSensorReadingBatch,
    db: Session = Depends(get_db)
) -> dict:
    """
    Upload a batch of sensor readings (accelerometer, gyroscope, etc.).

    Sensor data is typically collected at higher frequencies than GPS,
    so batching is especially important here.
    """
    session = db.get(TripSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Trip session not found")

    if session.status != SessionStatus.IN_PROGRESS:
        raise HTTPException(status_code=400, detail="Session is not in progress")

    if not batch.readings:
        raise HTTPException(status_code=400, detail="Batch cannot be empty")

    readings = [
        TripSensorReading(session_id=session_id, **r.model_dump())
        for r in batch.readings
    ]

    db.add_all(readings)

    # Update last activity timestamp
    session.last_activity_at = datetime.utcnow()

    db.commit()

    return {
        "added": len(readings),
        "session_id": session_id,
        "first_timestamp": batch.readings[0].timestamp.isoformat(),
        "last_timestamp": batch.readings[-1].timestamp.isoformat(),
    }


@router.get("/{session_id}/sensors", response_model=list[TripSensorReadingRead])
def get_sensor_readings(
    session_id: UUID,
    skip: int = 0,
    limit: int = 1000,
    db: Session = Depends(get_db)
) -> Sequence[TripSensorReadingRead]:
    """Get all sensor readings for a trip session."""
    session = db.get(TripSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Trip session not found")

    readings = db.execute(
        select(TripSensorReading)
        .where(TripSensorReading.session_id == session_id)
        .order_by(TripSensorReading.timestamp)
        .offset(skip).limit(limit)
    ).scalars().all()

    return [TripSensorReadingRead.model_validate(r) for r in readings]


# ============================================================
# Stale Session Cleanup
# ============================================================

@router.post("/cleanup/stale", tags=["admin"])
def cleanup_stale_sessions(
    inactive_minutes: int = Query(
        default=30,
        ge=5,
        description="Mark sessions as abandoned if no activity for this many minutes"
    ),
    db: Session = Depends(get_db)
) -> dict:
    """
    Mark stale trip sessions as abandoned (admin/cron operation).

    Sessions with no activity for longer than `inactive_minutes` will be:
    - Marked as ABANDONED
    - Have their computed_path generated from existing points
    - Have ended_at set to last_activity_at

    Call this periodically via cron job (e.g., every 15 minutes).
    """
    cutoff = datetime.utcnow() - timedelta(minutes=inactive_minutes)

    # Find stale sessions
    stale_sessions = db.execute(
        select(TripSession)
        .where(TripSession.status == SessionStatus.IN_PROGRESS)
        .where(TripSession.last_activity_at < cutoff)
    ).scalars().all()

    abandoned_count = 0
    for session in stale_sessions:
        # Compute path from whatever points we have
        points = db.execute(
            select(TripSessionPoint)
            .where(TripSessionPoint.session_id == session.id)
            .order_by(TripSessionPoint.timestamp)
        ).scalars().all()

        if len(points) >= 2:
            coords = [(p.longitude, p.latitude) for p in points]
            linestring = f"SRID=4326;LINESTRING({', '.join(f'{lon} {lat}' for lon, lat in coords)})"
            session.computed_path = func.ST_GeomFromEWKT(linestring)

        session.status = SessionStatus.ABANDONED
        session.ended_at = session.last_activity_at
        abandoned_count += 1

    db.commit()

    return {
        "checked_before": cutoff.isoformat(),
        "abandoned_count": abandoned_count,
        "session_ids": [s.id for s in stale_sessions]
    }


@router.post("/{session_id}/simplify", response_model=TripSessionRead)
def simplify_recording(
    session_id: UUID,
    tolerance: float = Query(
        default=0.00005,
        ge=0.000001,
        description="RDP tolerance in degrees (WGS84); ~0.00005 ≈ 5 m",
    ),
    db: Session = Depends(get_db),
) -> TripSessionRead:
    """
    Apply PostGIS ST_Simplify (Douglas-Peucker) to the trip session path.

    Overwrites computed_path with the simplified linestring and removes
    location points that were filtered out by the algorithm.
    """
    session = db.get(TripSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Trip session not found")

    try:
        reduce_linestring_from_recording_session(db, session_id, tolerance=tolerance)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    db.commit()
    db.refresh(session)
    return TripSessionRead.model_validate(session)


@router.post("/{session_id}/resume", response_model=TripSessionRead)
def resume_recording(session_id: UUID, db: Session = Depends(get_db)) -> TripSessionRead:
    """
    Resume an abandoned trip session.

    If a session was auto-abandoned but the user comes back,
    they can resume it (e.g., if they just had a long tunnel with no signal).
    """
    session = db.get(TripSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Trip session not found")

    if session.status != SessionStatus.ABANDONED:
        raise HTTPException(
            status_code=400,
            detail=f"Only abandoned sessions can be resumed (current status: {session.status})"
        )

    session.status = SessionStatus.IN_PROGRESS
    session.ended_at = None
    session.last_activity_at = datetime.utcnow()

    db.commit()
    db.refresh(session)
    return TripSessionRead.model_validate(session)
