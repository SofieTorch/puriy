"""Crowdsourced descriptors per ramal (Route).

The mobile flow is **vote-on-existing-first**: when a user wants to
add a descriptor, the UI shows existing ones with upvote chips and
only reveals the text input after the user explicitly says none of
them match. The endpoints support that flow:

- `GET /routes/{route_id}/descriptors[?device_id=…]` — list ordered
  by votes desc, including `voted_by_me` when device_id is provided.
- `POST /routes/{route_id}/descriptors/{descriptor_id}/upvote` —
  idempotent; +1 to `votes_count` only if a new vote row was inserted.
- `DELETE /routes/{route_id}/descriptors/{descriptor_id}/upvote` —
  reverse; -1 only if a vote row was removed.
- `POST /routes/{route_id}/descriptors` — create new. Returns 409
  with the existing descriptor if `text_normalized` already exists for
  the route, so the client can offer to upvote it instead.

Decision #5 from the design: `ramal_label` is never exposed in this
flow. The descriptor surface identifies the ramal by its geometry +
endpoint zones + street summary on the screen above the descriptors.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import (
    RamalDescriptor,
    RamalDescriptorVote,
    Route,
)
from database.connection import get_db
from database.devices import ensure_device
from database.models.ramal_descriptor import normalize_descriptor_text

from schemas.ramal_descriptor import (
    RamalDescriptorCreate,
    RamalDescriptorRead,
    RamalDescriptorVoteAction,
)


router = APIRouter(prefix="/routes/{route_id}/descriptors", tags=["descriptors"])


def _get_route_or_404(db: Session, route_id: UUID) -> Route:
    route = db.get(Route, route_id)
    if route is None:
        raise HTTPException(status_code=404, detail="Route not found")
    return route


def _to_read(
    descriptor: RamalDescriptor, *, voted_by_me: bool = False,
) -> RamalDescriptorRead:
    return RamalDescriptorRead(
        id=descriptor.id,
        route_id=descriptor.route_id,
        text=descriptor.text,
        votes_count=descriptor.votes_count,
        created_at=descriptor.created_at,
        voted_by_me=voted_by_me,
    )


@router.get("/", response_model=list[RamalDescriptorRead])
def list_descriptors(
    route_id: UUID,
    device_id: str | None = Query(default=None, max_length=255),
    db: Session = Depends(get_db),
) -> list[RamalDescriptorRead]:
    """List descriptors for a route, ordered by `votes_count desc, created_at asc`.

    When `device_id` is provided, each descriptor's `voted_by_me`
    reflects whether that device has already upvoted it.
    """
    _get_route_or_404(db, route_id)

    descriptors = db.execute(
        select(RamalDescriptor)
        .where(RamalDescriptor.route_id == route_id)
        .order_by(RamalDescriptor.votes_count.desc(), RamalDescriptor.created_at)
    ).scalars().all()

    voted_set: set[UUID] = set()
    if device_id and descriptors:
        voted_rows = db.execute(
            select(RamalDescriptorVote.descriptor_id).where(
                RamalDescriptorVote.device_id == device_id,
                RamalDescriptorVote.descriptor_id.in_([d.id for d in descriptors]),
            )
        ).scalars().all()
        voted_set = set(voted_rows)

    return [_to_read(d, voted_by_me=(d.id in voted_set)) for d in descriptors]


@router.post("/", response_model=RamalDescriptorRead, status_code=201)
def create_descriptor(
    route_id: UUID,
    body: RamalDescriptorCreate,
    db: Session = Depends(get_db),
) -> RamalDescriptorRead:
    """Create a new descriptor.

    Returns 409 with the existing descriptor in the body when a
    descriptor with the same `text_normalized` already exists for
    this route — the client should fall back to upvoting it.
    """
    _get_route_or_404(db, route_id)
    ensure_device(db, body.device_id)

    text_normalized = normalize_descriptor_text(body.text)
    if not text_normalized:
        raise HTTPException(status_code=400, detail="Descriptor text is empty.")

    # Pre-flight existence check (avoids the IntegrityError round-trip
    # when the dedup is the common case).
    existing = db.execute(
        select(RamalDescriptor).where(
            RamalDescriptor.route_id == route_id,
            RamalDescriptor.text_normalized == text_normalized,
        )
    ).scalars().first()
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "A descriptor with similar text already exists.",
                "existing": _to_read(existing).model_dump(mode="json"),
            },
        )

    descriptor = RamalDescriptor(
        route_id=route_id,
        text=body.text.strip(),
        text_normalized=text_normalized,
        votes_count=1,
        created_by_device_id=body.device_id,
    )
    db.add(descriptor)
    db.flush()
    # Creator's implicit vote — kept consistent with the cache (1).
    db.add(RamalDescriptorVote(
        descriptor_id=descriptor.id, device_id=body.device_id,
    ))
    try:
        db.commit()
    except IntegrityError:
        # Race: someone else inserted the same text between our check
        # and commit. Roll back and surface the conflict.
        db.rollback()
        existing = db.execute(
            select(RamalDescriptor).where(
                RamalDescriptor.route_id == route_id,
                RamalDescriptor.text_normalized == text_normalized,
            )
        ).scalars().first()
        if existing is not None:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "A descriptor with similar text already exists.",
                    "existing": _to_read(existing).model_dump(mode="json"),
                },
            )
        raise

    db.refresh(descriptor)
    return _to_read(descriptor, voted_by_me=True)


@router.post("/{descriptor_id}/upvote", response_model=RamalDescriptorRead)
def upvote_descriptor(
    route_id: UUID,
    descriptor_id: UUID,
    body: RamalDescriptorVoteAction,
    db: Session = Depends(get_db),
) -> RamalDescriptorRead:
    """Idempotent: inserts a vote row if missing and bumps `votes_count`.
    No-op when the device has already voted."""
    descriptor = db.get(RamalDescriptor, descriptor_id)
    if descriptor is None or descriptor.route_id != route_id:
        raise HTTPException(status_code=404, detail="Descriptor not found")
    ensure_device(db, body.device_id)

    existing_vote = db.execute(
        select(RamalDescriptorVote).where(
            RamalDescriptorVote.descriptor_id == descriptor_id,
            RamalDescriptorVote.device_id == body.device_id,
        )
    ).scalars().first()
    if existing_vote is None:
        db.add(RamalDescriptorVote(
            descriptor_id=descriptor_id, device_id=body.device_id,
        ))
        descriptor.votes_count += 1
        db.commit()
        db.refresh(descriptor)

    return _to_read(descriptor, voted_by_me=True)


@router.delete("/{descriptor_id}/upvote", response_model=RamalDescriptorRead)
def unvote_descriptor(
    route_id: UUID,
    descriptor_id: UUID,
    body: RamalDescriptorVoteAction,
    db: Session = Depends(get_db),
) -> RamalDescriptorRead:
    """Reverse an upvote. No-op when the device hadn't voted."""
    descriptor = db.get(RamalDescriptor, descriptor_id)
    if descriptor is None or descriptor.route_id != route_id:
        raise HTTPException(status_code=404, detail="Descriptor not found")

    vote = db.execute(
        select(RamalDescriptorVote).where(
            RamalDescriptorVote.descriptor_id == descriptor_id,
            RamalDescriptorVote.device_id == body.device_id,
        )
    ).scalars().first()
    if vote is not None:
        db.delete(vote)
        descriptor.votes_count = max(0, descriptor.votes_count - 1)
        db.commit()
        db.refresh(descriptor)

    return _to_read(descriptor, voted_by_me=False)
