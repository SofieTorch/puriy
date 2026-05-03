"""Tests for the detour-notification dispatch service."""

from datetime import datetime, timedelta
from unittest.mock import patch
from uuid import UUID

import pytest
from sqlalchemy.orm import Session

from database.models.detour import Detour
from database.models.device import Device, Platform
from database.models.line import Line, LineStatus
from database.models.notification_dispatch import NotificationDispatch, NotificationKind
from database.models.subscription import LineSubscription, SubscriptionKind
from database.models.trip import SessionStatus, TripSession

from services.push import notify_detour_subscribers


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def detour_line(db: Session) -> Line:
    line = Line(name="Línea 17", status=LineStatus.APPROVED)
    db.add(line)
    db.commit()
    db.refresh(line)
    return line


@pytest.fixture
def detour_session(db: Session, detour_line: Line) -> TripSession:
    """A completed TripSession; reporter device is `test-device-abc`
    (already auto-registered by conftest)."""
    session = TripSession(
        line_id=detour_line.id,
        device_id="test-device-abc",
        status=SessionStatus.COMPLETED,
        ended_at=datetime.utcnow(),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@pytest.fixture
def detour(db: Session, detour_line: Line, detour_session: TripSession) -> Detour:
    d = Detour(
        line_id=detour_line.id,
        session_id=detour_session.id,
        reason="Construcción",
        description="Calle cerrada por obras municipales",
    )
    db.add(d)
    db.commit()
    db.refresh(d)
    return d


def _make_subscriber(
    db: Session, device_id: str, line_id: UUID, *, token: str | None = "ExpoTok",
) -> Device:
    """Create a Device + LineSubscription in one shot."""
    dev = Device(id=device_id, expo_push_token=token, platform=Platform.IOS)
    db.add(dev)
    db.add(LineSubscription(
        device_id=device_id,
        line_id=line_id,
        kind=SubscriptionKind.COMMUTE,
    ))
    db.commit()
    return dev


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------

def test_sends_individual_when_no_history(
    db: Session, detour_line: Line, detour: Detour,
) -> None:
    _make_subscriber(db, "sub-1", detour_line.id)

    with patch("services.push.httpx.post") as mock_post:
        mock_post.return_value.raise_for_status = lambda: None
        result = notify_detour_subscribers(
            db, line_id=detour_line.id, detour_id=detour.id,
        )

    assert result == {"individual": 1, "coalesced": 0, "skipped": 0}
    assert mock_post.call_count == 1
    sent = mock_post.call_args.kwargs["json"]
    assert sent[0]["to"] == "ExpoTok"
    assert "Línea 17" in sent[0]["title"]
    assert sent[0]["data"]["kind"] == "detour_individual"

    rows = db.query(NotificationDispatch).filter_by(device_id="sub-1").all()
    assert [r.kind for r in rows] == [NotificationKind.DETOUR_INDIVIDUAL]


def test_sends_coalesced_after_three_individuals(
    db: Session, detour_line: Line, detour: Detour,
) -> None:
    _make_subscriber(db, "sub-2", detour_line.id)
    for _ in range(3):
        db.add(NotificationDispatch(
            device_id="sub-2",
            line_id=detour_line.id,
            detour_id=detour.id,
            kind=NotificationKind.DETOUR_INDIVIDUAL,
        ))
    db.commit()

    with patch("services.push.httpx.post") as mock_post:
        mock_post.return_value.raise_for_status = lambda: None
        result = notify_detour_subscribers(
            db, line_id=detour_line.id, detour_id=detour.id,
        )

    assert result == {"individual": 0, "coalesced": 1, "skipped": 0}
    sent = mock_post.call_args.kwargs["json"]
    assert sent[0]["data"]["kind"] == "detour_coalesced"
    assert "Más desvíos" in sent[0]["title"]

    coalesced = db.query(NotificationDispatch).filter_by(
        device_id="sub-2", kind=NotificationKind.DETOUR_COALESCED,
    ).all()
    assert len(coalesced) == 1


def test_skips_after_coalesced_already_sent(
    db: Session, detour_line: Line, detour: Detour,
) -> None:
    _make_subscriber(db, "sub-3", detour_line.id)
    for _ in range(3):
        db.add(NotificationDispatch(
            device_id="sub-3",
            line_id=detour_line.id,
            detour_id=detour.id,
            kind=NotificationKind.DETOUR_INDIVIDUAL,
        ))
    db.add(NotificationDispatch(
        device_id="sub-3",
        line_id=detour_line.id,
        detour_id=None,
        kind=NotificationKind.DETOUR_COALESCED,
    ))
    db.commit()

    with patch("services.push.httpx.post") as mock_post:
        result = notify_detour_subscribers(
            db, line_id=detour_line.id, detour_id=detour.id,
        )

    assert result == {"individual": 0, "coalesced": 0, "skipped": 1}
    assert mock_post.call_count == 0


def test_excludes_reporter(
    db: Session, detour_line: Line, detour: Detour,
) -> None:
    _make_subscriber(db, "reporter", detour_line.id)

    with patch("services.push.httpx.post") as mock_post:
        result = notify_detour_subscribers(
            db, line_id=detour_line.id, detour_id=detour.id,
            exclude_device_id="reporter",
        )

    assert result == {"individual": 0, "coalesced": 0, "skipped": 0}
    assert mock_post.call_count == 0


def test_skips_devices_without_token(
    db: Session, detour_line: Line, detour: Detour,
) -> None:
    _make_subscriber(db, "no-push-dev", detour_line.id, token=None)

    with patch("services.push.httpx.post") as mock_post:
        result = notify_detour_subscribers(
            db, line_id=detour_line.id, detour_id=detour.id,
        )

    assert result == {"individual": 0, "coalesced": 0, "skipped": 0}
    assert mock_post.call_count == 0


def test_window_only_counts_recent_dispatches(
    db: Session, detour_line: Line, detour: Detour,
) -> None:
    """Dispatches older than 24h don't count toward the limit."""
    _make_subscriber(db, "old-sub", detour_line.id)
    old = datetime.utcnow() - timedelta(hours=25)
    for _ in range(3):
        row = NotificationDispatch(
            device_id="old-sub",
            line_id=detour_line.id,
            detour_id=detour.id,
            kind=NotificationKind.DETOUR_INDIVIDUAL,
            sent_at=old,
        )
        db.add(row)
    db.commit()

    with patch("services.push.httpx.post") as mock_post:
        mock_post.return_value.raise_for_status = lambda: None
        result = notify_detour_subscribers(
            db, line_id=detour_line.id, detour_id=detour.id,
        )

    assert result == {"individual": 1, "coalesced": 0, "skipped": 0}


def test_returns_zero_counts_for_unknown_detour(
    db: Session, detour_line: Line,
) -> None:
    """Defensive: missing detour shouldn't crash, just no-op."""
    from uuid import uuid4
    with patch("services.push.httpx.post") as mock_post:
        result = notify_detour_subscribers(
            db, line_id=detour_line.id, detour_id=uuid4(),
        )
    assert result == {"individual": 0, "coalesced": 0, "skipped": 0}
    assert mock_post.call_count == 0


def test_expo_failure_does_not_raise(
    db: Session, detour_line: Line, detour: Detour,
) -> None:
    """A 5xx from Expo (or network error) must not propagate."""
    _make_subscriber(db, "sub-flaky", detour_line.id)

    def boom(*_args, **_kwargs):
        raise RuntimeError("expo down")

    with patch("services.push.httpx.post", side_effect=boom):
        # Must not raise, even though the post failed.
        result = notify_detour_subscribers(
            db, line_id=detour_line.id, detour_id=detour.id,
        )

    # The dispatch row is still written even when the POST fails — that
    # matches the "best-effort" semantics described in the docstring.
    assert result == {"individual": 1, "coalesced": 0, "skipped": 0}
