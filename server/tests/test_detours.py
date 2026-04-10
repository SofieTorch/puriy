"""Tests for the detours API endpoints."""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from geoalchemy2.shape import from_shape
from shapely.geometry import LineString
from sqlalchemy import func
from sqlalchemy.orm import Session

from database.models.detour import Detour, DetourStatus
from database.models.line import Line, LineStatus
from database.models.trip import TripSession, TripSessionPoint, SessionStatus


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

SAMPLE_PATH = LineString([(-66.157, -17.393), (-66.155, -17.395)])


def _make_completed_session(db: Session, line: Line) -> TripSession:
    """Create and flush a completed TripSession for the given line."""
    session = TripSession(
        line_id=line.id,
        status=SessionStatus.COMPLETED,
        ended_at=datetime.utcnow(),
    )
    db.add(session)
    db.flush()
    return session


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def line_for_detour(db: Session) -> Line:
    """Create an approved line for detour tests."""
    line = Line(name="Detour Test Line", status=LineStatus.APPROVED)
    db.add(line)
    db.commit()
    db.refresh(line)
    return line


@pytest.fixture
def second_line(db: Session) -> Line:
    """Create a second approved line for filtering tests."""
    line = Line(name="Second Detour Line", status=LineStatus.APPROVED)
    db.add(line)
    db.commit()
    db.refresh(line)
    return line


@pytest.fixture
def session_with_points(db: Session, line_for_detour: Line) -> TripSession:
    """Create an in-progress session with GPS points so computed_path is generated."""
    session = TripSession(
        line_id=line_for_detour.id,
        status=SessionStatus.IN_PROGRESS,
    )
    db.add(session)
    db.flush()

    coords = [(-66.157 + i * 0.001, -17.393 + i * 0.001) for i in range(5)]
    for i, (lon, lat) in enumerate(coords):
        point = TripSessionPoint(
            session_id=session.id,
            timestamp=datetime.utcnow() + timedelta(seconds=i),
            latitude=lat,
            longitude=lon,
            point=func.ST_GeomFromEWKT(f"SRID=4326;POINT({lon} {lat})"),
        )
        db.add(point)

    db.commit()
    db.refresh(session)
    return session


@pytest.fixture
def active_detour(db: Session, line_for_detour: Line) -> Detour:
    """Create an active detour."""
    session = _make_completed_session(db, line_for_detour)

    detour = Detour(
        line_id=line_for_detour.id,
        session_id=session.id,
        status=DetourStatus.ACTIVE,
        reason="construction",
        description="Road works on main avenue",
        path=from_shape(SAMPLE_PATH, srid=4326),
    )
    db.add(detour)
    db.commit()
    db.refresh(detour)
    return detour


@pytest.fixture
def expired_detour(db: Session, line_for_detour: Line) -> Detour:
    """Create an expired detour."""
    session = _make_completed_session(db, line_for_detour)

    detour = Detour(
        line_id=line_for_detour.id,
        session_id=session.id,
        status=DetourStatus.EXPIRED,
        reason="protest",
        path=from_shape(
            LineString([(-66.160, -17.390), (-66.158, -17.392)]), srid=4326
        ),
    )
    db.add(detour)
    db.commit()
    db.refresh(detour)
    return detour


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------


class TestCreateDetourViaRecording:
    """Tests for detour creation through POST /recordings/{id}/end."""

    def test_end_recording_with_detour_creates_detour(
        self,
        client: TestClient,
        db: Session,
        session_with_points: TripSession,
        line_for_detour: Line,
    ):
        """Ending a session with is_detour=True should create a Detour record."""
        response = client.post(
            f"/recordings/{session_with_points.id}/end",
            json={
                "line_id": str(line_for_detour.id),
                "is_detour": True,
                "detour_reason": "construction",
                "detour_description": "Bridge closed",
            },
        )

        assert response.status_code == 200

        detour = (
            db.query(Detour)
            .filter(Detour.session_id == session_with_points.id)
            .first()
        )
        assert detour is not None
        assert detour.line_id == line_for_detour.id
        assert detour.reason == "construction"
        assert detour.description == "Bridge closed"
        assert detour.status == DetourStatus.ACTIVE
        assert detour.path is not None

    def test_end_recording_without_detour_no_detour_created(
        self,
        client: TestClient,
        db: Session,
        session_with_points: TripSession,
        line_for_detour: Line,
    ):
        """Ending a session without is_detour should not create a Detour."""
        response = client.post(
            f"/recordings/{session_with_points.id}/end",
            json={"line_id": str(line_for_detour.id)},
        )

        assert response.status_code == 200

        detour = (
            db.query(Detour)
            .filter(Detour.session_id == session_with_points.id)
            .first()
        )
        assert detour is None


