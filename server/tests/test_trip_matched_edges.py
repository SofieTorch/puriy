from datetime import datetime, timedelta

import database.connection as database_connection
import geodata.match as match_module
from geodata.evaluate import load_reconstruction_traces_from_db
from geodata.match import _TraceOutput, match_session
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from database.models import Trip, TripMatchedEdge, TripPoint, TripSession, TripSessionPoint
from database.models.line import Line


def _add_session_points(db: Session, session: TripSession, coordinates: list[tuple[float, float]]) -> None:
    start = datetime.utcnow()
    for index, (lon, lat) in enumerate(coordinates):
        db.add(
            TripSessionPoint(
                session_id=session.id,
                timestamp=start + timedelta(seconds=index * 5),
                latitude=lat,
                longitude=lon,
                point=func.ST_GeomFromEWKT(f"SRID=4326;POINT({lon} {lat})"),
            )
        )
    db.commit()


def test_match_session_persists_trip_matched_edges(
    db: Session,
    completed_recording: TripSession,
    monkeypatch,
) -> None:
    _add_session_points(
        db,
        completed_recording,
        [
            (-66.1500, -17.3900),
            (-66.1495, -17.3895),
            (-66.1490, -17.3890),
        ],
    )

    def fake_trace_match(
        points,
        *,
        trace_id=None,
        costing="bus",
        search_radius=60,
        gps_accuracy=20,
    ):
        return _TraceOutput(
            shape_coords=[],
            edges=[
                {"id": 101, "forward": True},
                {"id": 101, "forward": True},
                {"id": 202, "forward": False},
            ],
            matched_points=[
                {"type": "matched", "lon": -66.1500, "lat": -17.3900, "distance_from_trace_point": 3.0},
                {"type": "matched", "lon": -66.1495, "lat": -17.3895, "distance_from_trace_point": 4.0},
                {"type": "matched", "lon": -66.1490, "lat": -17.3890, "distance_from_trace_point": 5.0},
            ],
            match_score=1.0,
            mean_snap_distance=4.0,
        )

    monkeypatch.setattr(match_module, "trace_match", fake_trace_match)

    result = match_session(db, completed_recording.id)

    trip = db.get(Trip, result.trip.id)
    assert trip is not None

    matched_edges = (
        db.execute(
            select(TripMatchedEdge)
            .where(TripMatchedEdge.trip_id == trip.id)
            .order_by(TripMatchedEdge.sequence)
        )
        .scalars()
        .all()
    )
    trip_points = (
        db.execute(
            select(TripPoint)
            .where(TripPoint.trip_id == trip.id)
            .order_by(TripPoint.point_index)
        )
        .scalars()
        .all()
    )

    assert len(trip_points) == 3
    assert [(edge.sequence, edge.valhalla_edge_id, edge.forward) for edge in matched_edges] == [
        (0, 101, True),
        (1, 101, True),
        (2, 202, False),
    ]


def test_load_reconstruction_traces_from_db_includes_matched_edges(
    db: Session,
    completed_recording: TripSession,
    approved_line: Line,
    monkeypatch,
) -> None:
    trip = Trip(session_id=completed_recording.id, line_id=approved_line.id)
    db.add(trip)
    db.flush()

    point_time = datetime.utcnow()
    db.add(
        TripPoint(
            trip_id=trip.id,
            point_index=0,
            timestamp=point_time,
            latitude=-17.3900,
            longitude=-66.1500,
            point=func.ST_GeomFromEWKT("SRID=4326;POINT(-66.150 -17.390)"),
        )
    )
    db.add(
        TripPoint(
            trip_id=trip.id,
            point_index=1,
            timestamp=point_time + timedelta(seconds=5),
            latitude=-17.3895,
            longitude=-66.1495,
            point=func.ST_GeomFromEWKT("SRID=4326;POINT(-66.1495 -17.3895)"),
        )
    )
    db.add(TripMatchedEdge(trip_id=trip.id, sequence=0, valhalla_edge_id=303, forward=True))
    db.add(TripMatchedEdge(trip_id=trip.id, sequence=1, valhalla_edge_id=404, forward=False))
    db.commit()

    monkeypatch.setattr(database_connection, "SessionLocal", lambda: db)

    traces = load_reconstruction_traces_from_db(
        line_id=approved_line.id,
        trace_source="cleaned",
    )

    assert len(traces) == 1
    assert traces[0].matched_edges is not None
    assert [
        (edge.sequence, edge.valhalla_edge_id, edge.forward)
        for edge in traces[0].matched_edges
    ] == [
        (0, 303, True),
        (1, 404, False),
    ]


def test_load_reconstruction_traces_from_db_handles_legacy_trips_without_matched_edges(
    db: Session,
    completed_recording: TripSession,
    approved_line: Line,
    monkeypatch,
) -> None:
    trip = Trip(session_id=completed_recording.id, line_id=approved_line.id)
    db.add(trip)
    db.flush()

    point_time = datetime.utcnow()
    db.add(
        TripPoint(
            trip_id=trip.id,
            point_index=0,
            timestamp=point_time,
            latitude=-17.3900,
            longitude=-66.1500,
            point=func.ST_GeomFromEWKT("SRID=4326;POINT(-66.150 -17.390)"),
        )
    )
    db.add(
        TripPoint(
            trip_id=trip.id,
            point_index=1,
            timestamp=point_time + timedelta(seconds=5),
            latitude=-17.3895,
            longitude=-66.1495,
            point=func.ST_GeomFromEWKT("SRID=4326;POINT(-66.1495 -17.3895)"),
        )
    )
    db.commit()

    monkeypatch.setattr(database_connection, "SessionLocal", lambda: db)

    traces = load_reconstruction_traces_from_db(
        line_id=approved_line.id,
        trace_source="cleaned",
    )

    assert len(traces) == 1
    assert traces[0].matched_edges is None
    assert len(traces[0].points) == 2
