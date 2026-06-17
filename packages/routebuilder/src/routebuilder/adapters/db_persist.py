"""Persist a ConsensusRoute as Route + RouteEdge rows.

Edges carry the same (valhalla_edge_id, forward) keys as the old
strategy's output, so geodata.migrate_votes keeps working when a new
version supersedes an old route. This adapter does NOT wire into
packages/pipeline — swapping the pipeline over is a separate task.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from database.models import Route, RouteEdge, RouteSource, RouteStatus
from geoalchemy2.shape import from_shape
from shapely.geometry import LineString
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..types import ConsensusRoute

STRATEGY_KEY = "routebuilder_v1"


def persist_consensus(
    db: Session,
    line_id: UUID,
    route: ConsensusRoute,
    *,
    supersede: bool = True,
) -> Route:
    """Create a PENDING Route (+edges) for a line/ramal.

    With supersede=True, any currently active route for the same
    (line, ramal) is marked SUPERSEDED and the new version continues
    its version chain. Vote migration is intentionally left to the
    caller (geodata.migrate_votes.migrate_votes_to_new_route).
    """
    previous = (
        db.execute(
            select(Route).where(
                Route.line_id == line_id,
                Route.ramal_label == route.ramal_label,
                Route.status != RouteStatus.SUPERSEDED,
            )
        )
        .scalars()
        .first()
    )

    version = 1
    if previous is not None:
        version = previous.version + 1
        if supersede:
            previous.status = RouteStatus.SUPERSEDED

    fragment_count = route.diagnostics.get("fragment_count", 1)
    fragment_index = route.diagnostics.get("fragment_index", 0)

    row = Route(
        line_id=line_id,
        version=version,
        source=RouteSource.COMPUTED,
        status=RouteStatus.PENDING,
        trip_count=route.trace_count,
        strategy_key=STRATEGY_KEY,
        ramal_label=route.ramal_label,
        fragment_index=fragment_index,
        fragment_count=fragment_count,
        created_at=datetime.now(UTC),
    )
    db.add(row)
    db.flush()

    for sequence, ce in enumerate(route.edges):
        path = None
        if len(ce.geometry) >= 2:
            path = from_shape(LineString(ce.geometry), srid=4326)
        db.add(RouteEdge(
            route_id=row.id,
            sequence=sequence,
            valhalla_edge_id=ce.edge.edge_id,
            forward=ce.edge.forward,
            path=path,
            confidence=ce.confidence,
        ))
    db.flush()
    return row
