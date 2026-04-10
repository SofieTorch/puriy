"""Detour models — temporary alternate routes for bus lines."""

import uuid as _uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional
from uuid import UUID

from geoalchemy2 import Geometry
from sqlalchemy import Column
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .line import Line
    from .trip import TripSession


class DetourStatus(str, Enum):
    ACTIVE = "active"
    EXPIRED = "expired"


class Detour(SQLModel, table=True):
    """A temporary alternate route for a bus line.

    Published immediately when reported. Confidence decays over time.
    Auto-expires 7 days after last confirmation.
    """

    __tablename__ = "detours"

    id: Optional[UUID] = Field(default_factory=_uuid.uuid4, primary_key=True)
    line_id: UUID = Field(foreign_key="lines.id", index=True)
    session_id: UUID = Field(foreign_key="trip_sessions.id", index=True)

    status: DetourStatus = Field(default=DetourStatus.ACTIVE)
    reason: Optional[str] = Field(default=None, max_length=50)
    description: Optional[str] = Field(default=None, max_length=500)

    path: Any = Field(
        default=None,
        sa_column=Column(
            Geometry(geometry_type="LINESTRING", srid=4326),
            nullable=True,
        ),
    )

    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_confirmed_at: datetime = Field(default_factory=datetime.utcnow)
    confirmed_count: int = Field(default=1)

    line: Optional["Line"] = Relationship(back_populates="detours")
    session: Optional["TripSession"] = Relationship(back_populates="detour")
