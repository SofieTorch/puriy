"""Tests for /devices/register and /devices/{id}/subscriptions."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models.device import Device, Platform
from database.models.line import Line, LineStatus
from database.models.subscription import LineSubscription, SubscriptionKind


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def line_a(db: Session) -> Line:
    line = Line(name="Línea A", status=LineStatus.APPROVED)
    db.add(line)
    db.commit()
    db.refresh(line)
    return line


@pytest.fixture
def line_b(db: Session) -> Line:
    line = Line(name="Línea B", status=LineStatus.APPROVED)
    db.add(line)
    db.commit()
    db.refresh(line)
    return line


# ------------------------------------------------------------------
# /devices/register
# ------------------------------------------------------------------

def test_register_creates_device(client: TestClient, db: Session) -> None:
    resp = client.post("/devices/register", json={
        "device_id": "device-aaa",
        "expo_push_token": "ExponentPushToken[xxx]",
        "platform": "ios",
        "locale": "es-BO",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "device-aaa"
    assert data["expo_push_token"] == "ExponentPushToken[xxx]"
    assert data["platform"] == "ios"
    assert data["locale"] == "es-BO"

    db.expire_all()
    stored = db.get(Device, "device-aaa")
    assert stored is not None
    assert stored.platform == Platform.IOS


def test_register_updates_existing_device(client: TestClient, db: Session) -> None:
    client.post("/devices/register", json={
        "device_id": "device-bbb",
        "expo_push_token": "old-token",
        "platform": "android",
    })
    resp = client.post("/devices/register", json={
        "device_id": "device-bbb",
        "expo_push_token": "new-token",
        "platform": "android",
        "locale": "en-US",
    })
    assert resp.status_code == 200
    assert resp.json()["expo_push_token"] == "new-token"
    assert resp.json()["locale"] == "en-US"


def test_register_without_push_token_succeeds(client: TestClient) -> None:
    """A device that declined notification permission still registers."""
    resp = client.post("/devices/register", json={
        "device_id": "device-ccc",
        "platform": "ios",
    })
    assert resp.status_code == 200
    assert resp.json()["expo_push_token"] is None


# ------------------------------------------------------------------
# /devices/{id}/subscriptions
# ------------------------------------------------------------------

def test_replace_subscriptions_creates_rows(
    client: TestClient, db: Session, line_a: Line, line_b: Line,
) -> None:
    client.post("/devices/register", json={"device_id": "dev-1", "platform": "ios"})

    resp = client.put(
        "/devices/dev-1/subscriptions",
        json={"line_ids": [str(line_a.id), str(line_b.id)]},
    )
    assert resp.status_code == 200

    db.expire_all()
    subs = db.execute(
        select(LineSubscription).where(LineSubscription.device_id == "dev-1")
    ).scalars().all()
    assert {sub.line_id for sub in subs} == {line_a.id, line_b.id}
    assert all(sub.kind == SubscriptionKind.COMMUTE for sub in subs)


def test_replace_subscriptions_replaces_old(
    client: TestClient, db: Session, line_a: Line, line_b: Line,
) -> None:
    client.post("/devices/register", json={"device_id": "dev-2", "platform": "android"})
    client.put("/devices/dev-2/subscriptions", json={"line_ids": [str(line_a.id)]})
    client.put("/devices/dev-2/subscriptions", json={"line_ids": [str(line_b.id)]})

    db.expire_all()
    subs = db.execute(
        select(LineSubscription).where(LineSubscription.device_id == "dev-2")
    ).scalars().all()
    assert {sub.line_id for sub in subs} == {line_b.id}


def test_replace_subscriptions_unknown_device_404(
    client: TestClient, line_a: Line,
) -> None:
    resp = client.put(
        "/devices/never-registered/subscriptions",
        json={"line_ids": [str(line_a.id)]},
    )
    assert resp.status_code == 404


def test_delete_subscription(
    client: TestClient, db: Session, line_a: Line, line_b: Line,
) -> None:
    client.post("/devices/register", json={"device_id": "dev-3", "platform": "ios"})
    client.put(
        "/devices/dev-3/subscriptions",
        json={"line_ids": [str(line_a.id), str(line_b.id)]},
    )

    resp = client.delete(f"/devices/dev-3/subscriptions/{line_a.id}")
    assert resp.status_code == 204

    db.expire_all()
    subs = db.execute(
        select(LineSubscription).where(LineSubscription.device_id == "dev-3")
    ).scalars().all()
    assert {sub.line_id for sub in subs} == {line_b.id}


def test_delete_subscription_unknown_is_noop(
    client: TestClient, line_a: Line,
) -> None:
    resp = client.delete(f"/devices/no-such-device/subscriptions/{line_a.id}")
    assert resp.status_code == 204
