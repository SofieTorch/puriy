from datetime import datetime
from typing import Optional
from uuid import UUID

from database.models.line import LineType
from sqlmodel import Field, SQLModel


class FareZoneRead(SQLModel):
    """Schema for reading a fare zone."""

    id: UUID
    name: str
    boundary_geojson: Optional[dict] = None


class FareReportCreate(SQLModel):
    """Schema for submitting a fare report."""

    line_id: UUID
    device_id: str = Field(max_length=255)
    session_id: Optional[UUID] = None
    amount_bob: float = Field(gt=0)
    boarding_latitude: float = Field(ge=-90, le=90)
    boarding_longitude: float = Field(ge=-180, le=180)
    alighting_latitude: float = Field(ge=-90, le=90)
    alighting_longitude: float = Field(ge=-180, le=180)


class FareReportRead(SQLModel):
    """Schema for reading a fare report."""

    id: UUID
    line_id: UUID
    device_id: str
    session_id: Optional[UUID] = None
    amount_bob: float
    boarding_latitude: float
    boarding_longitude: float
    alighting_latitude: float
    alighting_longitude: float
    boarding_zone: Optional[str] = None
    alighting_zone: Optional[str] = None
    created_at: datetime


class ZoneFareRead(SQLModel):
    """A single zone-pair fare entry."""

    boarding_zone: str
    alighting_zone: str
    amount_bob: float
    report_count: int


class LineFareRead(SQLModel):
    """Fare summary for a line."""

    line_id: UUID
    line_name: str
    line_type: Optional[LineType] = None
    flat_rate: Optional[float] = None
    zone_fares: list[ZoneFareRead] = []


class FareEstimateRead(SQLModel):
    """Estimated fare for a specific trip."""

    line_id: UUID
    boarding_zone: Optional[str] = None
    alighting_zone: Optional[str] = None
    estimated_amount_bob: Optional[float] = None
    report_count: int
