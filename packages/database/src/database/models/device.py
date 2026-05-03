"""Device registry — push notification tokens per client device."""

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel


class Platform(str, Enum):
    IOS = "ios"
    ANDROID = "android"


class Device(SQLModel, table=True):
    """A client device.

    `id` is the same string used throughout the codebase as `device_id` —
    generated client-side and provided in request bodies. After the FK
    refactor, every `device_id` referenced from TripSession / EdgeVote /
    LineVote / FareReport / LineSubscription / NotificationDispatch must
    point at a row in this table.

    `platform` and `expo_push_token` are nullable because (a) historical
    rows backfilled from existing device_ids have no platform info, and
    (b) a device can register without granting notification permission.
    """

    __tablename__ = "devices"

    id: str = Field(primary_key=True, max_length=255)
    expo_push_token: Optional[str] = Field(default=None, max_length=255)
    platform: Optional[Platform] = Field(default=None)
    locale: Optional[str] = Field(default=None, max_length=16)
    last_seen_at: datetime = Field(default_factory=datetime.utcnow)
    created_at: datetime = Field(default_factory=datetime.utcnow)
