"""Crowdsourced free-text descriptors for ramales (gap #7).

Users describe distinguishing features of a ramal — e.g. "lleva
banderines naranjas en frente", "letrero con logo de Univalle" — to
help other passengers identify which physical bus belongs to which
ramal of a given line.

Two tables:

- `RamalDescriptor` — one row per unique descriptor text per route.
  `text_normalized` (lowercased + trimmed) drives the unique constraint
  so casing/whitespace variations don't proliferate. The original `text`
  is kept for display.
- `RamalDescriptorVote` — one upvote per (descriptor, device). The
  `votes_count` cache on `RamalDescriptor` is updated transactionally
  with vote inserts/deletes so the API doesn't have to aggregate on
  every read.
"""

import uuid as _uuid
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class RamalDescriptor(SQLModel, table=True):
    """A user-submitted descriptor for one ramal (Route)."""

    __tablename__ = "ramal_descriptors"
    __table_args__ = (
        UniqueConstraint(
            "route_id", "text_normalized",
            name="uq_ramal_descriptor_route_text",
        ),
    )

    id: Optional[UUID] = Field(default_factory=_uuid.uuid4, primary_key=True)
    route_id: UUID = Field(foreign_key="routes.id", index=True)

    # Original text as the user typed it (display).
    text: str = Field(max_length=200)
    # Normalised (lowercased, whitespace-collapsed) for dedup. Indexed
    # implicitly via the unique constraint with `route_id`.
    text_normalized: str = Field(max_length=200)

    # Cached vote count (creator counts as 1; subsequent upvotes
    # increment). Maintained by the endpoints in lock-step with
    # `RamalDescriptorVote` inserts/deletes.
    votes_count: int = Field(default=1)

    created_by_device_id: str = Field(
        foreign_key="devices.id", max_length=255, index=True,
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)


class RamalDescriptorVote(SQLModel, table=True):
    """One upvote per (descriptor, device). Existence is the vote;
    deletes undo the upvote and decrement the cache."""

    __tablename__ = "ramal_descriptor_votes"
    __table_args__ = (
        UniqueConstraint(
            "descriptor_id", "device_id",
            name="uq_ramal_descriptor_vote_device",
        ),
    )

    id: Optional[UUID] = Field(default_factory=_uuid.uuid4, primary_key=True)
    descriptor_id: UUID = Field(
        foreign_key="ramal_descriptors.id", index=True,
    )
    device_id: str = Field(
        foreign_key="devices.id", max_length=255, index=True,
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)


def normalize_descriptor_text(text: str) -> str:
    """Canonical form for dedup: lowercased + whitespace collapsed."""
    return " ".join(text.lower().split())
