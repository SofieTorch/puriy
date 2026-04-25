"""Migrate EdgeVotes from a superseded route to a new route version."""

from uuid import UUID

from sqlalchemy import update
from sqlalchemy.orm import Session

from database.models import EdgeVote, RouteEdge


def migrate_votes_to_new_route(
    db: Session,
    old_route_id: UUID,
    new_route_id: UUID,
) -> int:
    """Carry forward votes from old route edges to matching new route edges.

    Matching is based on (valhalla_edge_id, forward). For each match:
    - Copies votes_for/votes_against to the new edge
    - Re-points EdgeVote records from old edge → new edge

    Returns the number of EdgeVote records migrated.
    """
    old_edges = (
        db.query(RouteEdge)
        .filter(RouteEdge.route_id == old_route_id)
        .all()
    )
    new_edges = (
        db.query(RouteEdge)
        .filter(RouteEdge.route_id == new_route_id)
        .all()
    )

    # Build lookup: (valhalla_edge_id, forward) → old edge
    old_by_key: dict[tuple[int | None, bool], RouteEdge] = {}
    for edge in old_edges:
        if edge.valhalla_edge_id is not None:
            old_by_key[(edge.valhalla_edge_id, edge.forward)] = edge

    migrated = 0
    for new_edge in new_edges:
        if new_edge.valhalla_edge_id is None:
            continue

        key = (new_edge.valhalla_edge_id, new_edge.forward)
        old_edge = old_by_key.get(key)
        if not old_edge:
            continue

        # Copy vote counts
        new_edge.votes_for = old_edge.votes_for
        new_edge.votes_against = old_edge.votes_against

        # Re-point EdgeVote records
        result = db.execute(
            update(EdgeVote)
            .where(EdgeVote.edge_id == old_edge.id)
            .values(edge_id=new_edge.id)
        )
        migrated += result.rowcount

    db.flush()
    return migrated
