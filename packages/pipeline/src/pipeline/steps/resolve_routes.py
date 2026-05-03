"""Promote Routes from PENDING to CONFIRMED once a quorum of their edges
are confirmed by community votes.

Without this step, no `Route` ever leaves `PENDING` in production —
`_save_reconstruction` always writes new Routes as PENDING and
`resolve_edge_votes` only touches individual `RouteEdge` rows. The
default `find_lines_nearby` filter (`status=CONFIRMED`) would then
hide every reconstructed route from users with `include_pending=False`.

This step fills that gap: after `resolve_edge_votes` has flipped
individual edges, it walks each non-superseded Route and promotes it
when the fraction of CONFIRMED edges crosses `approval_threshold`
(default 80 %). A route with no edges, or one whose CONFIRMED count
is below `min_confirmed_edges`, is left alone.
"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from database import EdgeStatus, Route, RouteStatus


def execute(
    db: Session,
    *,
    approval_threshold: float = 0.8,
    min_confirmed_edges: int = 1,
) -> dict:
    """Promote PENDING routes to CONFIRMED based on per-edge confirmation.

    Parameters
    ----------
    approval_threshold
        Fraction of edges that must be `CONFIRMED` for the Route to
        be promoted. 0.8 means "at least 80 % of edges confirmed".
    min_confirmed_edges
        Floor on the absolute number of confirmed edges. Prevents
        single-edge fallback routes (Valhalla-unavailable case) from
        being promoted on a single vote when that's not desired.
    """
    routes = db.execute(
        select(Route)
        .where(
            Route.status == RouteStatus.PENDING,
        )
    ).scalars().all()

    promoted = 0
    insufficient = 0
    no_edges = 0

    for route in routes:
        if not route.edges:
            no_edges += 1
            continue

        confirmed = sum(1 for e in route.edges if e.status == EdgeStatus.CONFIRMED)
        if confirmed < min_confirmed_edges:
            insufficient += 1
            continue

        ratio = confirmed / len(route.edges)
        if ratio < approval_threshold:
            insufficient += 1
            continue

        route.status = RouteStatus.CONFIRMED
        # `confirmed_at` lives on RouteEdge, not Route — track route-level
        # promotion via `last_compared_at` (it's the most recent moment
        # the route's status was re-evaluated, which is what the field
        # was added for in #6).
        route.last_compared_at = datetime.now(timezone.utc)
        promoted += 1

    db.commit()

    return {
        "routes_checked": len(routes),
        "routes_promoted": promoted,
        "routes_insufficient": insufficient,
        "routes_without_edges": no_edges,
        "approval_threshold": approval_threshold,
        "min_confirmed_edges": min_confirmed_edges,
    }
