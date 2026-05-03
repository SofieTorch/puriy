"""Line subscriptions — devices that should be notified about events on a line."""

import uuid as _uuid
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class SubscriptionKind(str, Enum):
    COMMUTE = "commute"


class LineSubscription(SQLModel, table=True):
    """A (device, line, kind) tuple. Used to find recipients for push
    notifications when something happens on a line — currently only
    commute saved-trips trigger subscriptions.
    """

    __tablename__ = "line_subscriptions"
    __table_args__ = (
        UniqueConstraint(
            "device_id", "line_id", "kind",
            name="uq_line_subscription_device_line_kind",
        ),
    )

    id: Optional[UUID] = Field(default_factory=_uuid.uuid4, primary_key=True)
    device_id: str = Field(foreign_key="devices.id", max_length=255, index=True)
    line_id: UUID = Field(foreign_key="lines.id", index=True)
    kind: SubscriptionKind = Field(default=SubscriptionKind.COMMUTE)
    created_at: datetime = Field(default_factory=datetime.utcnow)
