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
            line_uuid = UUID(str(leg["line_id"]))

            # Estimate fare for this leg using boarding/alighting endpoints
            # of the leg geometry (lon, lat order in the graph).
            from services.line_metadata import (
                current_headway_min,
                estimate_fare_bob,
            )

            if geometry and len(geometry) >= 2:
                boarding_lon, boarding_lat = geometry[0][0], geometry[0][1]
                alighting_lon, alighting_lat = geometry[-1][0], geometry[-1][1]
                directions_leg.fare_bob = estimate_fare_bob(
                    db, line_uuid,
                    boarding_lat, boarding_lon,
                    alighting_lat, alighting_lon,
                )

            directions_leg.frequency_min = current_headway_min(db, line_uuid)

            detour = db.execute(
                select(Detour).where(
                    Detour.line_id == line_uuid,
                    Detour.status == DetourStatus.ACTIVE,
                )
            ).scalars().first()
            if detour:
                try:
                    from services.detour_analysis import analyze_detour
                    analysis = analyze_detour(db, detour.path, line_uuid)
                except Exception:
                    analysis = None
                directions_leg.detour_alert = DetourAlert.from_detour(detour, analysis)

        legs.append(directions_leg)

    total_distance_m = sum(leg.distance_m for leg in legs)
    total_duration_s = sum(leg.duration_s for leg in legs)

    # RF-30: total fare is the sum across bus legs; None if *any* bus leg
    # lacks a fare estimate (so we never under-promise the cost).
    bus_legs = [leg for leg in legs if leg.mode == "bus"]
    if bus_legs and all(leg.fare_bob is not None for leg in bus_legs):
        total_fare_bob = round(sum(leg.fare_bob for leg in bus_legs), 2)
    else:
        total_fare_bob = None

    return DirectionsResponse(
        legs=legs,
        total_distance_m=total_distance_m,
        total_duration_s=total_duration_s,
        total_fare_bob=total_fare_bob,
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
