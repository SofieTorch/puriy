"""Database-mode API: promote a scenario's traces into the DB, then run the
*production* pipeline (clean_traces → reconstruct_routes) on a real Line and
read back the reconstruction — so the new approach can be tested end-to-end,
through the same code path the live system uses, from simlab."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..scenario import ScenarioConfig

SCENARIOS_DIR = Path(__file__).resolve().parents[3] / "scenarios"

db_router = APIRouter()


def _session():
    from database.connection import SessionLocal
    return SessionLocal()


def _status(value) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _line_status(value: str | None):
    """Coerce a string to LineStatus, defaulting to APPROVED (so the line is
    eligible for reconstruction)."""
    from database.models import LineStatus

    if not value:
        return LineStatus.APPROVED
    try:
        return LineStatus(value)
    except ValueError:
        try:
            return LineStatus[value.upper()]
        except KeyError:
            return LineStatus.APPROVED


# --- promote a scenario into the DB as raw traces ---------------------------

class _PromoteRequest(BaseModel):
    line_id: str | None = None
    line_name: str | None = None


@db_router.post("/scenarios/{scenario_id}/promote")
def promote_scenario(scenario_id: str, body: _PromoteRequest | None = None) -> dict:
    from ..db_export import export_scenario_to_db

    path = SCENARIOS_DIR / f"{scenario_id}.yaml"
    if not path.exists():
        raise HTTPException(404, f"scenario {scenario_id} not found")
    config = ScenarioConfig.from_yaml(path)
    body = body or _PromoteRequest()
    db = _session()
    try:
        return export_scenario_to_db(
            config, db,
            line_id=UUID(body.line_id) if body.line_id else None,
            line_name=body.line_name,
        )
    finally:
        db.close()


# --- lines (the DB explorer / picker) ---------------------------------------

@db_router.get("/lines")
def list_lines() -> list[dict]:
    from sqlalchemy import func, select

    from database.models import Line, Route, RouteStatus, Trip, TripSession

    db = _session()
    try:
        out = []
        lines = db.execute(select(Line).order_by(Line.created_at.desc())).scalars().all()
        for line in lines:
            def count(model, *extra):
                return db.execute(
                    select(func.count(model.id)).where(model.line_id == line.id, *extra)
                ).scalar() or 0
            out.append({
                "id": str(line.id),
                "name": line.name,
                "status": _status(line.status),
                "sessions": count(TripSession),
                "trips": count(Trip),
                "routes": count(Route, Route.status != RouteStatus.SUPERSEDED),
            })
        return out
    finally:
        db.close()


class _NewLine(BaseModel):
    name: str
    status: str | None = None


@db_router.post("/lines")
def create_line(body: _NewLine) -> dict:
    """Create a new (empty) line. Promote a scenario into it later, or use it
    as a container that several scenarios feed."""
    from database.models import Line

    db = _session()
    try:
        line = Line(name=body.name, status=_line_status(body.status))
        db.add(line)
        db.commit()
        db.refresh(line)
        return {"id": str(line.id), "name": line.name, "status": _status(line.status)}
    finally:
        db.close()


class _UpdateLine(BaseModel):
    name: str | None = None
    status: str | None = None


@db_router.patch("/lines/{line_id}")
def update_line(line_id: str, body: _UpdateLine) -> dict:
    """Rename a line and/or change its status."""
    from database.models import Line

    db = _session()
    try:
        line = db.get(Line, UUID(line_id))
        if line is None:
            raise HTTPException(404, f"line {line_id} not found")
        if body.name is not None:
            line.name = body.name
        if body.status is not None:
            line.status = _line_status(body.status)
        db.commit()
        db.refresh(line)
        return {"id": str(line.id), "name": line.name, "status": _status(line.status)}
    finally:
        db.close()


@db_router.delete("/lines/{line_id}")
def delete_line(line_id: str) -> dict:
    """Drop a line and everything under it (sessions, trips, routes). Intended
    for the sim-seeded lines."""
    from sqlalchemy import text

    lid = UUID(line_id)
    db = _session()
    try:
        for stmt in (
            "delete from route_edges where route_id in (select id from routes where line_id=:l)",
            "delete from routes where line_id=:l",
            "delete from trip_points where trip_id in (select id from trips where line_id=:l)",
            "delete from trip_matched_edges where trip_id in (select id from trips where line_id=:l)",
            "delete from travel_time_samples where trip_id in (select id from trips where line_id=:l)",
            "delete from trips where line_id=:l",
            "delete from trip_session_points where session_id in (select id from trip_sessions where line_id=:l)",
            "delete from trip_sensor_readings where session_id in (select id from trip_sessions where line_id=:l)",
            "delete from trip_sessions where line_id=:l",
            "delete from lines where id=:l",
        ):
            db.execute(text(stmt), {"l": lid})
        db.commit()
        return {"deleted": line_id}
    finally:
        db.close()


# --- run the production pipeline on a line ----------------------------------

class _ReconstructRequest(BaseModel):
    strategy: str = "routebuilder_divergence"
    clean: bool = True
    # Valhalla matching params for the clean step. These mirror simlab's own
    # reconstruction *exactly* (routebuilder.cleaning.clean_trace): the scenario
    # sets search_radius_m=8 / gps_accuracy_m=5 and CleaningConfig defaults
    # turn_penalty_factor=300. Since both paths call the same
    # geodata.match.trace_match, identical params -> identical matches, so the DB
    # pipeline reproduces simlab's clean routes. The production cron uses its own
    # looser defaults for real phone GPS — these only apply here.
    search_radius: int = 8
    gps_accuracy: int = 5
    turn_penalty_factor: int = 300


@db_router.post("/lines/{line_id}/reconstruct")
def reconstruct_line(line_id: str, body: _ReconstructRequest | None = None) -> dict:
    from pipeline.steps.clean_traces import execute as clean_execute
    from pipeline.steps.reconstruct_routes import execute as reconstruct_execute

    body = body or _ReconstructRequest()
    lid = UUID(line_id)
    db = _session()
    try:
        result: dict = {}
        if body.clean:
            result["clean_traces"] = clean_execute(
                db, line_id=lid,
                search_radius=body.search_radius,
                gps_accuracy=body.gps_accuracy,
                turn_penalty_factor=body.turn_penalty_factor,
            )
        result["reconstruct_routes"] = reconstruct_execute(
            db, line_id=lid, strategy_key=body.strategy,
            # Re-match the consensus spine with the SAME tight params as the
            # clean step, so the persisted per-edge geometry matches the
            # rendered consensus (no parallel-street zigzag).
            rematch_search_radius=body.search_radius,
            rematch_gps_accuracy=body.gps_accuracy,
            rematch_turn_penalty_factor=body.turn_penalty_factor,
        )
        return result
    finally:
        db.close()


# --- read back reconstruction + raw traces (for the map) --------------------

@db_router.get("/lines/{line_id}/routes")
def line_routes(line_id: str) -> dict:
    from geoalchemy2.shape import to_shape
    from sqlalchemy import select

    from database.models import Route, RouteEdge, RouteStatus

    lid = UUID(line_id)
    db = _session()
    try:
        features = []
        routes = db.execute(
            select(Route).where(Route.line_id == lid, Route.status != RouteStatus.SUPERSEDED)
        ).scalars().all()
        for route in routes:
            edges = db.execute(
                select(RouteEdge).where(RouteEdge.route_id == route.id)
                .order_by(RouteEdge.sequence)
            ).scalars().all()
            coords: list = []
            for edge in edges:
                if edge.path is None:
                    continue
                for x, y in to_shape(edge.path).coords:
                    if not coords or coords[-1] != [x, y]:
                        coords.append([x, y])
            if len(coords) >= 2:
                features.append({
                    "type": "Feature",
                    "geometry": {"type": "LineString", "coordinates": coords},
                    "properties": {
                        "kind": "db_route",
                        "ramal_label": route.ramal_label,
                        "status": _status(route.status),
                    },
                })
        return {"type": "FeatureCollection", "features": features}
    finally:
        db.close()


@db_router.get("/lines/{line_id}/traces")
def line_traces(line_id: str) -> dict:
    """Raw recorded sessions as polylines, for context on the map."""
    from sqlalchemy import select

    from database.models import TripSession, TripSessionPoint

    lid = UUID(line_id)
    db = _session()
    try:
        features = []
        sessions = db.execute(
            select(TripSession.id).where(TripSession.line_id == lid)
        ).scalars().all()
        for sid in sessions:
            pts = db.execute(
                select(TripSessionPoint.longitude, TripSessionPoint.latitude)
                .where(TripSessionPoint.session_id == sid)
                .order_by(TripSessionPoint.timestamp)
            ).all()
            coords = [[float(lon), float(lat)] for lon, lat in pts]
            if len(coords) >= 2:
                features.append({
                    "type": "Feature",
                    "geometry": {"type": "LineString", "coordinates": coords},
                    "properties": {"kind": "db_trace"},
                })
        return {"type": "FeatureCollection", "features": features}
    finally:
        db.close()
