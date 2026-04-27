"""Voting endpoints — let users approve/reject route edges they've traveled."""

from uuid import UUID

from database.connection import get_db
from database.models.line import Line, LineVote
from database.models.route import (
    EdgeVote,
    Route,
    RouteEdge,
    RouteStatus,
    Trip,
    VoteChoice,
)
from database.models.trip import TripSession
from fastapi import APIRouter, Depends, HTTPException, Query
from geoalchemy2 import WKBElement
from shapely import wkb
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from schemas.voting import (
    LineVoteRequest,
    LineVoteResponse,
    NearbyLineRead,
    PendingLineRead,
    VoteableEdgeRead,
    VoteableSegmentRead,
    VoteRequest,
    VoteResponse,
)
from geodata.edge_overlap import (
    DEFAULT_MIN_TRIPS,
    count_device_trips_for_line,
    find_lines_near_device_trips,
    find_overlapping_edges,
    find_unvoted_overlapping_edges,
    get_active_route,
    get_device_trips_for_line,
)

router = APIRouter(prefix="/vote", tags=["voting"])


@router.get("/pending", response_model=list[PendingLineRead])
def list_pending_votes(
    device_id: str = Query(..., description="Device identifier"),
    min_trips: int = Query(
        default=DEFAULT_MIN_TRIPS,
        ge=1,
        description="Minimum cleaned trips required before a device can vote on a line.",
    ),
    db: Session = Depends(get_db),
) -> list[PendingLineRead]:
    """List lines where this device has enough trips and un-voted route edges."""

    # Find all lines where this device has cleaned trips
    line_ids = (
        db.execute(
            select(Trip.line_id)
            .distinct()
            .join(TripSession, Trip.session_id == TripSession.id)
            .where(
                TripSession.device_id == device_id,
                Trip.computed_path.isnot(None),
            )
        )
        .scalars()
        .all()
    )

    results: list[PendingLineRead] = []
    for line_id in line_ids:
        # Skip lines where the device hasn't traveled enough
        trip_count = count_device_trips_for_line(db, device_id, line_id)
        if trip_count < min_trips:
            continue

        route = get_active_route(db, line_id)
        if not route:
            continue

        trips = get_device_trips_for_line(db, device_id, line_id)
        trip_ids = [t.id for t in trips]

        unvoted_edges = find_unvoted_overlapping_edges(
            db, route.id, trip_ids, device_id
        )
        if not unvoted_edges:
            continue

        line = db.get(Line, line_id)
        total_edges = len(route.edges)

        results.append(
            PendingLineRead(
                line_id=line_id,
                line_name=line.name,
                line_description=line.description,
                route_id=route.id,
                pending_edge_count=len(unvoted_edges),
                total_edge_count=total_edges,
            )
        )

    return results


@router.get("/{line_id}/segment", response_model=VoteableSegmentRead)
def get_voteable_segment(
    line_id: UUID,
    device_id: str = Query(..., description="Device identifier"),
    min_trips: int = Query(
        default=DEFAULT_MIN_TRIPS,
        ge=1,
        description="Minimum cleaned trips required before a device can vote on a line.",
    ),
    db: Session = Depends(get_db),
) -> VoteableSegmentRead:
    """Get the voteable segment for a line — edges overlapping with this device's trips."""

    line = db.get(Line, line_id)
    if not line:
        raise HTTPException(status_code=404, detail="Line not found")

    route = get_active_route(db, line_id)
    if not route:
        raise HTTPException(status_code=404, detail="No active route for this line")

    trip_count = count_device_trips_for_line(db, device_id, line_id)
    if trip_count < min_trips:
        raise HTTPException(
            status_code=403,
            detail=f"Not enough trips to vote ({trip_count}/{min_trips}). Keep recording!",
        )

    trips = get_device_trips_for_line(db, device_id, line_id)
    if not trips:
        raise HTTPException(
            status_code=404,
            detail="No cleaned trips found for this device on this line",
        )

    trip_ids = [t.id for t in trips]
    edges = find_unvoted_overlapping_edges(
        db, route.id, trip_ids, device_id
    )

    # Build a MultiLineString GeoJSON from edge geometries
    coordinates = []
    for edge in edges:
        if edge.path is not None:
            if isinstance(edge.path, WKBElement):
                shape = wkb.loads(bytes(edge.path.data))
                coordinates.append([list(c) for c in shape.coords])

    segment_geojson = None
    if coordinates:
        segment_geojson = {
            "type": "Feature",
            "properties": {"line_name": line.name, "route_id": str(route.id)},
            "geometry": {
                "type": "MultiLineString",
                "coordinates": coordinates,
            },
        }

    return VoteableSegmentRead(
        route_id=route.id,
        line_name=line.name,
        line_description=line.description,
        edges=[VoteableEdgeRead.model_validate(e) for e in edges],
        segment_geojson=segment_geojson,
    )


