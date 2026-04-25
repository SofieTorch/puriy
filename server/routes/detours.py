from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from database.connection import get_db
from database.models.detour import Detour, DetourStatus
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, update
from sqlalchemy.orm import Session, selectinload

from schemas.detour import DetourRead

router = APIRouter(prefix="/detours", tags=["detours"])


@router.get("/active", response_model=list[DetourRead])
def list_active_detours(
    line_id: Optional[UUID] = Query(None),
    db: Session = Depends(get_db),
) -> list[DetourRead]:
    """List all active detours, optionally filtered by line."""
    stmt = (
        select(Detour)
        .options(selectinload(Detour.line))
        .where(Detour.status == DetourStatus.ACTIVE)
    )
    if line_id is not None:
        stmt = stmt.where(Detour.line_id == line_id)
    detours = db.execute(stmt).scalars().all()
    return [DetourRead.model_validate(d) for d in detours]


@router.get("/active/{line_id}", response_model=DetourRead)
def get_active_detour_for_line(
    line_id: UUID,
    db: Session = Depends(get_db),
) -> DetourRead:
    """Get the active detour for a specific line."""
    stmt = (
        select(Detour)
        .options(selectinload(Detour.line))
        .where(Detour.status == DetourStatus.ACTIVE, Detour.line_id == line_id)
    )
    detour = db.execute(stmt).scalars().first()
    if detour is None:
        raise HTTPException(status_code=404, detail="No active detour for this line")
    return DetourRead.model_validate(detour)


@router.post("/{detour_id}/confirm", response_model=DetourRead)
def confirm_detour(
    detour_id: UUID,
    db: Session = Depends(get_db),
) -> DetourRead:
    """Confirm that a detour is still active."""
    stmt = (
        select(Detour)
        .options(selectinload(Detour.line))
        .where(Detour.id == detour_id, Detour.status == DetourStatus.ACTIVE)
    )
    detour = db.execute(stmt).scalars().first()
    if detour is None:
        raise HTTPException(status_code=404, detail="Detour not found or not active")
    detour.last_confirmed_at = datetime.utcnow()
    detour.confirmed_count += 1
    db.commit()
    db.refresh(detour)
    return DetourRead.model_validate(detour)


@router.post("/cleanup")
def cleanup_expired_detours(db: Session = Depends(get_db)) -> dict:
    """Expire detours not confirmed in the last 7 days."""
    cutoff = datetime.utcnow() - timedelta(days=7)
    stmt = (
        update(Detour)
        .where(
            Detour.status == DetourStatus.ACTIVE,
            Detour.last_confirmed_at < cutoff,
        )
        .values(status=DetourStatus.EXPIRED)
    )
    result = db.execute(stmt)
    db.commit()
    return {"expired_count": result.rowcount}
