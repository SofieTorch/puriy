from typing import Optional, Sequence
from uuid import UUID

from database.models.detour import Detour, DetourStatus
from database.models.line import Line, LineStatus
from database.models.route import Route, RouteEdge, RouteStatus
from database.models.trip import TripSession
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from geoalchemy2 import Geography, WKBElement
from shapely import wkb
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from database.connection import get_db
from schemas.directions import DetourAlert
from schemas.line import LineCreate, LineRead, LineUpdate, NearbyLineWithRouteRead
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


@router.get("/nearby/", response_model=list[NearbyLineWithRouteRead])
def find_lines_nearby(
    longitude: float = Query(..., description="Longitude of the point"),
    latitude: float = Query(..., description="Latitude of the point"),
    radius_meters: float = Query(default=500, ge=10, le=5000, description="Search radius in meters"),
    include_pending: bool = Query(default=False, description="Include pending (unapproved) lines and unconfirmed routes"),
    db: Session = Depends(get_db),
) -> list[NearbyLineWithRouteRead]:
    """Find lines whose routes pass within radius of a point, with route geometry."""
    point = func.ST_GeomFromEWKT(f"SRID=4326;POINT({longitude} {latitude})")

    allowed_line_statuses = [LineStatus.APPROVED]
    if include_pending:
        allowed_line_statuses.append(LineStatus.PENDING)

    allowed_route_statuses = [RouteStatus.CONFIRMED]
    if include_pending:
        allowed_route_statuses.append(RouteStatus.PENDING)

    # Find distinct lines with edges near the point
    line_ids = (
        db.execute(
            select(Line.id)
            .distinct()
            .join(Route, Route.line_id == Line.id)
            .join(RouteEdge, RouteEdge.route_id == Route.id)
            .where(
                Line.status.in_(allowed_line_statuses),
                Route.status.in_(allowed_route_statuses),
                func.ST_DWithin(
                    func.cast(RouteEdge.path, Geography),
                    func.cast(point, Geography),
                    radius_meters,
                ),
            )
        )
        .scalars()
        .all()
    )

    # Batch-fetch active detours for all matching lines
    active_detours = (
        db.execute(
            select(Detour).where(
                Detour.line_id.in_(line_ids),
                Detour.status == DetourStatus.ACTIVE,
            )
        )
        .scalars()
        .all()
    )
    detour_by_line = {d.line_id: d for d in active_detours}
    import logging
    logging.getLogger(__name__).info("Nearby: line_ids=%s, active_detours=%d, detour_by_line_keys=%s", line_ids, len(active_detours), list(detour_by_line.keys()))

    results: list[NearbyLineWithRouteRead] = []
    for line_id in line_ids:
        line = db.get(Line, line_id)
        if not line:
            continue

        # Get the active route's edges in order
        route = db.execute(
            select(Route)
            .where(Route.line_id == line_id, Route.status != RouteStatus.SUPERSEDED)
            .order_by(Route.version.desc())
        ).scalars().first()

        route_geojson = None
        if route:
            edges = (
                db.execute(
                    select(RouteEdge)
                    .where(RouteEdge.route_id == route.id)
                    .order_by(RouteEdge.sequence)
                )
                .scalars()
                .all()
            )
            all_coords: list[list[float]] = []
            for edge in edges:
                if edge.path is not None:
                    if isinstance(edge.path, WKBElement):
                        shape = wkb.loads(bytes(edge.path.data))
                        coords = [list(c) for c in shape.coords]
                        if all_coords and coords:
                            all_coords.extend(coords[1:])
                        else:
                            all_coords.extend(coords)

            if len(all_coords) >= 2:
                route_geojson = {
                    "type": "LineString",
                    "coordinates": all_coords,
                }

        detour = detour_by_line.get(line.id)
        detour_alert = None
        if detour:
            analysis = None
            try:
                from services.detour_analysis import analyze_detour
                analysis = analyze_detour(db, detour.path, line.id)
            except Exception:
                import traceback
                traceback.print_exc()
            detour_alert = DetourAlert.from_detour(detour, analysis).model_dump()

        results.append(
            NearbyLineWithRouteRead(
                line_id=line.id,
                line_name=line.name,
                line_description=line.description,
                route_geojson=route_geojson,
                detour_alert=detour_alert,
            )
        )

    return results


@router.get("/{line_id}/route")
def get_line_route(line_id: UUID, db: Session = Depends(get_db)) -> dict:
    """Get the active route geometry for a line as GeoJSON."""
    line = db.get(Line, line_id)
    if not line:
        raise HTTPException(status_code=404, detail="Line not found")

    from services.detour_analysis import get_line_route_geometry

    route_geom = get_line_route_geometry(db, line_id)
    if not route_geom:
        raise HTTPException(status_code=404, detail="No active route for this line")

    return {
        "type": "Feature",
        "properties": {"line_id": str(line.id), "line_name": line.name},
        "geometry": {
            "type": "LineString",
            "coordinates": [list(c) for c in route_geom.coords],
        },
    }


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
