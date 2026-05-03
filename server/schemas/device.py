"""Schemas for the /devices endpoints."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlmodel import SQLModel

from database.models.device import Platform


class DeviceRegister(SQLModel):
    """Body for POST /devices/register.

    Sent by the app on every launch (even when push permission is denied —
    in that case `expo_push_token` is null but the row is still created so
    that downstream FK-constrained writes succeed).
    """

    device_id: str
    expo_push_token: Optional[str] = None
    platform: Optional[Platform] = None
    locale: Optional[str] = None


class DeviceRead(SQLModel):
    id: str
    expo_push_token: Optional[str] = None
    platform: Optional[Platform] = None
    locale: Optional[str] = None
    last_seen_at: datetime
    created_at: datetime


class SubscriptionsUpdate(SQLModel):
    """Body for PUT /devices/{id}/subscriptions — bulk-replace commute subs."""

    line_ids: list[UUID]
