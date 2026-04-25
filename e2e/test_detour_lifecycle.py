"""Detour lifecycle tests -- confidence decay, expiry, and confirmation reset."""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest
import httpx

BASE_URL = os.getenv("TEST_SERVER_URL", "http://localhost:8001")

sys.path.insert(0, str(Path(__file__).parent.parent / "server"))
sys.path.insert(0, str(Path(__file__).parent.parent / "packages" / "database" / "src"))


@pytest.fixture
def db():
    from database.connection import SessionLocal

    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def active_detour_id(db):
    """Get the ID of the active detour from seed data."""
    from database.models.detour import Detour, DetourStatus
    from sqlalchemy import select

    db.expire_all()
    detour = (
        db.execute(select(Detour).where(Detour.status == DetourStatus.ACTIVE))
        .scalars()
        .first()
    )
    assert detour is not None, "No active detour found -- run seed.py first"
    return detour.id, detour.line_id


class TestDetourConfidenceDecay:
    def test_fresh_detour_100_percent(self, db, active_detour_id):
        detour_id, line_id = active_detour_id
        from database.models.detour import Detour

        detour = db.get(Detour, detour_id)
        detour.last_confirmed_at = datetime.utcnow()
        db.commit()

        resp = httpx.get(f"{BASE_URL}/detours/active/{line_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["days_since_confirmed"] == 0
        assert data["confidence_pct"] == 100

    def test_aging_detour_day3(self, db, active_detour_id):
        detour_id, line_id = active_detour_id
        from database.models.detour import Detour

        detour = db.get(Detour, detour_id)
        detour.last_confirmed_at = datetime.utcnow() - timedelta(days=3)
        db.commit()

        resp = httpx.get(f"{BASE_URL}/detours/active/{line_id}")
        data = resp.json()
        assert data["days_since_confirmed"] == 3
        assert 50 <= data["confidence_pct"] <= 60  # ~57%

    def test_near_expiry_day6(self, db, active_detour_id):
        detour_id, line_id = active_detour_id
        from database.models.detour import Detour

        detour = db.get(Detour, detour_id)
        detour.last_confirmed_at = datetime.utcnow() - timedelta(days=6)
        db.commit()

        resp = httpx.get(f"{BASE_URL}/detours/active/{line_id}")
        data = resp.json()
        assert data["days_since_confirmed"] == 6
        assert data["confidence_pct"] <= 20

    def test_cleanup_expires_old_detour(self, db, active_detour_id):
        detour_id, line_id = active_detour_id
        from database.models.detour import Detour, DetourStatus

        detour = db.get(Detour, detour_id)
        detour.last_confirmed_at = datetime.utcnow() - timedelta(days=8)
        db.commit()

        resp = httpx.post(f"{BASE_URL}/detours/cleanup")
        assert resp.status_code == 200
        assert resp.json()["expired_count"] >= 1

        resp = httpx.get(f"{BASE_URL}/detours/active/{line_id}")
        assert resp.status_code == 404

        # Re-activate for subsequent tests
        db.expire_all()
        detour = db.get(Detour, detour_id)
        detour.status = DetourStatus.ACTIVE
        detour.last_confirmed_at = datetime.utcnow()
        db.commit()

    def test_confirmation_resets_confidence(self, db, active_detour_id):
        detour_id, line_id = active_detour_id
        from database.models.detour import Detour, DetourStatus

        detour = db.get(Detour, detour_id)
        detour.last_confirmed_at = datetime.utcnow() - timedelta(days=5)
        detour.status = DetourStatus.ACTIVE
        db.commit()

        resp = httpx.post(f"{BASE_URL}/detours/{detour_id}/confirm")
        assert resp.status_code == 200

        resp = httpx.get(f"{BASE_URL}/detours/active/{line_id}")
        data = resp.json()
        assert data["days_since_confirmed"] == 0
        assert data["confidence_pct"] == 100

    def test_nearby_lines_shows_confidence(self, db, active_detour_id):
        detour_id, line_id = active_detour_id
        from database.models.detour import Detour, DetourStatus

        detour = db.get(Detour, detour_id)
        detour.last_confirmed_at = datetime.utcnow() - timedelta(days=3)
        detour.status = DetourStatus.ACTIVE
        db.commit()

        resp = httpx.get(
            f"{BASE_URL}/lines/nearby/",
            params={
                "longitude": -66.182,
                "latitude": -17.394,
                "radius_meters": 2000,
                "include_pending": True,
            },
            timeout=30.0,
        )
        assert resp.status_code == 200
        data = resp.json()
        line_250 = next((l for l in data if "250" in l["line_name"]), None)
        assert line_250 is not None
        assert line_250["detour_alert"] is not None
        assert line_250["detour_alert"]["days_since_confirmed"] == 3
