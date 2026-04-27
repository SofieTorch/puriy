"""Shared database query helpers for transit-lab notebooks.

Decouples data loading from rendering — each function returns plain dicts
or lists ready for display, not ORM objects.
"""

from uuid import UUID

from geoalchemy2 import WKBElement
from shapely import wkb
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from database.models import (
    EdgeVote,
    Line,
    LineStatus,
    Route,
    RouteEdge,
    RouteStatus,
    Trip,
    TripSession,
    SessionStatus,
)


def load_lines(db: Session, *, status: LineStatus | None = None) -> list[dict]:
    """Load lines with session/trip/route counts."""
    query = select(Line)
    if status is not None:
        query = query.where(Line.status == status)
    lines = db.execute(query.order_by(Line.name)).scalars().all()

    result = []
    for line in lines:
        session_count = db.execute(
            select(func.count()).where(TripSession.line_id == line.id)
        ).scalar() or 0
        trip_count = db.execute(
            select(func.count()).where(Trip.line_id == line.id)
        ).scalar() or 0
        route = db.execute(
            select(Route)
            .where(Route.line_id == line.id, Route.status != RouteStatus.SUPERSEDED)
            .order_by(Route.version.desc())
        ).scalars().first()

        result.append({
            "id": str(line.id),
            "name": line.name,
            "description": line.description or "",
            "line_type": line.line_type.value if line.line_type else "",
            "status": line.status.value,
            "session_count": session_count,
            "trip_count": trip_count,
            "route_version": route.version if route else None,
            "route_strategy": route.strategy_key or "" if route else "",
            "fragment_count": route.fragment_count if route else 0,
        })
    return result


def load_sessions(
    db: Session,
    line_id: UUID,
    *,
    status: SessionStatus | None = None,
) -> list[dict]:
    """Load trip sessions for a line."""
    query = select(TripSession).where(TripSession.line_id == line_id)
    if status is not None:
        query = query.where(TripSession.status == status)
    sessions = db.execute(query.order_by(TripSession.started_at.desc())).scalars().all()

    result = []
    for s in sessions:
        path_coords = _extract_coords(s.computed_path)
        trip = db.execute(
            select(Trip).where(Trip.session_id == s.id)
        ).scalars().first()

        result.append({
            "id": str(s.id),
            "device_id": s.device_id or "",
            "status": s.status.value,
            "processing_status": s.processing_status.value,
            "started_at": s.started_at.isoformat() if s.started_at else "",
            "ended_at": s.ended_at.isoformat() if s.ended_at else "",
            "point_count": len(s.points) if s.points else 0,
            "has_trip": trip is not None,
            "match_score": f"{trip.match_score:.2f}" if trip and trip.match_score else "",
            "trip_id": str(trip.id) if trip else None,
            "path": path_coords,
        })
    return result


def load_trips(db: Session, line_id: UUID, *, min_score: float = 0.0) -> list[dict]:
    """Load cleaned trips for a line."""
    query = select(Trip).where(Trip.line_id == line_id)
    if min_score > 0:
        query = query.where(Trip.match_score >= min_score)
    trips = db.execute(query.order_by(Trip.processed_at)).scalars().all()

    result = []
    for trip in trips:
        path_coords = _extract_coords(trip.computed_path)
        result.append({
            "id": str(trip.id),
            "session_id": str(trip.session_id),
            "status": trip.status.value,
            "match_score": trip.match_score,
            "frechet_distance": trip.frechet_distance,
            "path": path_coords,
        })
    return result


def load_route_edges(db: Session, line_id: UUID) -> list[dict]:
    """Load edges from the active route for a line."""
    route = db.execute(
        select(Route)
        .where(Route.line_id == line_id, Route.status != RouteStatus.SUPERSEDED)
        .order_by(Route.version.desc())
    ).scalars().first()

    if not route:
        return []

    edges = db.execute(
        select(RouteEdge)
        .where(RouteEdge.route_id == route.id)
        .order_by(RouteEdge.sequence)
    ).scalars().all()

    result = []
    for edge in edges:
        path_coords = _extract_coords(edge.path)
        result.append({
            "id": str(edge.id),
            "route_id": str(edge.route_id),
            "sequence": edge.sequence,
            "valhalla_edge_id": edge.valhalla_edge_id,
            "forward": edge.forward,
            "confidence": edge.confidence,
            "status": edge.status.value,
            "votes_for": edge.votes_for,
            "votes_against": edge.votes_against,
            "path": path_coords,
        })
    return result


def load_route_info(db: Session, line_id: UUID) -> list[dict]:
    """Load all route versions for a line."""
    routes = db.execute(
        select(Route)
        .where(Route.line_id == line_id)
        .order_by(Route.version.desc(), Route.fragment_index)
    ).scalars().all()

    result = []
    for route in routes:
        edge_count = db.execute(
            select(func.count()).where(RouteEdge.route_id == route.id)
        ).scalar() or 0
        result.append({
            "id": str(route.id),
            "version": route.version,
            "source": route.source.value,
            "status": route.status.value,
            "strategy_key": route.strategy_key or "",
            "trip_count": route.trip_count,
            "fragment_index": route.fragment_index,
            "fragment_count": route.fragment_count,
            "edge_count": edge_count,
            "created_at": route.created_at.isoformat(),
        })
    return result


def _extract_coords(geom) -> list[list[float]]:
    """Extract [[lon, lat], ...] from a PostGIS geometry or return empty list."""
    if geom is None:
        return []
    if isinstance(geom, WKBElement):
        shape = wkb.loads(bytes(geom.data))
        return [list(c) for c in shape.coords]
    try:
        return [list(c) for c in geom.coords]
    except Exception:
        return []
