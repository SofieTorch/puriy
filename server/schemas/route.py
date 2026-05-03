from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from database.models.route import (
    EdgeStatus,
    Route,
    RouteEdge,
    RouteSource,
    RouteStatus,
)
from geoalchemy2 import WKBElement
from pydantic import model_validator
from shapely import wkb
from shapely.geometry import LineString
from sqlmodel import SQLModel


class RouteEdgeRead(SQLModel):
    """Schema for reading a route edge (API response)."""

    id: UUID
    route_id: UUID
    sequence: int
    valhalla_edge_id: Optional[int] = None
    forward: bool
    path: Optional[list[list[float]]] = None
    confidence: float
    status: EdgeStatus
    votes_for: int
    votes_against: int
    confirmed_at: Optional[datetime] = None

    @model_validator(mode="before")
    @classmethod
    def convert_geometry(cls, data: Any) -> Any:
        if isinstance(data, RouteEdge):
            result = {
                "id": data.id,
                "route_id": data.route_id,
                "sequence": data.sequence,
                "valhalla_edge_id": data.valhalla_edge_id,
                "forward": data.forward,
                "path": None,
                "confidence": data.confidence,
                "status": data.status,
                "votes_for": data.votes_for,
                "votes_against": data.votes_against,
                "confirmed_at": data.confirmed_at,
            }
            if data.path is not None:
                if isinstance(data.path, WKBElement):
                    shape = wkb.loads(bytes(data.path.data))
                    result["path"] = list(shape.coords)
                elif isinstance(data.path, LineString):
                    result["path"] = list(data.path.coords)
            return result
        return data


class RouteRead(SQLModel):
    """Schema for reading a route (API response)."""

    id: UUID
    line_id: UUID
    version: int
    ramal_label: str
    source: RouteSource
    status: RouteStatus
    trip_count: int
    strategy_key: Optional[str] = None
    fragment_index: int
    fragment_count: int
    created_at: datetime
    street_summary: list[str] = []
    endpoint_zones: list[Optional[str]] = [None, None]
    edges: list[RouteEdgeRead] = []

    @model_validator(mode="before")
    @classmethod
    def convert_edges(cls, data: Any) -> Any:
        if isinstance(data, Route):
            return {
                "id": data.id,
                "line_id": data.line_id,
                "version": data.version,
                "ramal_label": data.ramal_label,
                "source": data.source,
                "status": data.status,
                "trip_count": data.trip_count,
                "strategy_key": data.strategy_key,
                "fragment_index": data.fragment_index,
                "fragment_count": data.fragment_count,
                "created_at": data.created_at,
                "street_summary": data.street_summary or [],
                "endpoint_zones": data.endpoint_zones or [None, None],
                "edges": [
                    RouteEdgeRead.model_validate(edge)
                    for edge in data.edges
                ],
            }
        return data
