from typing import Optional, Sequence
from uuid import UUID

from database.models.line import Line, LineStatus
from database.models.trip import TripSession
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from database.connection import get_db
from schemas.line import LineCreate, LineRead, LineUpdate
from schemas.route import RouteRead

router = APIRouter(prefix="/lines", tags=["lines"])


@router.post("/", response_model=LineRead, status_code=201)
def create_line(line_data: LineCreate, db: Session = Depends(get_db)) -> LineRead:
    """Create a new transit line."""
    line = Line(
        name=line_data.name,
        description=line_data.description,
    )
    db.add(line)
    db.commit()
    db.refresh(line)
    return LineRead.model_validate(line)


@router.get("/", response_model=list[LineRead])
def list_lines(
    skip: int = 0,
    limit: int = 100,
    status: Optional[LineStatus] = Query(
        default=LineStatus.APPROVED,
        description="Filter by status. Use 'pending' to see lines awaiting approval."
    ),
    include_all: bool = Query(
        default=False,
        description="If true, return all lines regardless of status (admin use)."
    ),
    db: Session = Depends(get_db)
) -> Sequence[LineRead]:
    """List transit lines. By default, only returns approved lines."""
    query = select(Line)

    if not include_all:
        query = query.where(Line.status == status)

    lines = db.execute(query.offset(skip).limit(limit)).scalars().all()
    return [LineRead.model_validate(ln) for ln in lines]


@router.get("/{line_id}", response_model=LineRead)
def get_line(line_id: UUID, db: Session = Depends(get_db)) -> LineRead:
    """Get a specific line by ID."""
    line = db.get(Line, line_id)
    if not line:
        raise HTTPException(status_code=404, detail="Line not found")
    return LineRead.model_validate(line)


@router.patch("/{line_id}", response_model=LineRead)
def update_line(
    line_id: UUID,
    line_data: LineUpdate,
    db: Session = Depends(get_db)
) -> LineRead:
    """Update an existing line."""
    line = db.get(Line, line_id)
    if not line:
        raise HTTPException(status_code=404, detail="Line not found")

    update_data = line_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(line, key, value)

    db.add(line)
    db.commit()
    db.refresh(line)
    return LineRead.model_validate(line)


@router.delete("/{line_id}", status_code=204)
def delete_line(line_id: UUID, db: Session = Depends(get_db)) -> None:
    """Delete a line."""
    line = db.get(Line, line_id)
    if not line:
        raise HTTPException(status_code=404, detail="Line not found")
    db.delete(line)
    db.commit()


@router.post("/{line_id}/merge/{target_line_id}", response_model=LineRead)
def merge_line(
    line_id: UUID,
    target_line_id: UUID,
    db: Session = Depends(get_db)
) -> LineRead:
    """
    Merge a line into another line (admin operation).

    All trace sessions from line_id will be moved to target_line_id.
    The source line will be marked as MERGED with a reference to the target.
    """
    if line_id == target_line_id:
        raise HTTPException(status_code=400, detail="Cannot merge a line into itself")

    source = db.get(Line, line_id)
    if not source:
        raise HTTPException(status_code=404, detail=f"Source line {line_id} not found")

    target = db.get(Line, target_line_id)
    if not target:
        raise HTTPException(status_code=404, detail=f"Target line {target_line_id} not found")

    if source.status == LineStatus.MERGED:
        raise HTTPException(
            status_code=400,
            detail=f"Source line {line_id} is already merged into line {source.merged_into_id}"
        )

    if target.status == LineStatus.MERGED:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot merge into line {target_line_id} as it is already merged into another line"
        )

    db.execute(
        update(TripSession)
        .where(TripSession.line_id == line_id)
        .values(line_id=target_line_id)
    )

    source.status = LineStatus.MERGED
    source.merged_into_id = target_line_id

    db.commit()
    db.refresh(target)

    return LineRead.model_validate(target)


@router.post("/{line_id}/route/import", response_model=RouteRead, status_code=201)
async def import_route(
    line_id: UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> RouteRead:
    """Import a GeoJSON file as an inferred route with Valhalla edges."""
    from geodata.import_route import import_route_from_geojson

    content = await file.read()
    try:
        geojson_str = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File must be valid UTF-8 encoded GeoJSON")

    try:
        route = import_route_from_geojson(
            db,
            geojson_str,
            line_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    return RouteRead.model_validate(route)


@router.post("/{line_id}/approve", response_model=LineRead)
def approve_line(line_id: UUID, db: Session = Depends(get_db)) -> LineRead:
    """Approve a pending line (admin operation)."""
    line = db.get(Line, line_id)
    if not line:
        raise HTTPException(status_code=404, detail="Line not found")

    if line.status != LineStatus.PENDING:
        raise HTTPException(
            status_code=400,
            detail=f"Line is not pending (current status: {line.status})"
        )

    line.status = LineStatus.APPROVED
    db.commit()
    db.refresh(line)

    return LineRead.model_validate(line)
