"""Optional DB persistence: push simulated data into the real models.

Lets the actual server/pipeline run against simulated devices, trips
and votes — useful to demo the production stack without field data.
Everything created here is tagged (device_model="simulator", device
ids prefixed "sim:") so it can be identified and wiped.
"""

from __future__ import annotations

from uuid import UUID

from database.models import (
    Device,
    EdgeVote,
    FareReport,
    Line,
    LineStatus,
    ProcessingStatus,
    Route,
    RouteEdge,
    SessionStatus,
    TripSession,
    TripSessionPoint,
    VoteChoice,
)
from geoalchemy2.shape import from_shape
from shapely.geometry import LineString, Point
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..sim.fares import FareReport as SimFareReport
from ..sim.personas import SimTrip
from ..sim.votes import VotingOutcome


def ensure_line(db: Session, name: str) -> Line:
    line = db.execute(select(Line).where(Line.name == name)).scalars().first()
    if line is None:
        line = Line(name=name, status=LineStatus.PENDING)
        db.add(line)
        db.flush()
    return line


def ensure_device(db: Session, device_id: str) -> Device:
    device = db.get(Device, device_id)
    if device is None:
        device = Device(id=device_id, platform=None)
        db.add(device)
        db.flush()
    return device


def persist_trips(db: Session, line_id: UUID, trips: list[SimTrip]) -> list[TripSession]:
    """Simulated trips → TripSession + TripSessionPoint rows (RAW),
    ready for the real clean_traces pipeline step."""
    sessions: list[TripSession] = []
    for trip in trips:
        if len(trip.points) < 2:
            continue
        ensure_device(db, trip.device_id)
        coords = [(p.lon, p.lat) for p in trip.points]
        session = TripSession(
            line_id=line_id,
            device_id=trip.device_id,
            device_model="simulator",
            status=SessionStatus.COMPLETED,
            processing_status=ProcessingStatus.RAW,
            started_at=trip.points[0].timestamp,
            ended_at=trip.points[-1].timestamp,
            last_activity_at=trip.points[-1].timestamp,
            computed_path=from_shape(LineString(coords), srid=4326),
            notes=f"simlab trip {trip.trip_id}",
        )
        db.add(session)
        db.flush()
        for point in trip.points:
            db.add(TripSessionPoint(
                session_id=session.id,
                timestamp=point.timestamp,
                latitude=point.lat,
                longitude=point.lon,
                point=from_shape(Point(point.lon, point.lat), srid=4326),
            ))
        sessions.append(session)
    db.flush()
    return sessions


def persist_votes(db: Session, route: Route, outcome: VotingOutcome) -> int:
    """Simulated vote events → EdgeVote rows + RouteEdge tallies."""
    edges_by_key: dict[tuple[int, bool], RouteEdge] = {
        (e.valhalla_edge_id, e.forward): e
        for e in db.execute(
            select(RouteEdge).where(RouteEdge.route_id == route.id)
        ).scalars()
        if e.valhalla_edge_id is not None
    }
    created = 0
    for vote in outcome.votes:
        edge = edges_by_key.get((vote.edge_id, vote.forward))
        if edge is None:
            continue
        ensure_device(db, vote.device_id)
        existing = db.execute(
            select(EdgeVote).where(
                EdgeVote.edge_id == edge.id, EdgeVote.device_id == vote.device_id
            )
        ).scalars().first()
        if existing is not None:
            continue
        db.add(EdgeVote(
            edge_id=edge.id,
            device_id=vote.device_id,
            vote=VoteChoice.APPROVE if vote.approve else VoteChoice.REJECT,
        ))
        if vote.approve:
            edge.votes_for += 1
        else:
            edge.votes_against += 1
        created += 1
    db.flush()
    return created


def persist_fares(db: Session, line_id: UUID, reports: list[SimFareReport]) -> int:
    for report in reports:
        ensure_device(db, report.device_id)
        db.add(FareReport(
            line_id=line_id,
            device_id=report.device_id,
            amount_bob=report.amount_bob,
            boarding_latitude=report.boarding_lat,
            boarding_longitude=report.boarding_lon,
            alighting_latitude=report.alighting_lat,
            alighting_longitude=report.alighting_lon,
        ))
    db.flush()
    return len(reports)
