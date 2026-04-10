import uuid as _uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional
from uuid import UUID

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel

from .route import VoteChoice

if TYPE_CHECKING:
    from .route import Route, Trip
    from .trip import TripSession


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
    """A transit line (e.g., "Line 42", "Red Line").

    The route geometry lives in the associated Route records (versioned).
    """

    __tablename__ = "lines"

    id: Optional[UUID] = Field(default_factory=_uuid.uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    status: LineStatus = Field(default=LineStatus.PENDING)
    merged_into_id: Optional[UUID] = Field(default=None, foreign_key="lines.id")

    trip_sessions: list["TripSession"] = Relationship(back_populates="line")
    trips: list["Trip"] = Relationship(back_populates="line")
    routes: list["Route"] = Relationship(back_populates="line")
    line_votes: list["LineVote"] = Relationship(back_populates="line")


class LineVote(SQLModel, table=True):
    """A familiarity vote on a transit line — 'I know this line exists in my area'."""

    __tablename__ = "line_votes"
    __table_args__ = (
        UniqueConstraint("line_id", "device_id", name="uq_line_vote_device"),
    )

    id: Optional[UUID] = Field(default_factory=_uuid.uuid4, primary_key=True)
    line_id: UUID = Field(foreign_key="lines.id", index=True)
    device_id: str = Field(max_length=255, index=True)

    vote: VoteChoice = Field()
    created_at: datetime = Field(default_factory=datetime.utcnow)

    line: Optional["Line"] = Relationship(back_populates="line_votes")
