from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional

from geoalchemy2 import Geometry
from sqlalchemy import Column
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .recording import RecordingSession


class LineStatus(str, Enum):
    """Status of a transit line."""

    PENDING = "pending"
    APPROVED = "approved"
    MERGED = "merged"


class LineBase(SQLModel):
    """Base model for Line with common fields."""

    name: str = Field(max_length=255, index=True)
    description: Optional[str] = Field(default=None, max_length=1000)


class Line(LineBase, table=True):
    """
    A transit line (e.g., "Line 42", "Red Line").

    The path is stored as a PostGIS LINESTRING geometry in WGS84 (SRID 4326).
    """

    __tablename__ = "lines"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    path: Any = Field(
        sa_column=Column(
            Geometry(geometry_type="LINESTRING", srid=4326),
            nullable=True,
        )
    )

    status: LineStatus = Field(default=LineStatus.PENDING)
    merged_into_id: Optional[int] = Field(default=None, foreign_key="lines.id")

    recordings: list["RecordingSession"] = Relationship(back_populates="line")
