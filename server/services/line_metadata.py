"""Reusable lookups for per-line metadata used outside the /lines/* and
/fares/* endpoints — currently called from /directions/ to attach a
fare estimate and the current frequency to each bus leg of a planned
route.

Both functions are resilient: they return None when data is missing
(no fare reports yet, no schedule inferred for today's bucket) so
callers can render the rest of the response without bailing out.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy import Numeric, cast, func, select
from sqlalchemy.orm import Session

from database.models.fare import FareReport, FareZone
from database.models.line import Line, LineType
from database.models.line_schedule import DayBucket, LineSchedule

LOCAL_TZ = timezone(timedelta(hours=-4))  # Cochabamba, no DST.


def _resolve_zone(db: Session, lat: float, lon: float) -> UUID | None:
    point = func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326)
    return db.execute(
        select(FareZone.id).where(func.ST_Contains(FareZone.boundary, point))
    ).scalars().first()


def _fare_median():
    """Median fare amount (rounded to 2 dp). Median, not mean, so a stray
    misreport doesn't skew the estimate — the point of crowdsourcing with noise.
    """
    # percentile_cont returns double precision; cast to numeric so round(x, 2)
    # is valid in Postgres.
    return func.round(
        cast(func.percentile_cont(0.5).within_group(FareReport.amount_bob.asc()), Numeric),
        2,
    )


def estimate_fare_bob(
    db: Session,
    line_id: UUID,
    boarding_lat: float,
    boarding_lon: float,
    alighting_lat: float,
    alighting_lon: float,
) -> Optional[float]:
    """Return the estimated fare in BOB for one bus leg, or None if there's
    no signal (no reports / unresolvable zones).

    For MICRO lines the fare is a flat median across all reports;
    for trufi/taxi-trufi lines it's the median over the resolved
    boarding/alighting zone-pair (symmetric).
    """
    line = db.get(Line, line_id)
    if line is None:
        return None

    if line.line_type == LineType.MICRO:
        median = db.execute(
            select(_fare_median()).where(FareReport.line_id == line_id)
        ).scalar_one_or_none()
        return float(median) if median is not None else None

    boarding_zone_id = _resolve_zone(db, boarding_lat, boarding_lon)
    alighting_zone_id = _resolve_zone(db, alighting_lat, alighting_lon)
    if not boarding_zone_id or not alighting_zone_id:
        return None

    median = db.execute(
        select(_fare_median()).where(
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
    ).scalar_one_or_none()
    return float(median) if median is not None else None


def _today_bucket(now: Optional[datetime] = None) -> DayBucket:
    """Map today's local weekday to a DayBucket.

    `now` is exposed for testing — defaults to current local Cochabamba time.
    """
    dt = (now or datetime.now(timezone.utc)).astimezone(LOCAL_TZ)
    weekday = dt.weekday()
    if weekday == 5:
        return DayBucket.SATURDAY
    if weekday == 6:
        return DayBucket.SUNDAY
    return DayBucket.WEEKDAY


def current_headway_min(
    db: Session,
    line_id: UUID,
    *,
    now: Optional[datetime] = None,
) -> Optional[int]:
    """Return the published headway (minutes) for `line_id` in today's bucket,
    or None if no `LineSchedule` row exists for that bucket or the cadence
    was deemed unreliable (RF-24).
    """
    bucket = _today_bucket(now)
    row = db.get(LineSchedule, (line_id, bucket))
    if row is None:
        return None
    return row.headway_min
