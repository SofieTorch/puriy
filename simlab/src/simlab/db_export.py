"""Export a simulated scenario's traces into the database as raw recordings.

Writes one ``TripSession`` + ``TripSessionPoint``s per generated trip, under
``sim:*`` devices (provenance isolation by device id), on a chosen or freshly
created ``Line``. The traces go in *raw* — the production pipeline
(``clean_traces`` → ``reconstruct_routes``) then processes them exactly like
mobile uploads, so the new reconstruction (e.g. the routebuilder strategy) can
be exercised end-to-end from simlab. No ground-truth geometry is stored: the
Line is just a container, and everything in the DB is raw.
"""

from __future__ import annotations

import random
from pathlib import Path
from uuid import UUID

from geoalchemy2.shape import from_shape
from shapely.geometry import Point
from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import (
    Device,
    Line,
    LineStatus,
    LineType,
    ProcessingStatus,
    SessionStatus,
    TripSession,
    TripSessionPoint,
)

from .scenario import ScenarioConfig
from .sim.fares import simulate_fares
from .sim.gps import simulate_trip_points
from .sim.personas import build_personas, form_voters, generate_trip_history
from .sim.route import load_route

# simlab/src/simlab/db_export.py → parents[3] is the repo root (matches runner).
REPO_ROOT = Path(__file__).resolve().parents[3]


def _generate_trips(config: ScenarioConfig, rng: random.Random):
    """(trip, gps_points) for every generated trip — the same generation the
    runner's simulate stage uses, so DB-mode matches scenario mode."""
    routes = {
        spec.name: load_route(config.resolve_path(spec.path, REPO_ROOT))
        for spec in config.routes
    }
    rideable = {
        spec.name: routes[spec.name]
        for spec in config.routes if spec.role != "detour"
    }
    personas = build_personas(config)
    trips = generate_trip_history(personas, rideable, config, rng)
    form_voters(trips, rideable, config, rng)
    noise_mult = {spec.name: spec.noise_multiplier for spec in config.personas}

    out = []
    for trip in trips:
        points = simulate_trip_points(
            trip, rideable[trip.route_name], config, rng,
            noise_multiplier=noise_mult.get(trip.persona_name, 1.0),
        )
        if len(points) >= 2:
            out.append((trip, points))
    # Crowdsourced fare reports for the kept trips (same generation as the
    # runner's fares stage) — written to the DB so the fare pipeline can
    # resolve zones and estimate per-line fares.
    fare_reports = simulate_fares([t for t, _ in out], rideable, config, rng)
    return out, fare_reports


def export_scenario_to_db(
    config: ScenarioConfig,
    db: Session,
    *,
    line_id: UUID | None = None,
    line_name: str | None = None,
    line_type: LineType | None = None,
) -> dict:
    """Materialize a scenario's traces into the DB as raw sessions.

    ``line_id`` targets an existing line; otherwise a new APPROVED line is
    created (named ``line_name`` or the scenario name). ``line_type`` (micro /
    trufi / taxi_trufi) is recorded on a newly-created line and drives the fare
    rule downstream (trufi = zone-based, micro = flat). Returns a summary.
    """
    rng = random.Random(config.seed)
    trips, fare_reports = _generate_trips(config, rng)
    if not trips:
        return {"error": "no trips generated", "sessions": 0, "points": 0}

    if line_id is not None:
        line = db.get(Line, line_id)
        if line is None:
            raise ValueError(f"line {line_id} not found")
    else:
        line = Line(
            name=line_name or config.name,
            status=LineStatus.APPROVED,
            line_type=line_type,
        )
        db.add(line)
        db.flush()

    # Devices: one per distinct sim device id (already ``sim:*`` from the
    # simulator — provenance isolation comes for free).
    existing = {row[0] for row in db.execute(select(Device.id)).all()}
    for device_id in {trip.device_id for trip, _ in trips}:
        if device_id not in existing:
            db.add(Device(id=device_id))
            existing.add(device_id)
    db.flush()

    n_points = 0
    for trip, points in trips:
        session = TripSession(
            line_id=line.id,
            device_id=trip.device_id,
            status=SessionStatus.COMPLETED,
            processing_status=ProcessingStatus.RAW,
            started_at=points[0].timestamp,
            ended_at=points[-1].timestamp,
            last_activity_at=points[-1].timestamp,
            notes=f"simlab:{config.name}",
        )
        db.add(session)
        db.flush()
        for p in points:
            db.add(TripSessionPoint(
                session_id=session.id,
                timestamp=p.timestamp,
                latitude=p.lat,
                longitude=p.lon,
                point=from_shape(Point(p.lon, p.lat), srid=4326),
            ))
            n_points += 1
    # Fare reports (raw — zones resolved later by the resolve_fares step).
    from database.models import FareReport, FareSource
    n_fares = 0
    for r in fare_reports:
        if r.device_id not in existing:
            db.add(Device(id=r.device_id))
            existing.add(r.device_id)
        db.add(FareReport(
            line_id=line.id,
            device_id=r.device_id,
            amount_bob=r.amount_bob,
            boarding_latitude=r.boarding_lat,
            boarding_longitude=r.boarding_lon,
            alighting_latitude=r.alighting_lat,
            alighting_longitude=r.alighting_lon,
            source=FareSource.REGISTRATION,
        ))
        n_fares += 1
    db.commit()

    return {
        "line_id": str(line.id),
        "line_name": line.name,
        "sessions": len(trips),
        "points": n_points,
        "devices": len({trip.device_id for trip, _ in trips}),
        "fare_reports": n_fares,
    }
