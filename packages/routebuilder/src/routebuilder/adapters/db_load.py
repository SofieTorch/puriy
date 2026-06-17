"""Load matched traces for a line from the existing database models.

Mirrors the query shape of geodata.evaluate.load_reconstruction_traces_from_db,
but produces routebuilder MatchedTrace objects. The database stores no
per-edge geometry (TripMatchedEdge is just edge id + direction), so the
loader recovers geometry by re-matching the trip's cleaned polyline
through Valhalla — cached on disk by trip id, so this is cheap after
the first run (same approach as the old strategy's recover_geometry).
"""

from __future__ import annotations

from uuid import UUID

from database.models import Trip, TripMatchedEdge, TripPoint, TripStatus
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..cleaning import clean_trace
from ..config import CleaningConfig
from ..types import DirectedEdge, MatchedTrace, RawPoint


def load_matched_traces(
    db: Session,
    line_id: UUID,
    *,
    recover_geometry: bool = True,
    cleaning_config: CleaningConfig | None = None,
) -> list[MatchedTrace]:
    """All CLEAN trips of a line as MatchedTraces (ordered points/edges).

    With recover_geometry=True (default, requires Valhalla) each trace
    carries per-edge geometry, which consensus needs for localized
    support and output assembly. Set False only for tests/inspection.
    """
    trips = (
        db.execute(
            select(Trip).where(Trip.line_id == line_id, Trip.status == TripStatus.CLEAN)
        )
        .scalars()
        .all()
    )

    traces: list[MatchedTrace] = []
    for trip in trips:
        points = (
            db.execute(
                select(TripPoint)
                .where(TripPoint.trip_id == trip.id)
                .order_by(TripPoint.point_index)
            )
            .scalars()
            .all()
        )
        if len(points) < 2:
            continue

        device_id = getattr(trip.session, "device_id", None) if trip.session else None

        if recover_geometry:
            # Cleaned points re-match deterministically with a tight
            # radius; the trace cache keys on the trip uuid.
            config = cleaning_config or CleaningConfig(
                search_radius_m=20, gps_accuracy_m=5, min_match_quality=0.0, min_edges=1
            )
            trace = clean_trace(
                str(trip.id),
                [
                    RawPoint(lon=p.longitude, lat=p.latitude, timestamp=p.timestamp)
                    for p in points
                ],
                config,
                device_id=device_id,
            )
            if trace is not None:
                traces.append(trace)
                continue

        edges = (
            db.execute(
                select(TripMatchedEdge)
                .where(TripMatchedEdge.trip_id == trip.id)
                .order_by(TripMatchedEdge.sequence)
            )
            .scalars()
            .all()
        )
        if not edges:
            continue
        directed: list[DirectedEdge] = []
        for edge in edges:
            de = DirectedEdge(int(edge.valhalla_edge_id), bool(edge.forward))
            if directed and directed[-1] == de:
                continue
            directed.append(de)

        traces.append(MatchedTrace(
            trace_id=str(trip.id),
            edges=directed,
            edge_geometries={},
            matched_polyline=[(p.longitude, p.latitude) for p in points],
            match_quality=trip.match_score or 1.0,
            device_id=device_id,
            started_at=points[0].timestamp,
        ))
    return traces
