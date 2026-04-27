from typing import Sequence
from uuid import UUID

from database.models.fare import FareReport, FareZone
from database.models.line import Line, LineType
from fastapi import APIRouter, Depends, HTTPException, Query
from geoalchemy2 import WKBElement
from shapely import wkb
from shapely.geometry import mapping
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from database.connection import get_db
from schemas.fare import (
    FareEstimateRead,
    FareReportCreate,
    FareReportRead,
    FareZoneRead,
    LineFareRead,
    ZoneFareRead,
)

router = APIRouter(prefix="/fares", tags=["fares"])


def _resolve_zone(db: Session, lat: float, lon: float) -> UUID | None:
    """Find the fare zone containing the given point, or None."""
    point = func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326)
    zone_id = db.execute(
        select(FareZone.id).where(func.ST_Contains(FareZone.boundary, point))
    ).scalars().first()
    return zone_id


def _zone_read(zone: FareZone) -> FareZoneRead:
    """Convert a FareZone model to its read schema."""
    boundary_geojson = None
    if zone.boundary is not None:
        if isinstance(zone.boundary, WKBElement):
            shape = wkb.loads(bytes(zone.boundary.data))
            boundary_geojson = mapping(shape)
    return FareZoneRead(id=zone.id, name=zone.name, boundary_geojson=boundary_geojson)


# ============================================================
# Zones
# ============================================================


@router.get("/zones", response_model=list[FareZoneRead])
def list_fare_zones(db: Session = Depends(get_db)) -> list[FareZoneRead]:
    """List all fare zones."""
    zones = db.execute(select(FareZone).order_by(FareZone.name)).scalars().all()
    return [_zone_read(z) for z in zones]


# ============================================================
# Reports
# ============================================================


