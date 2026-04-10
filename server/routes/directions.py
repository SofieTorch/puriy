import logging
from uuid import UUID

from database.models.detour import Detour, DetourStatus
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from database.connection import get_db
from geodata.transit_graph import (
    build_transit_graph,
    find_route,
    get_or_build_graph,
    invalidate_graph,
)
from geodata.walk_route import walk_route
from schemas.directions import (
    DetourAlert,
    DirectionsLeg,
    DirectionsRequest,
    DirectionsResponse,
    GraphRebuildResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/directions", tags=["directions"])


@router.post("/", response_model=DirectionsResponse)
def get_directions(
    req: DirectionsRequest,
    db: Session = Depends(get_db),
) -> DirectionsResponse:
    """Find a multi-modal transit route between two points."""
    origin = tuple(req.origin)
    destination = tuple(req.destination)

    graph = get_or_build_graph(db)

    route = find_route(
        graph,
        origin,
        destination,
        include_pending_lines=req.include_pending_lines,
        include_pending_routes=req.include_pending_routes,
    )
    if route is None:
        raise HTTPException(status_code=404, detail="No route found")

    legs: list[DirectionsLeg] = []
    for leg in route:
        geometry = leg["geometry"]

        # For walking legs, get accurate geometry from Valhalla
        if leg["mode"] == "walk":
            try:
                walk = walk_route(leg["from_coord"], leg["to_coord"])
                geometry = [list(c) for c in walk.coords]
                leg["distance_m"] = walk.distance_m
                leg["duration_s"] = walk.duration_s
            except Exception:
                logger.warning(
                    "Valhalla walking route failed, using straight-line geometry",
                    exc_info=True,
                )
                # Fall back to graph geometry (straight line)
                geometry = [list(c) for c in geometry]

        directions_leg = DirectionsLeg(
            mode=leg["mode"],
            line_name=leg["line_name"],
            line_id=str(leg["line_id"]) if leg["line_id"] else None,
            geometry=geometry,
            distance_m=leg["distance_m"],
            duration_s=leg["duration_s"],
        )

        if leg["mode"] == "bus" and leg["line_id"]:
            detour = db.execute(
                select(Detour).where(
                    Detour.line_id == UUID(str(leg["line_id"])),
                    Detour.status == DetourStatus.ACTIVE,
                )
            ).scalars().first()
            if detour:
                try:
                    from services.detour_analysis import analyze_detour
                    analysis = analyze_detour(db, detour.path, UUID(str(leg["line_id"])))
                except Exception:
                    analysis = None
                directions_leg.detour_alert = DetourAlert.from_detour(detour, analysis)

        legs.append(directions_leg)

    total_distance_m = sum(leg.distance_m for leg in legs)
    total_duration_s = sum(leg.duration_s for leg in legs)

    return DirectionsResponse(
        legs=legs,
        total_distance_m=total_distance_m,
        total_duration_s=total_duration_s,
    )


@router.post("/graph/rebuild", response_model=GraphRebuildResponse)
def rebuild_graph(db: Session = Depends(get_db)) -> GraphRebuildResponse:
    """Rebuild the transit graph from scratch."""
    invalidate_graph()
    graph = build_transit_graph(db)

    bus_edges = 0
    transfer_edges = 0
    line_ids: set[str] = set()

    for edges in graph.adjacency.values():
        for edge in edges:
            if edge.mode == "bus":
                bus_edges += 1
                if edge.line_id:
                    line_ids.add(str(edge.line_id))
            else:
                transfer_edges += 1

    return GraphRebuildResponse(
        nodes=len(graph.nodes),
        bus_edges=bus_edges,
        transfer_edges=transfer_edges,
        lines=len(line_ids),
    )
