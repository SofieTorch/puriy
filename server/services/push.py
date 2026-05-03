"""Push notification dispatch via the Expo HTTP API.

Notifies commute subscribers when a detour is reported on their line.
Implements a 24h-rolling rate limit per (device, line):

  * up to 3 individual "Desvío en {línea}" notifications, then
  * one "Más desvíos en {línea}" coalesced summary, then
  * silence until the window resets.

Each delivery is logged in `notification_dispatches` so the limit is
durable across restarts.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from database.connection import SessionLocal
from database.models.detour import Detour
from database.models.device import Device
from database.models.line import Line
from database.models.notification_dispatch import NotificationDispatch, NotificationKind
from database.models.subscription import LineSubscription, SubscriptionKind

logger = logging.getLogger(__name__)

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"
INDIVIDUAL_LIMIT = 3
WINDOW = timedelta(hours=24)


def notify_detour_subscribers(
    db: Session,
    *,
    line_id: UUID,
    detour_id: UUID,
    exclude_device_id: Optional[str] = None,
) -> dict[str, int]:
    """Send detour pushes to all commute subscribers of `line_id`.

    Returns a dict `{individual, coalesced, skipped}` with counts of what
    was sent (or suppressed). The caller is responsible for committing
    the session — but this function commits internally because it's
    typically called from a BackgroundTask with its own short-lived
    session, so committing here keeps the dispatches log durable even
    if the caller forgets.
    """
    line = db.get(Line, line_id)
    detour = db.get(Detour, detour_id)
    if line is None or detour is None:
        logger.warning(
            "notify_detour_subscribers: missing line=%s or detour=%s",
            line_id, detour_id,
        )
        return {"individual": 0, "coalesced": 0, "skipped": 0}

    # All subscribed devices that have a push token.
    devices = db.execute(
        select(Device)
        .join(LineSubscription, LineSubscription.device_id == Device.id)
        .where(
            LineSubscription.line_id == line_id,
            LineSubscription.kind == SubscriptionKind.COMMUTE,
            Device.expo_push_token.is_not(None),
        )
    ).scalars().all()

    if exclude_device_id is not None:
        devices = [d for d in devices if d.id != exclude_device_id]

    if not devices:
        return {"individual": 0, "coalesced": 0, "skipped": 0}

    cutoff = datetime.utcnow() - WINDOW
    individual_targets: list[Device] = []
    coalesced_targets: list[Device] = []
    skipped = 0

    for device in devices:
        recent = db.execute(
            select(NotificationDispatch).where(
                NotificationDispatch.device_id == device.id,
                NotificationDispatch.line_id == line_id,
                NotificationDispatch.sent_at >= cutoff,
            )
        ).scalars().all()

        n_individual = sum(
            1 for r in recent if r.kind == NotificationKind.DETOUR_INDIVIDUAL
        )
        n_coalesced = sum(
            1 for r in recent if r.kind == NotificationKind.DETOUR_COALESCED
        )

        if n_coalesced >= 1:
            # Already sent the daily summary — silence until the window resets.
            skipped += 1
        elif n_individual < INDIVIDUAL_LIMIT:
            individual_targets.append(device)
        else:
            coalesced_targets.append(device)

    line_name = line.name or "tu línea"

    if individual_targets:
        body = detour.reason or "Desvío activo"
        if detour.description:
            body = f"{body}: {detour.description[:80]}"
        _post_to_expo([
            {
                "to": d.expo_push_token,
                "title": f"Desvío en {line_name}",
                "body": body,
                "data": {
                    "kind": "detour_individual",
                    "line_id": str(line_id),
                    "detour_id": str(detour_id),
                },
            }
            for d in individual_targets
        ])
        for d in individual_targets:
            db.add(NotificationDispatch(
                device_id=d.id,
                line_id=line_id,
                detour_id=detour_id,
                kind=NotificationKind.DETOUR_INDIVIDUAL,
            ))

    if coalesced_targets:
        _post_to_expo([
            {
                "to": d.expo_push_token,
                "title": f"Más desvíos en {line_name}",
                "body": "Hay varios desvíos activos. Tocá para verlos.",
                "data": {
                    "kind": "detour_coalesced",
                    "line_id": str(line_id),
                },
            }
            for d in coalesced_targets
        ])
        for d in coalesced_targets:
            db.add(NotificationDispatch(
                device_id=d.id,
                line_id=line_id,
                detour_id=None,
                kind=NotificationKind.DETOUR_COALESCED,
            ))

    db.commit()
    return {
        "individual": len(individual_targets),
        "coalesced": len(coalesced_targets),
        "skipped": skipped,
    }


def _post_to_expo(messages: list[dict]) -> None:
    """POST a batch of messages to Expo. Logs failures but never raises —
    push delivery failures must not disrupt the user's request flow.
    """
    if not messages:
        return
    try:
        resp = httpx.post(EXPO_PUSH_URL, json=messages, timeout=10.0)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001 — intentional broad catch
        logger.warning("Expo push failed (%d msgs): %s", len(messages), exc)


def dispatch_detour_notifications(
    line_id: UUID,
    detour_id: UUID,
    exclude_device_id: Optional[str] = None,
) -> None:
    """BackgroundTask entry point — opens a fresh DB session, runs the
    dispatch, swallows any error so the task scheduler never crashes the
    request lifecycle.
    """
    with SessionLocal() as db:
        try:
            notify_detour_subscribers(
                db,
                line_id=line_id,
                detour_id=detour_id,
                exclude_device_id=exclude_device_id,
            )
        except Exception:  # noqa: BLE001
            logger.exception("notify_detour_subscribers crashed")
            db.rollback()
