"""Housekeeping: abandon stale sessions, expire old detours."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from database import Detour, DetourStatus, SessionStatus, TripSession


def execute(
    db: Session,
    *,
    inactive_minutes: int = 30,
    detour_expiry_days: int = 7,
) -> dict:
    now = datetime.now(timezone.utc)

    # Mark stale IN_PROGRESS sessions as ABANDONED
    cutoff = now - timedelta(minutes=inactive_minutes)
    stale = db.execute(
        select(TripSession).where(
            TripSession.status == SessionStatus.IN_PROGRESS,
            TripSession.last_activity_at < cutoff,
        )
    ).scalars().all()

    for session in stale:
        session.status = SessionStatus.ABANDONED
        session.ended_at = session.last_activity_at

    # Expire detours not confirmed recently
    detour_cutoff = now - timedelta(days=detour_expiry_days)
    expired = db.execute(
        update(Detour)
        .where(
            Detour.status == DetourStatus.ACTIVE,
            Detour.last_confirmed_at < detour_cutoff,
        )
        .values(status=DetourStatus.EXPIRED)
        .returning(Detour.id)
    ).all()

    db.commit()

    return {
        "sessions_abandoned": len(stale),
        "detours_expired": len(expired),
    }
