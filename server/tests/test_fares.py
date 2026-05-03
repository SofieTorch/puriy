"""Tests for the /fares endpoints — focused on the changes from #4
(FareSource tagging and common_amounts in LineFareRead)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from database.models.fare import FareReport, FareSource
from database.models.line import Line, LineStatus, LineType


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def micro_line(db: Session) -> Line:
    line = Line(name="Línea 130", status=LineStatus.APPROVED, line_type=LineType.MICRO)
    db.add(line)
    db.commit()
    db.refresh(line)
    return line


def _seed_fare(
    db: Session,
    line_id,
    amount: float,
    *,
    device_id: str = "test-device-abc",
    source: FareSource = FareSource.REGISTRATION,
) -> None:
    db.add(FareReport(
        line_id=line_id,
        device_id=device_id,
        amount_bob=amount,
        boarding_latitude=-17.39, boarding_longitude=-66.16,
        alighting_latitude=-17.40, alighting_longitude=-66.17,
        source=source,
    ))


# ------------------------------------------------------------------
# common_amounts in LineFareRead
# ------------------------------------------------------------------

def test_line_fares_returns_common_amounts_ordered_by_frequency(
    client: TestClient, db: Session, micro_line: Line,
) -> None:
    # 3 reports of 2.5, 2 reports of 3.0, 1 report of 5.0
    for _ in range(3):
        _seed_fare(db, micro_line.id, 2.5)
    for _ in range(2):
        _seed_fare(db, micro_line.id, 3.0)
    _seed_fare(db, micro_line.id, 5.0)
    db.commit()

    resp = client.get(f"/fares/lines/{micro_line.id}")
    assert resp.status_code == 200
    body = resp.json()
    amounts = body["common_amounts"]
    assert len(amounts) == 3
    # Most-frequent first.
    assert amounts[0]["amount_bob"] == 2.5
    assert amounts[0]["report_count"] == 3
    assert amounts[1]["amount_bob"] == 3.0
    assert amounts[1]["report_count"] == 2
    assert amounts[2]["amount_bob"] == 5.0
    assert amounts[2]["report_count"] == 1


def test_line_fares_no_reports_returns_empty_amounts(
    client: TestClient, micro_line: Line,
) -> None:
    resp = client.get(f"/fares/lines/{micro_line.id}")
    assert resp.status_code == 200
    assert resp.json()["common_amounts"] == []


def test_line_fares_caps_common_amounts_at_four(
    client: TestClient, db: Session, micro_line: Line,
) -> None:
    """The endpoint returns at most 4 distinct amounts."""
    for amount in [1.5, 2.0, 2.5, 3.0, 3.5, 4.0]:
        _seed_fare(db, micro_line.id, amount)
    db.commit()
    resp = client.get(f"/fares/lines/{micro_line.id}")
    assert len(resp.json()["common_amounts"]) == 4


# ------------------------------------------------------------------
# source tagging on POST /fares/reports
# ------------------------------------------------------------------

def test_fare_report_defaults_to_registration(
    client: TestClient, db: Session, micro_line: Line,
) -> None:
    resp = client.post("/fares/reports", json={
        "line_id": str(micro_line.id),
        "device_id": "test-device-abc",
        "amount_bob": 2.5,
        "boarding_latitude": -17.39,
        "boarding_longitude": -66.16,
        "alighting_latitude": -17.40,
        "alighting_longitude": -66.17,
    })
    assert resp.status_code == 201
    assert resp.json()["source"] == "registration"


def test_fare_report_can_be_marked_as_confirmation(
    client: TestClient, db: Session, micro_line: Line,
) -> None:
    resp = client.post("/fares/reports", json={
        "line_id": str(micro_line.id),
        "device_id": "test-device-abc",
        "amount_bob": 2.5,
        "boarding_latitude": -17.39,
        "boarding_longitude": -66.16,
        "alighting_latitude": -17.40,
        "alighting_longitude": -66.17,
        "source": "confirmation",
    })
    assert resp.status_code == 201
    assert resp.json()["source"] == "confirmation"


# ------------------------------------------------------------------
# /fares/zones/resolve — preview endpoint (CU-08)
# ------------------------------------------------------------------

def test_resolve_zones_returns_names_for_known_points(
    client: TestClient, db: Session,
) -> None:
    """A point inside a defined `FareZone.boundary` resolves to its name;
    a point outside any zone resolves to `null`. This is what the mobile
    fare prompt uses to show identified municipalities before submit."""
    from geoalchemy2.shape import from_shape
    from shapely.geometry import Polygon

    from database.models.fare import FareZone

    # A small square covering Plaza Colón (~ -17.393, -66.157).
    cocha_polygon = Polygon([
        (-66.20, -17.40), (-66.10, -17.40),
        (-66.10, -17.35), (-66.20, -17.35),
        (-66.20, -17.40),
    ])
    db.add(FareZone(
        name="Cochabamba",
        boundary=from_shape(cocha_polygon, srid=4326),
    ))
    db.commit()

    resp = client.post("/fares/zones/resolve", json={
        "boarding_latitude": -17.39, "boarding_longitude": -66.16,   # in
        "alighting_latitude": -17.50, "alighting_longitude": -66.30, # out
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"boarding_zone": "Cochabamba", "alighting_zone": None}


def test_resolve_zones_validates_input(client: TestClient) -> None:
    """Out-of-range lat/lon returns 422."""
    resp = client.post("/fares/zones/resolve", json={
        "boarding_latitude": -91, "boarding_longitude": 0,
        "alighting_latitude": 0, "alighting_longitude": 0,
    })
    assert resp.status_code == 422
