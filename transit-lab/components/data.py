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
    VoteChoice,
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


def load_route_edges(
    db: Session,
    line_id: UUID,
    *,
    route_id: UUID | None = None,
) -> list[dict]:
    """Load edges for a route. Defaults to the active route for the line."""
    if route_id is not None:
        route = db.get(Route, route_id)
    else:
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


def count_eligible_voters(db: Session, line_id: UUID, *, min_trips: int = 3) -> int:
    """Count distinct devices with at least ``min_trips`` cleaned trips on a line."""
    device_trip_counts = (
        select(TripSession.device_id, func.count(Trip.id).label("trip_count"))
        .join(Trip, Trip.session_id == TripSession.id)
        .where(
            Trip.line_id == line_id,
            Trip.computed_path.isnot(None),
            TripSession.device_id.isnot(None),
        )
        .group_by(TripSession.device_id)
        .subquery()
    )
    return db.execute(
        select(func.count())
        .select_from(device_trip_counts)
        .where(device_trip_counts.c.trip_count >= min_trips)
    ).scalar_one()


def load_edge_voter_counts(db: Session, route_id: UUID) -> dict[str, int]:
    """Map ``edge_id`` (as str) -> distinct voter count for the given route."""
    rows = db.execute(
        select(EdgeVote.edge_id, func.count(func.distinct(EdgeVote.device_id)))
        .join(RouteEdge, RouteEdge.id == EdgeVote.edge_id)
        .where(RouteEdge.route_id == route_id)
        .group_by(EdgeVote.edge_id)
    ).all()
    return {str(edge_id): int(count) for edge_id, count in rows}


def load_voting_events(db: Session, route_id: UUID) -> list[dict]:
    """Reconstruct voting events for a route by grouping EdgeVote rows.

    A voting event is one device's POST to /vote/{line_id}; that creates many
    EdgeVote rows in a single transaction with very close timestamps. We group
    by (device_id, vote, second-bucketed created_at) and aggregate the edge ids.
    """
    bucket = func.date_trunc("second", EdgeVote.created_at).label("event_time")
    rows = db.execute(
        select(
            EdgeVote.device_id,
            EdgeVote.vote,
            bucket,
            func.count().label("edge_count"),
            func.array_agg(EdgeVote.edge_id).label("edge_ids"),
        )
        .join(RouteEdge, RouteEdge.id == EdgeVote.edge_id)
        .where(RouteEdge.route_id == route_id)
        .group_by(EdgeVote.device_id, EdgeVote.vote, bucket)
        .order_by(bucket.desc())
    ).all()
    return [
        {
            "device_id": device_id,
            "vote": vote.value if isinstance(vote, VoteChoice) else str(vote),
            "created_at": created_at,
            "edge_count": int(edge_count),
            "edge_ids": [str(eid) for eid in edge_ids],
        }
        for device_id, vote, created_at, edge_count, edge_ids in rows
    ]


def load_segment_for_device(
    db: Session,
    line_id: UUID,
    device_id: str,
    *,
    min_trips: int = 3,
) -> dict:
    """Compute what segment the live API would currently show this device.

    Returns a dict with:
      - ``trip_count``: cleaned trips this device has on the line
      - ``eligible``: True if trip_count >= min_trips
      - ``edges``: list of edge dicts (same shape as load_route_edges) — empty
        when not eligible or no overlap remains
    """
    from geodata.edge_overlap import (
        count_device_trips_for_line,
        find_unvoted_overlapping_edges,
        get_active_route,
        get_device_trips_for_line,
    )

    trip_count = count_device_trips_for_line(db, device_id, line_id)
    if trip_count < min_trips:
        return {"trip_count": trip_count, "eligible": False, "edges": []}

    route = get_active_route(db, line_id)
    if route is None:
        return {"trip_count": trip_count, "eligible": True, "edges": []}

    trips = get_device_trips_for_line(db, device_id, line_id)
    trip_ids = [t.id for t in trips]
    edges = find_unvoted_overlapping_edges(db, route.id, trip_ids, device_id)

    edge_dicts = []
    for edge in edges:
        edge_dicts.append({
            "id": str(edge.id),
            "route_id": str(edge.route_id),
            "sequence": edge.sequence,
            "valhalla_edge_id": edge.valhalla_edge_id,
            "forward": edge.forward,
            "confidence": edge.confidence,
            "status": edge.status.value,
            "votes_for": edge.votes_for,
            "votes_against": edge.votes_against,
            "path": _extract_coords(edge.path),
        })
    return {"trip_count": trip_count, "eligible": True, "edges": edge_dicts}


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
