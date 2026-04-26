"""Fare models — zones and crowdsourced fare reports."""

import uuid as _uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional
from uuid import UUID

from geoalchemy2 import Geometry
from sqlalchemy import Column, Numeric
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .line import Line
    from .trip import TripSession


class FareZone(SQLModel, table=True):
    """A geographic zone used for zone-pair fare lookups (e.g., a municipality)."""

    __tablename__ = "fare_zones"

    id: Optional[UUID] = Field(default_factory=_uuid.uuid4, primary_key=True)
    name: str = Field(max_length=255, index=True, unique=True)

    boundary: Any = Field(
        default=None,
        sa_column=Column(
            Geometry(geometry_type="MULTIPOLYGON", srid=4326),
            nullable=True,
        ),
    )

    created_at: datetime = Field(default_factory=datetime.utcnow)

    boarding_reports: list["FareReport"] = Relationship(
        back_populates="boarding_zone",
        sa_relationship_kwargs={"foreign_keys": "[FareReport.boarding_zone_id]"},
    )
    alighting_reports: list["FareReport"] = Relationship(
        back_populates="alighting_zone",
        sa_relationship_kwargs={"foreign_keys": "[FareReport.alighting_zone_id]"},
    )


class FareReport(SQLModel, table=True):
    """A crowdsourced fare observation submitted by a user."""

    __tablename__ = "fare_reports"

    id: Optional[UUID] = Field(default_factory=_uuid.uuid4, primary_key=True)
    line_id: UUID = Field(foreign_key="lines.id", index=True)
    device_id: str = Field(max_length=255, index=True)
    session_id: Optional[UUID] = Field(default=None, foreign_key="trip_sessions.id")

    amount_bob: float = Field(
        sa_column=Column(Numeric(6, 2), nullable=False),
    )

    boarding_latitude: float = Field(ge=-90, le=90)
    boarding_longitude: float = Field(ge=-180, le=180)
    alighting_latitude: float = Field(ge=-90, le=90)
    alighting_longitude: float = Field(ge=-180, le=180)

    boarding_zone_id: Optional[UUID] = Field(
        default=None, foreign_key="fare_zones.id", index=True,
    )
    alighting_zone_id: Optional[UUID] = Field(
        default=None, foreign_key="fare_zones.id", index=True,
    )

    created_at: datetime = Field(default_factory=datetime.utcnow)

    line: Optional["Line"] = Relationship(back_populates="fare_reports")
    session: Optional["TripSession"] = Relationship(back_populates="fare_reports")
    boarding_zone: Optional["FareZone"] = Relationship(
        back_populates="boarding_reports",
        sa_relationship_kwargs={"foreign_keys": "[FareReport.boarding_zone_id]"},
    )
    alighting_zone: Optional["FareZone"] = Relationship(
        back_populates="alighting_reports",
        sa_relationship_kwargs={"foreign_keys": "[FareReport.alighting_zone_id]"},
    )
