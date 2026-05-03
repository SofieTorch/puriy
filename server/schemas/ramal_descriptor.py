"""Schemas for the `/routes/{route_id}/descriptors` endpoints (gap #7)."""

from datetime import datetime
from uuid import UUID

from sqlmodel import Field, SQLModel


class RamalDescriptorCreate(SQLModel):
    """Body for creating a new descriptor."""

    text: str = Field(min_length=1, max_length=200)
    device_id: str = Field(min_length=1, max_length=255)


class RamalDescriptorVoteAction(SQLModel):
    """Body for upvote/unvote endpoints."""

    device_id: str = Field(min_length=1, max_length=255)


class RamalDescriptorRead(SQLModel):
    """A descriptor as returned to the client."""

    id: UUID
    route_id: UUID
    text: str
    votes_count: int
    created_at: datetime
    # True iff the device specified via `?device_id=` (when listing) has
    # already upvoted this descriptor — drives the "voted" UI state.
    voted_by_me: bool = False


class RamalDescriptorConflict(SQLModel):
    """Returned with HTTP 409 when a create-new submission collides
    with an existing descriptor (same `text_normalized`). The client
    is expected to surface the existing descriptor and offer to upvote
    it instead."""

    detail: str = "A descriptor with similar text already exists."
    existing: RamalDescriptorRead
