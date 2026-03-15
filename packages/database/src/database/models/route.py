"""Route reconstruction models — cleaned trips, estimations, segments, and votes."""

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


# ---------------------------------------------------------------------------
# Trip (cleaned / map-matched)
# ---------------------------------------------------------------------------


class TripStatus(str, Enum):
    """Whether the cleaned trip matches the existing route."""

    CLEAN = "clean"
    DEVIATED = "deviated"


class Trip(SQLModel, table=True):
    """A cleaned / map-matched version of a raw TripSession."""

    __tablename__ = "trips"

    id: Optional[UUID] = Field(default_factory=_uuid.uuid4, primary_key=True)
    session_id: UUID = Field(foreign_key="trip_sessions.id", index=True)
    line_id: UUID = Field(foreign_key="lines.id", index=True)

    status: TripStatus = Field(default=TripStatus.CLEAN)
    match_score: Optional[float] = Field(default=None)
    frechet_distance: Optional[float] = Field(default=None)

    computed_path: Any = Field(
        default=None,
        sa_column=Column(
            Geometry(geometry_type="LINESTRING", srid=4326),
            nullable=True,
        ),
    )

    processed_at: datetime = Field(default_factory=datetime.utcnow)

    session: Optional["TripSession"] = Relationship(back_populates="trips")
    line: Optional["Line"] = Relationship(back_populates="trips")
    points: list["TripPoint"] = Relationship(back_populates="trip")
    votes: list["SegmentVote"] = Relationship(back_populates="trip")
    travel_time_samples: list["TravelTimeSample"] = Relationship(back_populates="trip")
    resampled_trips: list["ResampledTrip"] = Relationship(back_populates="trip")


class TripPoint(SQLModel, table=True):
    """A single point in a cleaned trip (after HMM map-matching)."""

    __tablename__ = "trip_points"

    id: Optional[UUID] = Field(default_factory=_uuid.uuid4, primary_key=True)
    trip_id: UUID = Field(foreign_key="trips.id", index=True)
    point_index: int

    timestamp: datetime
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)

    point: Any = Field(
        default=None,
        sa_column=Column(
            Geometry(geometry_type="POINT", srid=4326),
            nullable=True,
        ),
    )

    trip: Optional["Trip"] = Relationship(back_populates="points")


# ---------------------------------------------------------------------------
# Route estimation (DBSCAN consensus)
# ---------------------------------------------------------------------------


class EstimationStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    SUPERSEDED = "superseded"


class RouteEstimation(SQLModel, table=True):
    """A DBSCAN consensus route for a line (versioned)."""

    __tablename__ = "route_estimations"

    id: Optional[UUID] = Field(default_factory=_uuid.uuid4, primary_key=True)
    line_id: UUID = Field(foreign_key="lines.id", index=True)
    version: int = Field(default=1)

    status: EstimationStatus = Field(default=EstimationStatus.PENDING)
    trip_count: int = Field(default=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    line: Optional["Line"] = Relationship(back_populates="route_estimations")
    segments: list["RouteSegment"] = Relationship(back_populates="estimation")


# ---------------------------------------------------------------------------
# Route segments (chunks for voting)
# ---------------------------------------------------------------------------


class SegmentStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"


class RouteSegment(SQLModel, table=True):
    """A chunk of an estimated route — the unit of user voting."""

    __tablename__ = "route_segments"

    id: Optional[UUID] = Field(default_factory=_uuid.uuid4, primary_key=True)
    estimation_id: UUID = Field(foreign_key="route_estimations.id", index=True)
    sequence: int

    path: Any = Field(
        sa_column=Column(
            Geometry(geometry_type="LINESTRING", srid=4326),
            nullable=True,
        ),
    )

    confidence: float = Field(default=0.0)
    status: SegmentStatus = Field(default=SegmentStatus.PENDING)
    votes_for: int = Field(default=0)
    votes_against: int = Field(default=0)
    confirmed_at: Optional[datetime] = Field(default=None)

    estimation: Optional["RouteEstimation"] = Relationship(back_populates="segments")
    votes: list["SegmentVote"] = Relationship(back_populates="segment")
    travel_time_samples: list["TravelTimeSample"] = Relationship(back_populates="segment")


# ---------------------------------------------------------------------------
# Segment votes
# ---------------------------------------------------------------------------


class VoteChoice(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"


class SegmentVote(SQLModel, table=True):
    """A vote on a route segment, backed by a cleaned trip."""

    __tablename__ = "segment_votes"

    id: Optional[UUID] = Field(default_factory=_uuid.uuid4, primary_key=True)
    segment_id: UUID = Field(foreign_key="route_segments.id", index=True)
    trip_id: UUID = Field(foreign_key="trips.id", index=True)

    vote: VoteChoice
    created_at: datetime = Field(default_factory=datetime.utcnow)

    segment: Optional["RouteSegment"] = Relationship(back_populates="votes")
    trip: Optional["Trip"] = Relationship(back_populates="votes")


# ---------------------------------------------------------------------------
# Resampled trips (uniform-interval normalization)
# ---------------------------------------------------------------------------


class ResampledTrip(SQLModel, table=True):
    """A Trip resampled to uniform distance intervals (pipeline step 4)."""

    __tablename__ = "resampled_trips"

    id: Optional[UUID] = Field(default_factory=_uuid.uuid4, primary_key=True)
    trip_id: UUID = Field(foreign_key="trips.id", index=True)

    interval_meters: float = Field(description="Resampling interval in metres")
    match_score: float = Field(description="Match score of the source Trip")
    point_count: int = Field(default=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    trip: Optional["Trip"] = Relationship(back_populates="resampled_trips")
    points: list["ResampledTripPoint"] = Relationship(back_populates="resampled_trip")


class ResampledTripPoint(SQLModel, table=True):
    """A single point in a resampled trip."""

    __tablename__ = "resampled_trip_points"

    id: Optional[UUID] = Field(default_factory=_uuid.uuid4, primary_key=True)
    resampled_trip_id: UUID = Field(foreign_key="resampled_trips.id", index=True)
    point_index: int

    timestamp: datetime
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)

    point: Any = Field(
        default=None,
        sa_column=Column(
            Geometry(geometry_type="POINT", srid=4326),
            nullable=True,
        ),
    )

    resampled_trip: Optional["ResampledTrip"] = Relationship(back_populates="points")


# ---------------------------------------------------------------------------
# Travel time samples
# ---------------------------------------------------------------------------


class TravelTimeSample(SQLModel, table=True):
    """Timing data from a clean trip for A→B estimation."""

    __tablename__ = "travel_time_samples"

    id: Optional[UUID] = Field(default_factory=_uuid.uuid4, primary_key=True)
    trip_id: UUID = Field(foreign_key="trips.id", index=True)
    segment_id: UUID = Field(foreign_key="route_segments.id", index=True)

    duration_seconds: float
    day_of_week: int = Field(ge=0, le=6)
    hour_of_day: int = Field(ge=0, le=23)

    trip: Optional["Trip"] = Relationship(back_populates="travel_time_samples")
    segment: Optional["RouteSegment"] = Relationship(back_populates="travel_time_samples")