class TestListActiveDetours:
    """Tests for GET /detours/active."""

    def test_list_active_detours(
        self, client: TestClient, active_detour: Detour
    ):
        """Should return active detours."""
        response = client.get("/detours/active")

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        ids = [d["id"] for d in data]
        assert str(active_detour.id) in ids

    def test_filter_by_line_id(
        self,
        client: TestClient,
        db: Session,
        active_detour: Detour,
        second_line: Line,
    ):
        """Should filter detours by line_id."""
        session2 = _make_completed_session(db, second_line)

        detour2 = Detour(
            line_id=second_line.id,
            session_id=session2.id,
            status=DetourStatus.ACTIVE,
            path=from_shape(SAMPLE_PATH, srid=4326),
        )
        db.add(detour2)
        db.commit()

        response = client.get(
            "/detours/active", params={"line_id": str(second_line.id)}
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["line_id"] == str(second_line.id)

    def test_expired_not_returned(
        self, client: TestClient, expired_detour: Detour
    ):
        """Expired detours should not appear in active list."""
        response = client.get("/detours/active")

        assert response.status_code == 200
        data = response.json()
        ids = [d["id"] for d in data]
        assert str(expired_detour.id) not in ids


class TestGetActiveDetourForLine:
    """Tests for GET /detours/active/{line_id}."""

    def test_returns_active_detour(
        self,
        client: TestClient,
        active_detour: Detour,
        line_for_detour: Line,
    ):
        """Should return 200 with detour data for a line with an active detour."""
        response = client.get(f"/detours/active/{line_for_detour.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(active_detour.id)
        assert data["line_id"] == str(line_for_detour.id)
        assert data["reason"] == "construction"
        assert data["confirmed_count"] == 1

    def test_404_when_no_detour(self, client: TestClient):
        """Should return 404 when line has no active detour."""
        response = client.get(f"/detours/active/{uuid4()}")

        assert response.status_code == 404


class TestConfirmDetour:
    """Tests for POST /detours/{id}/confirm."""

    def test_confirm_resets_timestamp(
        self, client: TestClient, db: Session, active_detour: Detour
    ):
        """Confirming should update last_confirmed_at and increment count."""
        original_confirmed_at = active_detour.last_confirmed_at
        original_count = active_detour.confirmed_count

        response = client.post(f"/detours/{active_detour.id}/confirm")

        assert response.status_code == 200
        data = response.json()
        assert data["confirmed_count"] == original_count + 1

        db.refresh(active_detour)
        assert active_detour.last_confirmed_at >= original_confirmed_at

    def test_confirm_expired_returns_404(
        self, client: TestClient, expired_detour: Detour
    ):
        """Should return 404 when trying to confirm an expired detour."""
        response = client.post(f"/detours/{expired_detour.id}/confirm")

        assert response.status_code == 404


class TestCleanup:
    """Tests for POST /detours/cleanup."""

    def test_cleanup_expires_old_detours(
        self, client: TestClient, db: Session, line_for_detour: Line
    ):
        """Detours not confirmed for 8 days should be expired by cleanup."""
        session = _make_completed_session(db, line_for_detour)

        old_detour = Detour(
            line_id=line_for_detour.id,
            session_id=session.id,
            status=DetourStatus.ACTIVE,
            last_confirmed_at=datetime.utcnow() - timedelta(days=8),
            path=from_shape(SAMPLE_PATH, srid=4326),
        )
        db.add(old_detour)
        db.commit()
        db.refresh(old_detour)

        response = client.post("/detours/cleanup")

        assert response.status_code == 200
        data = response.json()
        assert data["expired_count"] >= 1

        db.refresh(old_detour)
        assert old_detour.status == DetourStatus.EXPIRED

    def test_cleanup_keeps_recent_detours(
        self, client: TestClient, db: Session, active_detour: Detour
    ):
        """Recently confirmed detours should remain active after cleanup."""
        response = client.post("/detours/cleanup")

        assert response.status_code == 200

        db.refresh(active_detour)
        assert active_detour.status == DetourStatus.ACTIVE
