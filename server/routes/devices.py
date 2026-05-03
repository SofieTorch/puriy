"""Endpoints for device registration and commute subscriptions.

The app calls `POST /devices/register` on every launch (even when push
permission is denied — `expo_push_token` is just null in that case).
This guarantees that any subsequent write whose `device_id` is FK-
constrained to `devices.id` (TripSession, EdgeVote, LineVote, FareReport,
LineSubscription, NotificationDispatch) will succeed.

Subscriptions track which lines a device has saved as a "commute" trip
and therefore wants push notifications about. PUT replaces the full set
for a device; DELETE removes a single (device, line) pair.
"""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from database.connection import get_db
from database.models.device import Device
from database.models.subscription import LineSubscription, SubscriptionKind

from schemas.device import DeviceRead, DeviceRegister, SubscriptionsUpdate

router = APIRouter(prefix="/devices", tags=["devices"])


@router.post("/register", response_model=DeviceRead)
def register_device(body: DeviceRegister, db: Session = Depends(get_db)) -> DeviceRead:
    """Upsert a device by id. Updates push token, platform, locale on every call."""
    device = db.get(Device, body.device_id)
    now = datetime.utcnow()
    if device is None:
        device = Device(
            id=body.device_id,
            expo_push_token=body.expo_push_token,
            platform=body.platform,
            locale=body.locale,
            last_seen_at=now,
            created_at=now,
        )
        db.add(device)
    else:
        device.expo_push_token = body.expo_push_token
        device.platform = body.platform
        device.locale = body.locale
        device.last_seen_at = now
    db.commit()
    db.refresh(device)
    return DeviceRead.model_validate(device, from_attributes=True)


@router.put("/{device_id}/subscriptions", response_model=list[UUID])
def replace_subscriptions(
    device_id: str,
    body: SubscriptionsUpdate,
    db: Session = Depends(get_db),
) -> list[UUID]:
    """Bulk-replace this device's commute subscriptions with `body.line_ids`."""
    if db.get(Device, device_id) is None:
        raise HTTPException(status_code=404, detail="Device not registered")

    existing = db.execute(
        select(LineSubscription).where(
            LineSubscription.device_id == device_id,
            LineSubscription.kind == SubscriptionKind.COMMUTE,
        )
    ).scalars().all()
    for sub in existing:
        db.delete(sub)
    db.flush()

    for line_id in body.line_ids:
        db.add(LineSubscription(
            device_id=device_id,
            line_id=line_id,
            kind=SubscriptionKind.COMMUTE,
        ))
    db.commit()
    return body.line_ids


@router.delete("/{device_id}/subscriptions/{line_id}", status_code=204)
def delete_subscription(
    device_id: str,
    line_id: UUID,
    db: Session = Depends(get_db),
) -> None:
    """Remove a single commute subscription. No-op if it didn't exist."""
    sub = db.execute(
        select(LineSubscription).where(
            LineSubscription.device_id == device_id,
            LineSubscription.line_id == line_id,
            LineSubscription.kind == SubscriptionKind.COMMUTE,
        )
    ).scalar_one_or_none()
    if sub is not None:
        db.delete(sub)
        db.commit()
