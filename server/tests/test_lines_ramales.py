"""Server tests for ramal-aware API responses (gap #7 / RF-07).

Covers:
- `GET /lines/nearby` returns one `RamalSummary` per active ramal,
  with `endpoint_zones` and `street_summary` populated.
- `GET /lines/{id}/route` returns one GeoJSON Feature per active
  ramal — multi-ramal lines are no longer collapsed to a single
  feature.
- The internal `ramal_label` is included in the GeoJSON properties
  for client-side stability (caching, vote attribution) but the
  user-facing identity is endpoint zones + street summary.
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from geoalchemy2.shape import from_shape
from shapely.geometry import LineString
from sqlalchemy.orm import Session

from database import (
    Line,
    LineStatus,
    Route,
    RouteEdge,
    RouteSource,
    RouteStatus,
)


# Two distinct ramales of "line 230" sharing Beijing/Sacaba.
RAMAL_A_COORDS = [[-66.170, -17.390], [-66.160, -17.390], [-66.150, -17.390]]
RAMAL_B_COORDS = [[-66.170, -17.390], [-66.160, -17.395], [-66.150, -17.390]]


@pytest.fixture
def line_with_one_ramal(db: Session, approved_line: Line) -> Line:
    """Approved line with a single CONFIRMED ramal Route."""
    _seed_route(
        db, approved_line.id, RAMAL_A_COORDS,
        ramal_label="main",
        status=RouteStatus.CONFIRMED,
        street_summary=["Av. América", "Av. Beijing"],
        endpoint_zones=["Beijing", "Sacaba"],
    )
    return approved_line


@pytest.fixture
def line_with_two_ramales(db: Session, approved_line: Line) -> Line:
    """Approved line with two CONFIRMED ramales (main + r2)."""
    _seed_route(
        db, approved_line.id, RAMAL_A_COORDS,
        ramal_label="main",
        status=RouteStatus.CONFIRMED,
        street_summary=["Av. América"],
        endpoint_zones=["Beijing", "Sacaba"],
    )
    _seed_route(
        db, approved_line.id, RAMAL_B_COORDS,
        ramal_label="r2",
        status=RouteStatus.CONFIRMED,
        street_summary=["Av. Simón Lopez", "Av. Pacata"],
        endpoint_zones=["Beijing", "Sacaba"],
    )
    return approved_line


def _seed_route(
    db: Session,
    line_id: Any,
    coords: list[list[float]],
    *,
    ramal_label: str,
    status: RouteStatus,
    street_summary: list[str] | None = None,
    endpoint_zones: list[str | None] | None = None,
    version: int = 1,
) -> Route:
    route = Route(
        line_id=line_id,
        version=version,
        ramal_label=ramal_label,
        source=RouteSource.COMPUTED,
        status=status,
        trip_count=5,
        fragment_index=0,
        fragment_count=1,
        street_summary=street_summary,
        endpoint_zones=endpoint_zones,
    )
    db.add(route)
    db.flush()
    db.add(RouteEdge(
        route_id=route.id,
        sequence=0,
        valhalla_edge_id=None,
        forward=True,
        path=from_shape(LineString(coords), srid=4326),
        confidence=1.0,
    ))
    db.commit()
    db.refresh(route)
    return route


# ------------------------------------------------------------------
# GET /lines/nearby
# ------------------------------------------------------------------

def test_nearby_includes_single_ramal_summary(
    client: TestClient, line_with_one_ramal: Line,
) -> None:
    """A single-ramal line returns `ramales` as a 1-element list with
    its endpoint zones + street summary populated."""
    resp = client.get(
        "/lines/nearby/",
        params={"longitude": -66.160, "latitude": -17.390, "radius_meters": 500},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    line = data[0]
    assert "ramales" in line
    assert len(line["ramales"]) == 1
    ramal = line["ramales"][0]
    assert ramal["endpoint_zones"] == ["Beijing", "Sacaba"]
    assert ramal["street_summary"] == ["Av. América", "Av. Beijing"]
    assert "route_id" in ramal


def test_nearby_returns_one_summary_per_active_ramal(
    client: TestClient, line_with_two_ramales: Line,
) -> None:
    """A two-ramal line returns both ramales — each with its own
    `street_summary`."""
    resp = client.get(
        "/lines/nearby/",
        params={"longitude": -66.160, "latitude": -17.390, "radius_meters": 1500},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    ramales = data[0]["ramales"]
    assert len(ramales) == 2

    # Routes ordered by ramal_label alphabetically → main, r2.
    summaries_by_streets = {
        tuple(r["street_summary"]): r for r in ramales
    }
    assert ("Av. América",) in summaries_by_streets
    assert ("Av. Simón Lopez", "Av. Pacata") in summaries_by_streets


def test_nearby_omits_superseded_ramales(
    client: TestClient, db: Session, approved_line: Line,
) -> None:
    """SUPERSEDED routes are filtered out of `ramales`."""
    _seed_route(
        db, approved_line.id, RAMAL_A_COORDS,
        ramal_label="main",
        status=RouteStatus.CONFIRMED,
        street_summary=["Av. América"],
        endpoint_zones=["Beijing", "Sacaba"],
    )
    _seed_route(
        db, approved_line.id, RAMAL_B_COORDS,
        ramal_label="r2",
        status=RouteStatus.SUPERSEDED,
        street_summary=["Old streets"],
    )
    resp = client.get(
        "/lines/nearby/",
        params={"longitude": -66.160, "latitude": -17.390, "radius_meters": 500},
    )
    assert resp.status_code == 200
    ramales = resp.json()[0]["ramales"]
    assert len(ramales) == 1
    assert ramales[0]["street_summary"] == ["Av. América"]


# ------------------------------------------------------------------
# GET /lines/{id}/route
# ------------------------------------------------------------------

def test_get_line_route_returns_one_feature_per_ramal(
    client: TestClient, line_with_two_ramales: Line,
) -> None:
    """Multi-ramal line → FeatureCollection with one Feature per ramal."""
    resp = client.get(f"/lines/{line_with_two_ramales.id}/route")
    assert resp.status_code == 200
    data = resp.json()
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) == 2

    by_label = {
        f["properties"]["ramal_label"]: f for f in data["features"]
    }
    assert {"main", "r2"} == set(by_label.keys())
    main = by_label["main"]
    assert main["properties"]["street_summary"] == ["Av. América"]
    assert main["properties"]["endpoint_zones"] == ["Beijing", "Sacaba"]
    assert main["geometry"]["type"] == "LineString"


def test_get_line_route_includes_route_id_for_client_stability(
    client: TestClient, line_with_one_ramal: Line,
) -> None:
    """`route_id` in properties lets the mobile client cache + attribute
    votes per ramal without ever rendering `ramal_label` to users."""
    resp = client.get(f"/lines/{line_with_one_ramal.id}/route")
    assert resp.status_code == 200
    feature = resp.json()["features"][0]
    assert "route_id" in feature["properties"]
    assert feature["properties"]["ramal_label"] == "main"


def test_get_line_route_404_when_no_active_route(
    client: TestClient, approved_line: Line,
) -> None:
    """No active routes → 404, not an empty FeatureCollection."""
    resp = client.get(f"/lines/{approved_line.id}/route")
    assert resp.status_code == 404