@router.post("/reports", response_model=FareReportRead, status_code=201)
def submit_fare_report(
    body: FareReportCreate,
    db: Session = Depends(get_db),
) -> FareReportRead:
    """Submit a crowdsourced fare observation."""
    line = db.get(Line, body.line_id)
    if not line:
        raise HTTPException(status_code=404, detail="Line not found")

    boarding_zone_id = _resolve_zone(db, body.boarding_latitude, body.boarding_longitude)
    alighting_zone_id = _resolve_zone(db, body.alighting_latitude, body.alighting_longitude)

    report = FareReport(
        line_id=body.line_id,
        device_id=body.device_id,
        session_id=body.session_id,
        amount_bob=body.amount_bob,
        boarding_latitude=body.boarding_latitude,
        boarding_longitude=body.boarding_longitude,
        alighting_latitude=body.alighting_latitude,
        alighting_longitude=body.alighting_longitude,
        boarding_zone_id=boarding_zone_id,
        alighting_zone_id=alighting_zone_id,
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    boarding_zone_name = None
    alighting_zone_name = None
    if report.boarding_zone_id:
        bz = db.get(FareZone, report.boarding_zone_id)
        if bz:
            boarding_zone_name = bz.name
    if report.alighting_zone_id:
        az = db.get(FareZone, report.alighting_zone_id)
        if az:
            alighting_zone_name = az.name

    return FareReportRead(
        id=report.id,
        line_id=report.line_id,
        device_id=report.device_id,
        session_id=report.session_id,
        amount_bob=float(report.amount_bob),
        boarding_latitude=report.boarding_latitude,
        boarding_longitude=report.boarding_longitude,
        alighting_latitude=report.alighting_latitude,
        alighting_longitude=report.alighting_longitude,
        boarding_zone=boarding_zone_name,
        alighting_zone=alighting_zone_name,
        created_at=report.created_at,
    )


@router.get("/reports", response_model=list[FareReportRead])
def list_fare_reports(
    line_id: UUID | None = None,
    device_id: str | None = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
) -> Sequence[FareReportRead]:
    """List fare reports with optional filters."""
    bz = select(FareZone.name).where(FareZone.id == FareReport.boarding_zone_id).correlate(FareReport).scalar_subquery()
    az = select(FareZone.name).where(FareZone.id == FareReport.alighting_zone_id).correlate(FareReport).scalar_subquery()

    query = select(FareReport, bz.label("boarding_zone"), az.label("alighting_zone"))
    if line_id is not None:
        query = query.where(FareReport.line_id == line_id)
    if device_id is not None:
        query = query.where(FareReport.device_id == device_id)

    rows = db.execute(
        query.order_by(FareReport.created_at.desc()).offset(skip).limit(limit)
    ).all()

    return [
        FareReportRead(
            id=report.id,
            line_id=report.line_id,
            device_id=report.device_id,
            session_id=report.session_id,
            amount_bob=float(report.amount_bob),
            boarding_latitude=report.boarding_latitude,
            boarding_longitude=report.boarding_longitude,
            alighting_latitude=report.alighting_latitude,
            alighting_longitude=report.alighting_longitude,
            boarding_zone=boarding_zone,
            alighting_zone=alighting_zone,
            created_at=report.created_at,
        )
        for report, boarding_zone, alighting_zone in rows
    ]


# ============================================================
# Fare lookup
# ============================================================


def _aggregate_zone_fares(db: Session, line_id: UUID) -> list[ZoneFareRead]:
    """Aggregate fare reports into zone-pair fare entries."""
    bz = select(FareZone.name).where(FareZone.id == FareReport.boarding_zone_id).correlate(FareReport).scalar_subquery()
    az = select(FareZone.name).where(FareZone.id == FareReport.alighting_zone_id).correlate(FareReport).scalar_subquery()

    rows = db.execute(
        select(
            bz.label("boarding_zone"),
            az.label("alighting_zone"),
            func.round(func.avg(FareReport.amount_bob), 2).label("avg_amount"),
            func.count().label("report_count"),
        )
        .where(
            FareReport.line_id == line_id,
            FareReport.boarding_zone_id.is_not(None),
            FareReport.alighting_zone_id.is_not(None),
        )
        .group_by(FareReport.boarding_zone_id, FareReport.alighting_zone_id)
        .order_by(func.count().desc())
    ).all()

    return [
        ZoneFareRead(
            boarding_zone=row.boarding_zone,
            alighting_zone=row.alighting_zone,
            amount_bob=float(row.avg_amount),
            report_count=row.report_count,
        )
        for row in rows
        if row.boarding_zone and row.alighting_zone
    ]


@router.get("/lines/{line_id}", response_model=LineFareRead)
def get_line_fares(line_id: UUID, db: Session = Depends(get_db)) -> LineFareRead:
    """Get aggregated fare information for a line.

    For micros: returns a flat_rate (average of all reports).
    For trufis/taxi-trufis: returns a zone-pair fare matrix.
    """
    line = db.get(Line, line_id)
    if not line:
        raise HTTPException(status_code=404, detail="Line not found")

    if line.line_type == LineType.MICRO:
        avg_row = db.execute(
            select(
                func.round(func.avg(FareReport.amount_bob), 2).label("avg_amount"),
            ).where(FareReport.line_id == line_id)
        ).first()
        flat_rate = float(avg_row.avg_amount) if avg_row and avg_row.avg_amount else None
        return LineFareRead(
            line_id=line.id,
            line_name=line.name,
            line_type=line.line_type,
            flat_rate=flat_rate,
            zone_fares=[],
        )

    zone_fares = _aggregate_zone_fares(db, line_id)
    return LineFareRead(
        line_id=line.id,
        line_name=line.name,
        line_type=line.line_type,
        flat_rate=None,
        zone_fares=zone_fares,
    )


@router.get("/estimate", response_model=FareEstimateRead)
def estimate_fare(
    line_id: UUID = Query(...),
    boarding_lat: float = Query(..., ge=-90, le=90),
    boarding_lon: float = Query(..., ge=-180, le=180),
    alighting_lat: float = Query(..., ge=-90, le=90),
    alighting_lon: float = Query(..., ge=-180, le=180),
    db: Session = Depends(get_db),
) -> FareEstimateRead:
    """Estimate the fare for a specific boarding/alighting location pair."""
    line = db.get(Line, line_id)
    if not line:
        raise HTTPException(status_code=404, detail="Line not found")

    # For micros, zone doesn't matter — return flat average
    if line.line_type == LineType.MICRO:
        row = db.execute(
            select(
                func.round(func.avg(FareReport.amount_bob), 2).label("avg_amount"),
                func.count().label("report_count"),
            ).where(FareReport.line_id == line_id)
        ).first()
        return FareEstimateRead(
            line_id=line_id,
            estimated_amount_bob=float(row.avg_amount) if row and row.avg_amount else None,
            report_count=row.report_count if row else 0,
        )

    # For trufis/taxi-trufis, resolve zones and look up zone-pair fare
    boarding_zone_id = _resolve_zone(db, boarding_lat, boarding_lon)
    alighting_zone_id = _resolve_zone(db, alighting_lat, alighting_lon)

    boarding_zone_name = None
    alighting_zone_name = None
    if boarding_zone_id:
        bz = db.get(FareZone, boarding_zone_id)
        if bz:
            boarding_zone_name = bz.name
    if alighting_zone_id:
        az = db.get(FareZone, alighting_zone_id)
        if az:
            alighting_zone_name = az.name

    if not boarding_zone_id or not alighting_zone_id:
        return FareEstimateRead(
            line_id=line_id,
            boarding_zone=boarding_zone_name,
            alighting_zone=alighting_zone_name,
            estimated_amount_bob=None,
            report_count=0,
        )

    # Query both directions (symmetric fares)
    row = db.execute(
        select(
            func.round(func.avg(FareReport.amount_bob), 2).label("avg_amount"),
            func.count().label("report_count"),
        ).where(
            FareReport.line_id == line_id,
            (
                (FareReport.boarding_zone_id == boarding_zone_id)
                & (FareReport.alighting_zone_id == alighting_zone_id)
            )
            | (
                (FareReport.boarding_zone_id == alighting_zone_id)
                & (FareReport.alighting_zone_id == boarding_zone_id)
            ),
        )
    ).first()

    return FareEstimateRead(
        line_id=line_id,
        boarding_zone=boarding_zone_name,
        alighting_zone=alighting_zone_name,
        estimated_amount_bob=float(row.avg_amount) if row and row.avg_amount else None,
        report_count=row.report_count if row else 0,
    )
