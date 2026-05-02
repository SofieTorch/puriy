"""Accept or reject route edges based on community vote tallies."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from database import EdgeStatus, RouteEdge, RouteStatus, Route


def execute(
    db: Session,
    *,
    approval_threshold: float = 0.6,
    min_votes: int = 3,
) -> dict:
    # Find PENDING edges on non-superseded routes with enough votes
    edges = db.execute(
        select(RouteEdge)
        .join(Route, RouteEdge.route_id == Route.id)
        .where(
            RouteEdge.status == EdgeStatus.PENDING,
            Route.status != RouteStatus.SUPERSEDED,
            (RouteEdge.votes_for + RouteEdge.votes_against) >= min_votes,
        )
    ).scalars().all()

    confirmed = 0
    rejected = 0
    insufficient = 0

    for edge in edges:
        total = edge.votes_for + edge.votes_against
        if total < min_votes:
            insufficient += 1
            continue

        ratio = edge.votes_for / total
        if ratio >= approval_threshold:
            edge.status = EdgeStatus.CONFIRMED
            edge.confirmed_at = datetime.now(timezone.utc)
            confirmed += 1
        else:
            # Keep as PENDING but track that it was evaluated
            # (EdgeStatus doesn't have REJECTED — edges stay PENDING for re-voting)
            rejected += 1

    db.commit()

    return {
        "edges_checked": len(edges),
        "edges_confirmed": confirmed,
        "edges_rejected": rejected,
        "edges_insufficient_votes": insufficient,
    }
