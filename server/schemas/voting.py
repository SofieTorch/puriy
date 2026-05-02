from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from database.models.route import EdgeStatus, RouteEdge, VoteChoice
from geoalchemy2 import WKBElement
from pydantic import model_validator
from shapely import wkb
from shapely.geometry import LineString
from sqlmodel import SQLModel


class PendingLineRead(SQLModel):
    """A line with pending edges to vote on."""

    line_id: UUID
    line_name: str
    line_description: Optional[str] = None
    route_id: UUID
    pending_edge_count: int
    total_edge_count: int


class VoteableEdgeRead(SQLModel):
    """A route edge available for voting."""

    id: UUID
    sequence: int
    valhalla_edge_id: Optional[int] = None
    path: Optional[list[list[float]]] = None
    confidence: float
    status: EdgeStatus
    votes_for: int
    votes_against: int

    @model_validator(mode="before")
    @classmethod
    def convert_geometry(cls, data: Any) -> Any:
        if isinstance(data, RouteEdge):
            result = {
                "id": data.id,
                "sequence": data.sequence,
                "valhalla_edge_id": data.valhalla_edge_id,
                "path": None,
                "confidence": data.confidence,
                "status": data.status,
                "votes_for": data.votes_for,
                "votes_against": data.votes_against,
            }
            if data.path is not None:
                if isinstance(data.path, WKBElement):
                    shape = wkb.loads(bytes(data.path.data))
                    result["path"] = [list(c) for c in shape.coords]
                elif isinstance(data.path, LineString):
                    result["path"] = [list(c) for c in data.coords]
            return result
        return data


class VoteableSectionRead(SQLModel):
    """A contiguous group of edges the user can vote on as a unit."""

    section_index: int
    edges: list[VoteableEdgeRead] = []
    trip_count: int  # how many of the user's trips cover this section
    geometry: list[list[float]] = []  # stitched [lon, lat] coordinates


class VoteableSegmentRead(SQLModel):
    """The voteable segment for a line — edges that overlap with the user's trips."""

    route_id: UUID
    line_name: str
    line_description: Optional[str] = None
    route_geojson: Optional[dict] = None  # full route geometry for context
    sections: list[VoteableSectionRead] = []  # grouped contiguous sections
    edges: list[VoteableEdgeRead] = []
    segment_geojson: Optional[dict] = None


class VoteRequest(SQLModel):
    """Request body for submitting a vote."""

    device_id: str
    vote: VoteChoice
    section_index: Optional[int] = None  # vote on specific section only


class VoteResponse(SQLModel):
    """Response after submitting a vote."""

    edges_voted: int
    vote: VoteChoice


class NearbyLineRead(SQLModel):
    """A nearby line available for familiarity voting."""

    line_id: UUID
    line_name: str
    line_description: Optional[str] = None


class LineVoteRequest(SQLModel):
    """Request body for submitting a line familiarity vote."""

    device_id: str
    vote: VoteChoice


class LineVoteResponse(SQLModel):
    """Response after submitting a line vote."""

    line_id: UUID
    vote: VoteChoice
