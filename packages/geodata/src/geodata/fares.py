"""Fare helpers — resolve a point to its fare zone, and estimate a line's fare.

Fare model by bus type:
- **micro** (and unknown types): a flat rate — the average of all the line's
  fare reports, regardless of distance.
- **trufi / taxi_trufi**: zone-based — the fare depends on how far you travel,
  looked up by the (boarding zone, alighting zone) pair.
"""

from __future__ import annotations

from sqlalchemy import Numeric, cast, func, select
from sqlalchemy.orm import Session

from database.models import FareReport, FareZone, Line, LineType


def resolve_zone(db: Session, lat: float, lon: float):
    """Return the id of the FareZone containing (lat, lon), or None."""
    point = func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326)
    return db.execute(
        select(FareZone.id).where(func.ST_Contains(FareZone.boundary, point))
    ).scalars().first()


def _is_zonal(line: Line) -> bool:
    return line.line_type in (LineType.TRUFI, LineType.TAXI_TRUFI)


def _flat_estimate(db: Session, line_id) -> dict:
    avg = db.execute(
        select(func.round(cast(func.percentile_cont(0.5).within_group(FareReport.amount_bob.asc()), Numeric), 2))
        .where(FareReport.line_id == line_id)
    ).scalar()
    n = db.execute(
        select(func.count()).select_from(FareReport)
        .where(FareReport.line_id == line_id)
    ).scalar() or 0
    return {
        "type": "flat",
        "amount_bob": float(avg) if avg is not None else None,
        "reports": int(n),
    }


def estimate_line_fare(db: Session, line: Line) -> dict:
    """A line-level fare summary. Micro → a single flat amount; trufi → the
    range across zone pairs plus the per-pair breakdown."""
    if _is_zonal(line):
        rows = db.execute(
            select(
                FareReport.boarding_zone_id,
                FareReport.alighting_zone_id,
                func.round(cast(func.percentile_cont(0.5).within_group(FareReport.amount_bob.asc()), Numeric), 2),
                func.count(),
            )
            .where(
                FareReport.line_id == line.id,
                FareReport.boarding_zone_id.is_not(None),
                FareReport.alighting_zone_id.is_not(None),
            )
            .group_by(FareReport.boarding_zone_id, FareReport.alighting_zone_id)
        ).all()
        if rows:
            names = dict(db.execute(select(FareZone.id, FareZone.name)).all())
            pairs = [
                {
                    "boarding_zone": names.get(bz),
                    "alighting_zone": names.get(az),
                    "amount_bob": float(amt),
                    "reports": int(n),
                }
                for bz, az, amt, n in rows
            ]
            amounts = [p["amount_bob"] for p in pairs]
            return {
                "type": "zonal",
                "min_bob": min(amounts),
                "max_bob": max(amounts),
                "pairs": pairs,
            }
    # micro, or zonal line without resolved zone data yet → flat average.
    return _flat_estimate(db, line.id)
