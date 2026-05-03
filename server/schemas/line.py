from datetime import datetime, time
from typing import Any, Optional
from uuid import UUID

from database.models.line import Line, LineBase, LineStatus, LineType
from database.models.line_schedule import DayBucket
from pydantic import model_validator
from sqlmodel import Field, SQLModel


class LineCreate(LineBase):
    """Schema for creating a new line."""

    line_type: Optional[LineType] = None


class DayScheduleRead(SQLModel):
    """One inferred schedule entry for a (line, day_bucket) pair.

    Times are local Cochabamba time (UTC-4). `headway_min` may be null
    when the cadence is unreliable (RF-24); in that case service hours
    can still be present.
    """

    day_bucket: DayBucket
    service_start_at: Optional[time] = None
    service_end_at: Optional[time] = None
    headway_min: Optional[int] = None
    inferred_at: Optional[datetime] = None


class LineRead(LineBase):
    """Schema for reading a line (API response)."""

    id: UUID
    status: LineStatus
    line_type: Optional[LineType] = None
    merged_into_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
    schedules: list[DayScheduleRead] = []

    @model_validator(mode="before")
    @classmethod
    def convert_from_model(cls, data: Any) -> Any:
        if isinstance(data, Line):
            return {
                "id": data.id,
                "name": data.name,
                "description": data.description,
                "status": data.status,
                "line_type": data.line_type,
                "merged_into_id": data.merged_into_id,
                "created_at": data.created_at,
                "updated_at": data.updated_at,
                "schedules": [
                    DayScheduleRead(
                        day_bucket=s.day_bucket,
                        service_start_at=s.service_start_at,
                        service_end_at=s.service_end_at,
                        headway_min=s.headway_min,
                        inferred_at=s.inferred_at,
                    )
                    for s in (data.schedules or [])
                ],
            }
        return data


class RamalSummary(SQLModel):
    """Identity copy for one ramal — what the mobile card displays.

    The internal `ramal_label` (`main`, `r2`, …) is *not* exposed:
    users identify ramales by `endpoint_zones` (Beijing → Sacaba) and
    `street_summary` (Av. Beijing · Av. América · …) instead.
    """

    route_id: UUID
    endpoint_zones: list[Optional[str]] = [None, None]
    street_summary: list[str] = []


class NearbyLineWithRouteRead(SQLModel):
    """A line near a coordinate, with its route geometry."""

    line_id: UUID
    line_name: str
    line_description: Optional[str] = None
    route_geojson: Optional[dict] = None
    detour_alert: Optional[dict] = None
    # Per-ramal identity surfaced for the line card. Multi-ramal lines
    # return one entry per active ramal (each card shows its own
    # endpoints/streets); single-ramal lines collapse to a 1-element
    # list. `street_summary` and `endpoint_zones` are populated from
    # `Route.street_summary` / `Route.endpoint_zones` (gap #7 / RF-07).
    ramales: list[RamalSummary] = []


class LineUpdate(SQLModel):
    """Schema for updating a line (all fields optional)."""

    name: Optional[str] = Field(default=None, max_length=255)
    description: Optional[str] = Field(default=None, max_length=1000)
    status: Optional[LineStatus] = None
    line_type: Optional[LineType] = None
