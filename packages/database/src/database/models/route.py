"""Route reconstruction models — cleaned trips, routes, edges, and votes."""

import uuid as _uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional
from uuid import UUID

from geoalchemy2 import Geometry
from sqlalchemy import BigInteger, Column, Index, UniqueConstraint
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
    matched_edges: list["TripMatchedEdge"] = Relationship(back_populates="trip")
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


class TripMatchedEdge(SQLModel, table=True):
    """One ordered Valhalla edge traversal step for a cleaned trip."""

    __tablename__ = "trip_matched_edges"
    __table_args__ = (
        UniqueConstraint("trip_id", "sequence", name="uq_trip_matched_edges_trip_sequence"),
        Index("ix_trip_matched_edges_valhalla_edge_id_forward", "valhalla_edge_id", "forward"),
    )

    id: Optional[UUID] = Field(default_factory=_uuid.uuid4, primary_key=True)
    trip_id: UUID = Field(foreign_key="trips.id", index=True)
    sequence: int

    valhalla_edge_id: int = Field(
        sa_column=Column(BigInteger, nullable=False),
    )
    forward: bool = Field(default=True)

    trip: Optional["Trip"] = Relationship(back_populates="matched_edges")


# ---------------------------------------------------------------------------
# Route (versioned route for a line)
# ---------------------------------------------------------------------------


class RouteStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    SUPERSEDED = "superseded"


class RouteSource(str, Enum):
    COMPUTED = "computed"
    IMPORTED = "imported"


class Route(SQLModel, table=True):
    """A versioned route for a line, composed of road-network edges."""

    __tablename__ = "routes"

    id: Optional[UUID] = Field(default_factory=_uuid.uuid4, primary_key=True)
    line_id: UUID = Field(foreign_key="lines.id", index=True)
    version: int = Field(default=1)

    source: RouteSource = Field(default=RouteSource.COMPUTED)
    status: RouteStatus = Field(default=RouteStatus.PENDING)
    trip_count: int = Field(default=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    line: Optional["Line"] = Relationship(back_populates="routes")
    edges: list["RouteEdge"] = Relationship(back_populates="route")


# ---------------------------------------------------------------------------
# Route edges (Valhalla road-network edges — atomic voting unit)
# ---------------------------------------------------------------------------


class EdgeStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"


class RouteEdge(SQLModel, table=True):
    """A Valhalla road-network edge within an estimated route — the atomic voting unit."""

    __tablename__ = "route_edges"

    id: Optional[UUID] = Field(default_factory=_uuid.uuid4, primary_key=True)
    route_id: UUID = Field(foreign_key="routes.id", index=True)
    sequence: int

    valhalla_edge_id: Optional[int] = Field(
        default=None,
        sa_column=Column(BigInteger, nullable=True),
    )
    forward: bool = Field(default=True)

    path: Any = Field(
        sa_column=Column(
            Geometry(geometry_type="LINESTRING", srid=4326),
            nullable=True,
        ),
    )

    confidence: float = Field(default=0.0)
    status: EdgeStatus = Field(default=EdgeStatus.PENDING)
    votes_for: int = Field(default=0)
    votes_against: int = Field(default=0)
    confirmed_at: Optional[datetime] = Field(default=None)

    route: Optional["Route"] = Relationship(back_populates="edges")
    votes: list["EdgeVote"] = Relationship(back_populates="edge")
    travel_time_samples: list["TravelTimeSample"] = Relationship(back_populates="edge")


# ---------------------------------------------------------------------------
# Edge votes
# ---------------------------------------------------------------------------


class VoteChoice(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"


class EdgeVote(SQLModel, table=True):
    """A vote on a route edge, attributed by device."""

    __tablename__ = "edge_votes"
    __table_args__ = (
        UniqueConstraint("edge_id", "device_id", name="uq_edge_vote_device"),
    )

    id: Optional[UUID] = Field(default_factory=_uuid.uuid4, primary_key=True)
    edge_id: UUID = Field(foreign_key="route_edges.id", index=True)
    device_id: str = Field(max_length=255, index=True)

    vote: VoteChoice
    created_at: datetime = Field(default_factory=datetime.utcnow)

    edge: Optional["RouteEdge"] = Relationship(back_populates="votes")


# ---------------------------------------------------------------------------
# Resampled trips (uniform-interval normalization)
# ---------------------------------------------------------------------------


class ResampledTrip(SQLModel, table=True):
    """A Trip resampled to uniform distance intervals (pipeline step 4)."""

    __tablename__ = "resampled_trips"

    id: Optional[UUID] = Field(default_factory=_uuid.uuid4, primary_key=True)
    trip_id: UUID = Field(foreign_key="trips.id", index=True)

    interval_meters: float = Field(description="Resampling interval in metres")
    match_score: Optional[float] = Field(default=None, description="Min score filter used when batch-resampled; null for manual resamples")
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
    edge_id: UUID = Field(foreign_key="route_edges.id", index=True)

    duration_seconds: float
    day_of_week: int = Field(ge=0, le=6)
    hour_of_day: int = Field(ge=0, le=23)

    trip: Optional["Trip"] = Relationship(back_populates="travel_time_samples")
    edge: Optional["RouteEdge"] = Relationship(back_populates="travel_time_samples")
