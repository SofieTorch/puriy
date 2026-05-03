"""Inferred service hours and headway per line, bucketed by day type.

Each line gets up to three rows in `line_schedules` — one per
DayBucket (weekday / saturday / sunday). Rows are written by the
`infer_schedules` pipeline step from raw TripSession timestamps.
"""

from datetime import datetime, time
from enum import Enum
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .line import Line


class DayBucket(str, Enum):
    """Three coarse day buckets that share a typical service pattern.

    Holidays are treated as the day-of-week they fall on (v1
    simplification, documented in the Diseño chapter).
    """

    WEEKDAY = "weekday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"


class LineSchedule(SQLModel, table=True):
    """One inferred schedule entry for a (line, day_bucket) pair.

    Times are stored in **local Cochabamba time** (UTC-4, no DST), since
    that's how the user perceives "service starts at 06:00".

    `headway_min` may be NULL when the inference deems the cadence
    unreliable (high coefficient of variation); in that case the row
    still carries `service_start_at` / `service_end_at` so the client
    can show service hours without a frequency claim (RF-24).
    """

    __tablename__ = "line_schedules"

    line_id: UUID = Field(foreign_key="lines.id", primary_key=True)
    day_bucket: DayBucket = Field(primary_key=True)

    service_start_at: Optional[time] = Field(default=None)
    service_end_at: Optional[time] = Field(default=None)
    headway_min: Optional[int] = Field(default=None)

    inferred_at: datetime = Field(default_factory=datetime.utcnow)

    line: Optional["Line"] = Relationship(back_populates="schedules")
