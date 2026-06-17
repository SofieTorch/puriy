"""Assign crowdsourced fare reports to fare zones (point-in-polygon).

The fare equivalent of map-matching: a raw `FareReport` carries boarding /
alighting coordinates; this resolves each to the `FareZone` (municipality) that
contains it, so trufi (zone-based) fares can be aggregated per zone pair. Micro
fares are a flat average and don't need zones. Idempotent — only touches reports
with an unresolved zone.
"""

from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from database.models import FareReport
from geodata.fares import resolve_zone


def execute(db: Session, *, line_id: UUID | None = None) -> dict:
    query = select(FareReport).where(
        or_(
            FareReport.boarding_zone_id.is_(None),
            FareReport.alighting_zone_id.is_(None),
        )
    )
    if line_id:
        query = query.where(FareReport.line_id == line_id)

    reports = db.execute(query).scalars().all()
    boarding_resolved = 0
    alighting_resolved = 0

    for r in reports:
        if r.boarding_zone_id is None:
            z = resolve_zone(db, r.boarding_latitude, r.boarding_longitude)
            if z is not None:
                r.boarding_zone_id = z
                boarding_resolved += 1
        if r.alighting_zone_id is None:
            z = resolve_zone(db, r.alighting_latitude, r.alighting_longitude)
            if z is not None:
                r.alighting_zone_id = z
                alighting_resolved += 1

    db.commit()
    return {
        "reports_checked": len(reports),
        "boarding_resolved": boarding_resolved,
        "alighting_resolved": alighting_resolved,
    }
