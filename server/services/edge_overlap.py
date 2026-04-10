"""Spatial overlap helpers for voting — edges and nearby lines via PostGIS."""

from uuid import UUID

from database.models.line import Line, LineVote
from database.models.route import EdgeVote, Route, RouteEdge, RouteStatus, Trip
from database.models.trip import TripSession
from sqlalchemy import func, select
from sqlalchemy.orm import Session

# Minimum number of cleaned trips required before a device can vote on a line.
DEFAULT_MIN_TRIPS = 3


def count_device_trips_for_line(
    db: Session,
    device_id: str,
    line_id: UUID,
) -> int:
    """Count cleaned trips for a device on a specific line."""
    return (
        db.execute(
            select(func.count())
            .select_from(Trip)
            .join(TripSession, Trip.session_id == TripSession.id)
            .where(
                TripSession.device_id == device_id,
                Trip.line_id == line_id,
                Trip.computed_path.isnot(None),
            )
        )
        .scalar_one()
    )


def get_device_trips_for_line(
    db: Session,
    device_id: str,
    line_id: UUID,
) -> list[Trip]:
    """Get all cleaned trips for a device on a specific line."""
    return (
        db.execute(
            select(Trip)
            .join(TripSession, Trip.session_id == TripSession.id)
            .where(
                TripSession.device_id == device_id,
                Trip.line_id == line_id,
                Trip.computed_path.isnot(None),
            )
        )
        .scalars()
        .all()
    )


def get_active_route(db: Session, line_id: UUID) -> Route | None:
    """Get the active (non-superseded) route for a line, preferring the latest version."""
    return (
        db.execute(
            select(Route)
            .where(
                Route.line_id == line_id,
                Route.status != RouteStatus.SUPERSEDED,
            )
            .order_by(Route.version.desc())
        )
        .scalars()
        .first()
    )


def find_overlapping_edges(
    db: Session,
    route_id: UUID,
    trip_ids: list[UUID],
    tolerance_meters: float = 50.0,
) -> list[RouteEdge]:
    """Find RouteEdges that spatially overlap with any of the given trips.

    Uses PostGIS ST_DWithin on EPSG:3857 (Web Mercator) for meter-based distance.
    """
    if not trip_ids:
        return []

    return (
        db.execute(
            select(RouteEdge)
            .distinct()
            .join(
                Trip,
                func.ST_DWithin(
                    func.ST_Transform(RouteEdge.path, 3857),
                    func.ST_Transform(Trip.computed_path, 3857),
                    tolerance_meters,
                ),
            )
            .where(
                RouteEdge.route_id == route_id,
                Trip.id.in_(trip_ids),
            )
            .order_by(RouteEdge.sequence)
        )
        .scalars()
        .all()
    )


def find_unvoted_overlapping_edges(
    db: Session,
    route_id: UUID,
    trip_ids: list[UUID],
    device_id: str,
    tolerance_meters: float = 50.0,
) -> list[RouteEdge]:
    """Find overlapping edges that this device hasn't voted on yet."""
    if not trip_ids:
        return []

    voted_edge_ids = (
        select(EdgeVote.edge_id)
        .where(EdgeVote.device_id == device_id)
        .scalar_subquery()
    )

    return (
        db.execute(
            select(RouteEdge)
            .distinct()
            .join(
                Trip,
                func.ST_DWithin(
                    func.ST_Transform(RouteEdge.path, 3857),
                    func.ST_Transform(Trip.computed_path, 3857),
                    tolerance_meters,
                ),
            )
            .where(
                RouteEdge.route_id == route_id,
                Trip.id.in_(trip_ids),
                RouteEdge.id.notin_(voted_edge_ids),
            )
            .order_by(RouteEdge.sequence)
        )
        .scalars()
        .all()
    )


def find_lines_near_device_trips(
    db: Session,
    device_id: str,
    radius_meters: float = 200.0,
) -> list[Line]:
    """Find lines whose routes pass near this device's trips.

    Excludes lines the device already has trips on and lines already voted on.
    """
    # Lines the device already rides
    ridden_line_ids = (
        select(Trip.line_id)
        .distinct()
        .join(TripSession, Trip.session_id == TripSession.id)
        .where(TripSession.device_id == device_id)
        .scalar_subquery()
    )

    # Lines already voted on
    voted_line_ids = (
        select(LineVote.line_id)
        .where(LineVote.device_id == device_id)
        .scalar_subquery()
    )

    return (
        db.execute(
            select(Line)
            .distinct()
            .join(Route, Route.line_id == Line.id)
            .join(RouteEdge, RouteEdge.route_id == Route.id)
            .join(
                Trip,
                func.ST_DWithin(
                    func.ST_Transform(RouteEdge.path, 3857),
                    func.ST_Transform(Trip.computed_path, 3857),
                    radius_meters,
                ),
            )
            .join(TripSession, Trip.session_id == TripSession.id)
            .where(
                TripSession.device_id == device_id,
                Route.status != RouteStatus.SUPERSEDED,
                Line.id.notin_(ridden_line_ids),
                Line.id.notin_(voted_line_ids),
            )
            .order_by(Line.name)
        )
        .scalars()
        .all()
    )
