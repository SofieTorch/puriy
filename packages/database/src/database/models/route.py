"""Route reconstruction models — cleaned trips, routes, edges, and votes."""

import uuid as _uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional
from uuid import UUID

from geoalchemy2 import Geometry
from sqlalchemy import BigInteger, Column, Index, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
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
    __table_args__ = (
        # One active route per (line, ramal). The partial WHERE clause
        # excludes superseded rows so version chains can grow freely.
        Index(
            "uq_route_active_per_ramal",
            "line_id", "ramal_label",
            unique=True,
            postgresql_where=text("status != 'SUPERSEDED'"),
        ),
    )

    id: Optional[UUID] = Field(default_factory=_uuid.uuid4, primary_key=True)
    line_id: UUID = Field(foreign_key="lines.id", index=True)
    version: int = Field(default=1)

    source: RouteSource = Field(default=RouteSource.COMPUTED)
    status: RouteStatus = Field(default=RouteStatus.PENDING)
    trip_count: int = Field(default=0)
    strategy_key: Optional[str] = Field(default=None, max_length=100)
    fragment_index: int = Field(default=0)
    fragment_count: int = Field(default=1)
    # Internal grouping key: distinguishes ramales (variants) of the same
    # line. "main" for the first ramal a line gets; auto-detected
    # additional ramales get "r2", "r3", … assigned by the pipeline. Never
    # rendered to users — UIs identify ramales by geometry + endpoint
    # zones + street summary instead.
    ramal_label: str = Field(default="main", max_length=64, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    # Last time this route was compared against a freshly reconstructed
    # candidate and deemed close enough to keep (RF-19). Updated by the
    # `reconstruct_routes` pipeline step. None means it was never compared
    # after initial creation.
    last_compared_at: Optional[datetime] = Field(default=None)

    # Human-readable street/avenue names the route runs along, in order
    # (e.g. ["Av. Beijing", "Av. América", "Av. Pacata"]). Populated from
    # Valhalla `trace_match` edge names, filtered by minimum run length
    # so cross-streets don't appear. Also serves RF-07 ("show destinations
    # textually") on the line cards.
    street_summary: Optional[list[str]] = Field(
        default=None, sa_column=Column(JSONB, nullable=True),
    )
    # `[start_zone, end_zone]` neighbourhood/zone names for the first
    # and last polyline points (e.g. ["Beijing", "Sacaba"]). Reverse-
    # geocoded via Nominatim. Either side may be None if geocoding
    # didn't return a usable admin level.
    endpoint_zones: Optional[list[Optional[str]]] = Field(
        default=None, sa_column=Column(JSONB, nullable=True),
    )

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
    device_id: str = Field(foreign_key="devices.id", max_length=255, index=True)

    vote: VoteChoice
    created_at: datetime = Field(default_factory=datetime.utcnow)

    edge: Optional["RouteEdge"] = Relationship(back_populates="votes")


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
