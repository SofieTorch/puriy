import json
from typing import Optional, Sequence

from database.models.line import Line, LineStatus
from database.models.recording import RecordingSession
from fastapi import APIRouter, Depends, HTTPException, Query
from geoalchemy2.functions import ST_AsGeoJSON
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from database.connection import get_db
from schemas.line import LineCreate, LineRead, LineUpdate, path_to_linestring

router = APIRouter(prefix="/lines", tags=["lines"])


@router.post("/", response_model=LineRead, status_code=201)
def create_line(line_data: LineCreate, db: Session = Depends(get_db)) -> LineRead:
    """
    Create a new transit line.

    Path is optional; new lines (e.g. from recordings) often have no path yet.
    A daily cron job computes line paths from recording geopoints.
    """
    path_wkt = path_to_linestring(line_data.path) if line_data.path else None

    line = Line(
        name=line_data.name,
        description=line_data.description,
        path=path_wkt,
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
def get_line(line_id: int, db: Session = Depends(get_db)) -> LineRead:
    """Get a specific line by ID."""
    line = db.get(Line, line_id)
    if not line:
        raise HTTPException(status_code=404, detail="Line not found")
    return LineRead.model_validate(line)


@router.patch("/{line_id}", response_model=LineRead)
def update_line(
    line_id: int,
    line_data: LineUpdate,
    db: Session = Depends(get_db)
) -> LineRead:
    """Update an existing line."""
    line = db.get(Line, line_id)
    if not line:
        raise HTTPException(status_code=404, detail="Line not found")

    update_data = line_data.model_dump(exclude_unset=True)

    if "path" in update_data:
        path_wkt = path_to_linestring(update_data.pop("path"))
        line.path = path_wkt

    for key, value in update_data.items():
        setattr(line, key, value)

    db.add(line)
    db.commit()
    db.refresh(line)
    return LineRead.model_validate(line)


@router.delete("/{line_id}", status_code=204)
def delete_line(line_id: int, db: Session = Depends(get_db)) -> None:
    """Delete a line."""
    line = db.get(Line, line_id)
    if not line:
        raise HTTPException(status_code=404, detail="Line not found")
    db.delete(line)
    db.commit()


@router.get("/{line_id}/geojson")
def get_line_geojson(line_id: int, db: Session = Depends(get_db)) -> dict:
    """Get line path as GeoJSON Feature."""
    line = db.get(Line, line_id)
    if not line:
        raise HTTPException(status_code=404, detail="Line not found")

    if line.path is None:
        raise HTTPException(status_code=404, detail="Line has no path defined")

    result = db.execute(
        select(ST_AsGeoJSON(Line.path)).where(Line.id == line_id)
    ).scalar_one()

    return {
        "type": "Feature",
        "properties": {
            "id": line.id,
            "name": line.name,
        },
        "geometry": json.loads(result)
    }


@router.get("/nearby/", response_model=list[LineRead])
def find_lines_nearby(
    longitude: float,
    latitude: float,
    radius_meters: float = 1000,
    db: Session = Depends(get_db)
) -> Sequence[LineRead]:
    """Find lines with paths within a given radius of a point."""
    point = f"SRID=4326;POINT({longitude} {latitude})"

    query = select(Line).where(
        Line.path.isnot(None),
        func.ST_DWithin(
            func.ST_Transform(Line.path, 3857),
            func.ST_Transform(func.ST_GeomFromEWKT(point), 3857),
            radius_meters
        )
    )

    lines = db.execute(query).scalars().all()
    return [LineRead.model_validate(ln) for ln in lines]


@router.post("/{line_id}/merge/{target_line_id}", response_model=LineRead)
def merge_line(
    line_id: int,
    target_line_id: int,
    db: Session = Depends(get_db)
) -> LineRead:
    """
    Merge a line into another line (admin operation).

    All recordings from line_id will be moved to target_line_id.
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
        update(RecordingSession)
        .where(RecordingSession.line_id == line_id)
        .values(line_id=target_line_id)
    )

    source.status = LineStatus.MERGED
    source.merged_into_id = target_line_id

    db.commit()
    db.refresh(target)

    return LineRead.model_validate(target)


@router.post("/{line_id}/approve", response_model=LineRead)
def approve_line(line_id: int, db: Session = Depends(get_db)) -> LineRead:
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
