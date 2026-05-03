"""Tests for the `resolve_routes` step (Route PENDING → CONFIRMED
promotion based on edge-confirmation quorum).

This step closes the gap where Routes were never promoted out of
PENDING in production, so the default `find_lines_nearby` filter
(`status=CONFIRMED`) hid every reconstructed route from users.
"""

import pytest
from geoalchemy2.shape import from_shape
from shapely.geometry import LineString
from sqlalchemy.orm import Session

from database import (
    EdgeStatus,
    Line,
    LineStatus,
    Route,
    RouteEdge,
    RouteSource,
    RouteStatus,
)
from pipeline.steps.resolve_routes import execute


COORDS = [[-66.157, -17.393], [-66.156, -17.393], [-66.155, -17.393]]


@pytest.fixture
def line(db: Session) -> Line:
    line = Line(name="L-resolve", status=LineStatus.APPROVED)
    db.add(line)
    db.commit()
    db.refresh(line)
    return line


def _seed_route(
    db: Session, line: Line, *,
    edge_statuses: list[EdgeStatus],
    status: RouteStatus = RouteStatus.PENDING,
    ramal_label: str = "main",
    version: int = 1,
) -> Route:
    """Create a Route with one RouteEdge per entry in `edge_statuses`."""
    route = Route(
        line_id=line.id, version=version, ramal_label=ramal_label,
        source=RouteSource.COMPUTED, status=status,
        trip_count=5, fragment_index=0, fragment_count=1,
    )
    db.add(route)
    db.flush()
    for i, edge_status in enumerate(edge_statuses):
        db.add(RouteEdge(
            route_id=route.id, sequence=i, valhalla_edge_id=None, forward=True,
            path=from_shape(LineString(COORDS), srid=4326),
            confidence=1.0, status=edge_status,
        ))
    db.commit()
    db.refresh(route)
    return route


# ------------------------------------------------------------------
# Basic promotion
# ------------------------------------------------------------------

def test_promotes_route_when_all_edges_confirmed(
    db: Session, line: Line,
) -> None:
    route = _seed_route(db, line, edge_statuses=[EdgeStatus.CONFIRMED] * 3)

    result = execute(db)

    assert result["routes_promoted"] == 1
    db.refresh(route)
    assert route.status == RouteStatus.CONFIRMED
    assert route.last_compared_at is not None


def test_promotes_at_default_80pct_threshold(
    db: Session, line: Line,
) -> None:
    """4/5 edges confirmed = 80%, exactly at the default threshold."""
    route = _seed_route(db, line, edge_statuses=[
        EdgeStatus.CONFIRMED, EdgeStatus.CONFIRMED, EdgeStatus.CONFIRMED,
        EdgeStatus.CONFIRMED, EdgeStatus.PENDING,
    ])
    result = execute(db)
    assert result["routes_promoted"] == 1
    db.refresh(route)
    assert route.status == RouteStatus.CONFIRMED


def test_does_not_promote_below_threshold(
    db: Session, line: Line,
) -> None:
    """3/5 edges = 60%, below the 80% default → stays PENDING."""
    route = _seed_route(db, line, edge_statuses=[
        EdgeStatus.CONFIRMED, EdgeStatus.CONFIRMED, EdgeStatus.CONFIRMED,
        EdgeStatus.PENDING, EdgeStatus.PENDING,
    ])
    result = execute(db)
    assert result["routes_promoted"] == 0
    assert result["routes_insufficient"] == 1
    db.refresh(route)
    assert route.status == RouteStatus.PENDING


def test_promotes_single_edge_fallback_route(
    db: Session, line: Line,
) -> None:
    """Single-edge routes (Valhalla-unavailable fallback) confirm with
    one vote at default `min_confirmed_edges=1`. Without this, fallback
    routes would never become CONFIRMED."""
    route = _seed_route(db, line, edge_statuses=[EdgeStatus.CONFIRMED])
    result = execute(db)
    assert result["routes_promoted"] == 1
    db.refresh(route)
    assert route.status == RouteStatus.CONFIRMED


# ------------------------------------------------------------------
# Edge cases
# ------------------------------------------------------------------

def test_skips_routes_with_no_edges(
    db: Session, line: Line,
) -> None:
    route = Route(
        line_id=line.id, version=1, ramal_label="main",
        source=RouteSource.COMPUTED, status=RouteStatus.PENDING,
        trip_count=0, fragment_index=0, fragment_count=1,
    )
    db.add(route)
    db.commit()
    db.refresh(route)

    result = execute(db)
    assert result["routes_without_edges"] == 1
    assert result["routes_promoted"] == 0
    db.refresh(route)
    assert route.status == RouteStatus.PENDING


def test_skips_already_confirmed_routes(
    db: Session, line: Line,
) -> None:
    """CONFIRMED routes are excluded from the candidate query — no
    re-evaluation, no double-promotion timestamp churn."""
    route = _seed_route(
        db, line, edge_statuses=[EdgeStatus.CONFIRMED] * 3,
        status=RouteStatus.CONFIRMED,
    )
    original_compared_at = route.last_compared_at

    result = execute(db)
    assert result["routes_promoted"] == 0
    db.refresh(route)
    assert route.last_compared_at == original_compared_at


def test_skips_superseded_routes(
    db: Session, line: Line,
) -> None:
    route = _seed_route(
        db, line, edge_statuses=[EdgeStatus.CONFIRMED] * 3,
        status=RouteStatus.SUPERSEDED,
    )
    result = execute(db)
    assert result["routes_promoted"] == 0
    db.refresh(route)
    assert route.status == RouteStatus.SUPERSEDED


def test_min_confirmed_edges_floor_blocks_promotion(
    db: Session, line: Line,
) -> None:
    """With `min_confirmed_edges=3`, a route with only 1 confirmed
    edge stays PENDING even if that's 100% of its edges."""
    route = _seed_route(db, line, edge_statuses=[EdgeStatus.CONFIRMED])
    result = execute(db, min_confirmed_edges=3)
    assert result["routes_promoted"] == 0
    db.refresh(route)
    assert route.status == RouteStatus.PENDING


def test_threshold_is_configurable(
    db: Session, line: Line,
) -> None:
    """A 60%-confirmed route doesn't promote at default 0.8, but does
    at 0.5."""
    route = _seed_route(db, line, edge_statuses=[
        EdgeStatus.CONFIRMED, EdgeStatus.CONFIRMED, EdgeStatus.CONFIRMED,
        EdgeStatus.PENDING, EdgeStatus.PENDING,
    ])

    result_strict = execute(db)
    assert result_strict["routes_promoted"] == 0
    db.refresh(route)
    assert route.status == RouteStatus.PENDING

    result_loose = execute(db, approval_threshold=0.5)
    assert result_loose["routes_promoted"] == 1
    db.refresh(route)
    assert route.status == RouteStatus.CONFIRMED


def test_multi_ramal_routes_promote_independently(
    db: Session, line: Line,
) -> None:
    """Each ramal's Route is its own promotion candidate — main can
    confirm while r2 stays PENDING."""
    main = _seed_route(
        db, line, edge_statuses=[EdgeStatus.CONFIRMED] * 3,
        ramal_label="main",
    )
    r2 = _seed_route(
        db, line, edge_statuses=[EdgeStatus.PENDING] * 3,
        ramal_label="r2",
    )

    result = execute(db)
    assert result["routes_promoted"] == 1

    db.refresh(main)
    db.refresh(r2)
    assert main.status == RouteStatus.CONFIRMED
    assert r2.status == RouteStatus.PENDING