@router.post("/{line_id}", response_model=VoteResponse, status_code=201)
def submit_vote(
    line_id: UUID,
    vote_req: VoteRequest,
    min_trips: int = Query(
        default=DEFAULT_MIN_TRIPS,
        ge=1,
        description="Minimum cleaned trips required before a device can vote on a line.",
    ),
    db: Session = Depends(get_db),
) -> VoteResponse:
    """Submit a vote (approve/reject) for all overlapping edges on this line."""

    line = db.get(Line, line_id)
    if not line:
        raise HTTPException(status_code=404, detail="Line not found")

    route = get_active_route(db, line_id)
    if not route:
        raise HTTPException(status_code=404, detail="No active route for this line")

    trip_count = count_device_trips_for_line(db, vote_req.device_id, line_id)
    if trip_count < min_trips:
        raise HTTPException(
            status_code=403,
            detail=f"Not enough trips to vote ({trip_count}/{min_trips}). Keep recording!",
        )

    trips = get_device_trips_for_line(db, vote_req.device_id, line_id)
    if not trips:
        raise HTTPException(
            status_code=404,
            detail="No cleaned trips found for this device on this line",
        )

    trip_ids = [t.id for t in trips]
    edges = find_overlapping_edges(db, route.id, trip_ids)

    if not edges:
        raise HTTPException(
            status_code=404,
            detail="No route edges overlap with this device's trips",
        )

    voted_count = 0
    for edge in edges:
        # Check if vote already exists (unique constraint)
        existing = db.execute(
            select(EdgeVote).where(
                EdgeVote.edge_id == edge.id,
                EdgeVote.device_id == vote_req.device_id,
            )
        ).scalar_one_or_none()

        if existing:
            # Update existing vote if changed
            if existing.vote != vote_req.vote:
                # Adjust counters
                if existing.vote == VoteChoice.APPROVE:
                    edge.votes_for = max(0, edge.votes_for - 1)
                else:
                    edge.votes_against = max(0, edge.votes_against - 1)

                existing.vote = vote_req.vote

                if vote_req.vote == VoteChoice.APPROVE:
                    edge.votes_for += 1
                else:
                    edge.votes_against += 1
        else:
            db.add(
                EdgeVote(
                    edge_id=edge.id,
                    device_id=vote_req.device_id,
                    vote=vote_req.vote,
                )
            )
            if vote_req.vote == VoteChoice.APPROVE:
                edge.votes_for += 1
            else:
                edge.votes_against += 1

        voted_count += 1

    db.commit()

    return VoteResponse(
        edges_voted=voted_count,
        vote=vote_req.vote,
    )


# ---------------------------------------------------------------------------
# Line familiarity voting
# ---------------------------------------------------------------------------


@router.get("/lines/nearby", response_model=list[NearbyLineRead])
def list_nearby_lines(
    device_id: str = Query(..., description="Device identifier"),
    radius_meters: float = Query(
        default=200.0,
        ge=10,
        description="Search radius in meters around trip paths.",
    ),
    db: Session = Depends(get_db),
) -> list[NearbyLineRead]:
    """List lines near this device's trips that haven't been voted on yet."""
    lines = find_lines_near_device_trips(db, device_id, radius_meters)

    return [
        NearbyLineRead(
            line_id=ln.id,
            line_name=ln.name,
            line_description=ln.description,
        )
        for ln in lines
    ]


@router.post("/lines/{line_id}", response_model=LineVoteResponse, status_code=201)
def submit_line_vote(
    line_id: UUID,
    vote_req: LineVoteRequest,
    db: Session = Depends(get_db),
) -> LineVoteResponse:
    """Submit a familiarity vote on a line (approve = 'I know this line')."""
    line = db.get(Line, line_id)
    if not line:
        raise HTTPException(status_code=404, detail="Line not found")

    existing = db.execute(
        select(LineVote).where(
            LineVote.line_id == line_id,
            LineVote.device_id == vote_req.device_id,
        )
    ).scalar_one_or_none()

    if existing:
        existing.vote = vote_req.vote
    else:
        db.add(
            LineVote(
                line_id=line_id,
                device_id=vote_req.device_id,
                vote=vote_req.vote,
            )
        )

    db.commit()

    return LineVoteResponse(line_id=line_id, vote=vote_req.vote)
