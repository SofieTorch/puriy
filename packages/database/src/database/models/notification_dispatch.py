"""Notification dispatch log — what we sent, to whom, when.

Used to enforce the per-(device, line) rate limit: up to 3 individual
detour notifications in a 24h rolling window, then one coalesced "más
desvíos en línea X" summary.
"""

import uuid as _uuid
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from sqlmodel import Field, SQLModel


class NotificationKind(str, Enum):
    DETOUR_INDIVIDUAL = "detour_individual"
    DETOUR_COALESCED = "detour_coalesced"


class NotificationDispatch(SQLModel, table=True):
    __tablename__ = "notification_dispatches"

    id: Optional[UUID] = Field(default_factory=_uuid.uuid4, primary_key=True)
    device_id: str = Field(foreign_key="devices.id", max_length=255, index=True)
    line_id: UUID = Field(foreign_key="lines.id", index=True)
    detour_id: Optional[UUID] = Field(
        default=None, foreign_key="detours.id", index=True,
    )
    kind: NotificationKind
    sent_at: datetime = Field(default_factory=datetime.utcnow, index=True)
