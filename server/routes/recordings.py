from datetime import datetime, timedelta
from typing import Sequence

from database.models.line import Line, LineStatus
from database.models.recording import (
    LocationPoint,
    RecordingSession,
    RecordingStatus,
    SensorReading,
)
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from database.connection import get_db
from geodata.simplify import simplify_recording_session
from schemas.recording import (
    EndRecordingRequest,
    LocationPointBatch,
    LocationPointCreate,
    LocationPointRead,
    RecordingSessionCreate,
    RecordingSessionRead,
    SensorReadingBatch,
    SensorReadingCreate,
    SensorReadingRead,
)

router = APIRouter(prefix="/recordings", tags=["recordings"])


# ============================================================
# Recording Sessions
# ============================================================

@router.post("/", response_model=RecordingSessionRead, status_code=201)
def start_recording(
    session_data: RecordingSessionCreate,
    db: Session = Depends(get_db)
) -> RecordingSessionRead:
    """
    Start a new recording session.

    The line is not required at start; it will be assigned when the session ends.
    """
    session = RecordingSession(
        line_id=None,
        direction=session_data.direction,
        device_model=session_data.device_model,
        os_version=session_data.os_version,
        notes=session_data.notes,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return RecordingSessionRead.model_validate(session)


@router.get("/", response_model=list[RecordingSessionRead])
def list_recordings(
    line_id: int | None = None,
    status: RecordingStatus | None = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
) -> Sequence[RecordingSessionRead]:
    """List recording sessions with optional filters."""
    query = select(RecordingSession)

    if line_id is not None:
        query = query.where(RecordingSession.line_id == line_id)
    if status is not None:
        query = query.where(RecordingSession.status == status)
    
    sessions = db.execute(
        query.order_by(RecordingSession.started_at.desc())
        .offset(skip).limit(limit)
    ).scalars().all()
    
    return [RecordingSessionRead.model_validate(s) for s in sessions]


@router.get("/{session_id}", response_model=RecordingSessionRead)
def get_recording(session_id: int, db: Session = Depends(get_db)) -> RecordingSessionRead:
    """Get a specific recording session."""
    session = db.get(RecordingSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Recording session not found")
    return RecordingSessionRead.model_validate(session)


@router.post("/{session_id}/end", response_model=RecordingSessionRead)
def end_recording(
    session_id: int,
    body: EndRecordingRequest,
    db: Session = Depends(get_db),
) -> RecordingSessionRead:
    """
    End a recording session.

    - If line_id is provided: assign to that line, status COMPLETED.
    - If line_id is null but line_name is provided: create a new line (PENDING) and assign, status COMPLETED.
    - If both are null: status DISCARDED.
    The computed path is always generated from the collected location points.
    """
    session = db.get(RecordingSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Recording session not found")

    if session.status != RecordingStatus.IN_PROGRESS:
        raise HTTPException(
            status_code=400,
            detail=f"Session is not in progress (current status: {session.status})"
        )

    # Compute path from location points
    points = db.execute(
        select(LocationPoint)
        .where(LocationPoint.session_id == session_id)
        .order_by(LocationPoint.timestamp)
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
        session.status = RecordingStatus.COMPLETED
    elif line_name_trimmed:
        new_line = Line(
            name=line_name_trimmed,
            status=LineStatus.PENDING,
        )
        db.add(new_line)
        db.flush()
        session.line_id = new_line.id
        session.status = RecordingStatus.COMPLETED
    else:
        session.status = RecordingStatus.DISCARDED

    session.ended_at = datetime.utcnow()

    db.commit()
    db.refresh(session)
    return RecordingSessionRead.model_validate(session)


@router.post("/{session_id}/cancel", response_model=RecordingSessionRead)
def cancel_recording(session_id: int, db: Session = Depends(get_db)) -> RecordingSessionRead:
    """Cancel an in-progress recording session."""
    session = db.get(RecordingSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Recording session not found")
    
    if session.status != RecordingStatus.IN_PROGRESS:
        raise HTTPException(
            status_code=400,
            detail=f"Session is not in progress (current status: {session.status})"
        )
    
    session.status = RecordingStatus.CANCELLED
    session.ended_at = datetime.utcnow()
    
    db.commit()
    db.refresh(session)
    return RecordingSessionRead.model_validate(session)


# ============================================================
# Location Points - Batch Upload
# ============================================================

@router.post("/{session_id}/locations", response_model=LocationPointRead, status_code=201)
def add_location_point(
    session_id: int,
    point_data: LocationPointCreate,
    db: Session = Depends(get_db)
) -> LocationPointRead:
    """Add a single location point to a recording session."""
    session = db.get(RecordingSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Recording session not found")
    
    if session.status != RecordingStatus.IN_PROGRESS:
        raise HTTPException(status_code=400, detail="Session is not in progress")
    
    # Create PostGIS point
    point_wkt = f"SRID=4326;POINT({point_data.longitude} {point_data.latitude})"
    
    point = LocationPoint(
        session_id=session_id,
        **point_data.model_dump(),
        point=func.ST_GeomFromEWKT(point_wkt)
    )
    db.add(point)
    db.commit()
    db.refresh(point)
    return LocationPointRead.model_validate(point)


@router.post("/{session_id}/locations/batch", status_code=201)
def add_location_batch(
    session_id: int,
    batch: LocationPointBatch,
    db: Session = Depends(get_db)
) -> dict:
    """
    Upload a batch of GPS location points.
    
    This is the recommended way to upload location data - collect points
    locally on the device and upload in batches every 30-60 seconds.
    """
    session = db.get(RecordingSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Recording session not found")
    
    if session.status != RecordingStatus.IN_PROGRESS:
        raise HTTPException(status_code=400, detail="Session is not in progress")
    
    if not batch.points:
        raise HTTPException(status_code=400, detail="Batch cannot be empty")
    
    points = []
    for p in batch.points:
        point_wkt = f"SRID=4326;POINT({p.longitude} {p.latitude})"
        points.append(LocationPoint(
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


@router.get("/{session_id}/locations", response_model=list[LocationPointRead])
def get_location_points(
    session_id: int,
    skip: int = 0,
    limit: int = 1000,
    db: Session = Depends(get_db)
) -> Sequence[LocationPointRead]:
    """Get all location points for a recording session."""
    session = db.get(RecordingSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Recording session not found")
    
    points = db.execute(
        select(LocationPoint)
        .where(LocationPoint.session_id == session_id)
        .order_by(LocationPoint.timestamp)
        .offset(skip).limit(limit)
    ).scalars().all()
    
    return [LocationPointRead.model_validate(p) for p in points]


# ============================================================
# Sensor Readings - Batch Upload
# ============================================================

@router.post("/{session_id}/sensors", response_model=SensorReadingRead, status_code=201)
def add_sensor_reading(
    session_id: int,
    reading_data: SensorReadingCreate,
    db: Session = Depends(get_db)
) -> SensorReadingRead:
    """Add a single sensor reading to a recording session."""
    session = db.get(RecordingSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Recording session not found")
    
    if session.status != RecordingStatus.IN_PROGRESS:
        raise HTTPException(status_code=400, detail="Session is not in progress")
    
    reading = SensorReading(session_id=session_id, **reading_data.model_dump())
    db.add(reading)
    db.commit()
    db.refresh(reading)
    return SensorReadingRead.model_validate(reading)


@router.post("/{session_id}/sensors/batch", status_code=201)
def add_sensor_batch(
    session_id: int,
    batch: SensorReadingBatch,
    db: Session = Depends(get_db)
) -> dict:
    """
    Upload a batch of sensor readings (accelerometer, gyroscope, etc.).
    
    Sensor data is typically collected at higher frequencies than GPS,
    so batching is especially important here.
    """
    session = db.get(RecordingSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Recording session not found")
    
    if session.status != RecordingStatus.IN_PROGRESS:
        raise HTTPException(status_code=400, detail="Session is not in progress")
    
    if not batch.readings:
        raise HTTPException(status_code=400, detail="Batch cannot be empty")
    
    readings = [
        SensorReading(session_id=session_id, **r.model_dump())
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


@router.get("/{session_id}/sensors", response_model=list[SensorReadingRead])
def get_sensor_readings(
    session_id: int,
    skip: int = 0,
    limit: int = 1000,
    db: Session = Depends(get_db)
) -> Sequence[SensorReadingRead]:
    """Get all sensor readings for a recording session."""
    session = db.get(RecordingSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Recording session not found")
    
    readings = db.execute(
        select(SensorReading)
        .where(SensorReading.session_id == session_id)
        .order_by(SensorReading.timestamp)
        .offset(skip).limit(limit)
    ).scalars().all()
    
    return [SensorReadingRead.model_validate(r) for r in readings]


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
    Mark stale recording sessions as abandoned (admin/cron operation).
    
    Sessions with no activity for longer than `inactive_minutes` will be:
    - Marked as ABANDONED
    - Have their computed_path generated from existing points
    - Have ended_at set to last_activity_at
    
    Call this periodically via cron job (e.g., every 15 minutes).
    """
    cutoff = datetime.utcnow() - timedelta(minutes=inactive_minutes)
    
    # Find stale sessions
    stale_sessions = db.execute(
        select(RecordingSession)
        .where(RecordingSession.status == RecordingStatus.IN_PROGRESS)
        .where(RecordingSession.last_activity_at < cutoff)
    ).scalars().all()
    
    abandoned_count = 0
    for session in stale_sessions:
        # Compute path from whatever points we have
        points = db.execute(
            select(LocationPoint)
            .where(LocationPoint.session_id == session.id)
            .order_by(LocationPoint.timestamp)
        ).scalars().all()
        
        if len(points) >= 2:
            coords = [(p.longitude, p.latitude) for p in points]
            linestring = f"SRID=4326;LINESTRING({', '.join(f'{lon} {lat}' for lon, lat in coords)})"
            session.computed_path = func.ST_GeomFromEWKT(linestring)
        
        session.status = RecordingStatus.ABANDONED
        session.ended_at = session.last_activity_at
        abandoned_count += 1
    
    db.commit()
    
    return {
        "checked_before": cutoff.isoformat(),
        "abandoned_count": abandoned_count,
        "session_ids": [s.id for s in stale_sessions]
    }


@router.post("/{session_id}/simplify", response_model=RecordingSessionRead)
def simplify_recording(
    session_id: int,
    tolerance: float = Query(
        default=0.00005,
        ge=0.000001,
        description="RDP tolerance in degrees (WGS84); ~0.00005 ≈ 5 m",
    ),
    db: Session = Depends(get_db),
) -> RecordingSessionRead:
    """
    Apply PostGIS ST_Simplify (Douglas-Peucker) to the recording session path.

    Overwrites computed_path with the simplified linestring and removes
    location points that were filtered out by the algorithm.
    """
    session = db.get(RecordingSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Recording session not found")

    try:
        simplify_recording_session(db, session_id, tolerance=tolerance)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    db.commit()
    db.refresh(session)
    return RecordingSessionRead.model_validate(session)


@router.post("/{session_id}/resume", response_model=RecordingSessionRead)
def resume_recording(session_id: int, db: Session = Depends(get_db)) -> RecordingSessionRead:
    """
    Resume an abandoned recording session.
    
    If a session was auto-abandoned but the user comes back,
    they can resume it (e.g., if they just had a long tunnel with no signal).
    """
    session = db.get(RecordingSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Recording session not found")
    
    if session.status != RecordingStatus.ABANDONED:
        raise HTTPException(
            status_code=400,
            detail=f"Only abandoned sessions can be resumed (current status: {session.status})"
        )
    
    session.status = RecordingStatus.IN_PROGRESS
    session.ended_at = None
    session.last_activity_at = datetime.utcnow()
    
    db.commit()
    db.refresh(session)
    return RecordingSessionRead.model_validate(session)
