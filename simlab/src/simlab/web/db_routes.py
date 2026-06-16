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


# --- preview the voteable segments (what the app would show each rider) ------

def _stitch(edges, to_shape) -> list[list[float]]:
    """Concatenate consecutive edge LineStrings into one [lon, lat] polyline,
    de-duplicating the shared boundary vertex (same logic the server uses)."""
    out: list[list[float]] = []
    for edge in edges:
        if edge.path is None:
            continue
        coords = [[x, y] for x, y in to_shape(edge.path).coords]
        if not coords:
            continue
        if out and out[-1] == coords[0]:
            out.extend(coords[1:])
        else:
            out.extend(coords)
    return out


def _polyline_length_m(coords: list[list[float]]) -> float:
    from math import asin, cos, radians, sin, sqrt

    total = 0.0
    for (lo1, la1), (lo2, la2) in zip(coords, coords[1:]):
        lo1, la1, lo2, la2 = map(radians, (lo1, la1, lo2, la2))
        h = sin((la2 - la1) / 2) ** 2 + cos(la1) * cos(la2) * sin((lo2 - lo1) / 2) ** 2
        total += 6371000 * 2 * asin(sqrt(h))
    return total


@db_router.get("/lines/{line_id}/voteable-segments")
def line_voteable_segments(line_id: str, min_trips: int = 1) -> dict:
    """Preview the voteable segments per rider — exactly what each device would
    be shown to vote on in the app, WITHOUT casting any votes.

    For every device with cleaned trips on the line, find the route edges that
    overlap its own trips (per ramal), group them into contiguous sections, and
    return them as a User -> Segments hierarchy. ``min_trips`` defaults to 1
    because sim devices record a single trip each (the production app gates at
    3); raise it to see who would actually be eligible.
    """
    from geoalchemy2.shape import to_shape
    from sqlalchemy import select

    from database.models import Route, RouteEdge, RouteStatus, Trip, TripSession
    from geodata.edge_overlap import (
        find_overlapping_edges,
        get_device_trips_for_line,
    )

    lid = UUID(line_id)
    db = _session()
    try:
        # Active route per ramal (sim lines have several).
        routes = db.execute(
            select(Route).where(
                Route.line_id == lid, Route.status != RouteStatus.SUPERSEDED
            )
        ).scalars().all()
        if not routes:
            return {"users": [], "ramal_count": 0}

        # Every device that recorded a cleaned trip on this line.
        device_ids = db.execute(
            select(TripSession.device_id)
            .distinct()
            .join(Trip, Trip.session_id == TripSession.id)
            .where(Trip.line_id == lid, Trip.computed_path.isnot(None))
            .order_by(TripSession.device_id)
        ).scalars().all()

        users = []
        for device_id in device_ids:
            trips = get_device_trips_for_line(db, device_id, lid)
            if len(trips) < min_trips:
                continue
            trip_ids = [t.id for t in trips]

            segments = []
            for route in routes:
                edges = find_overlapping_edges(db, route.id, trip_ids)
                if not edges:
                    continue
                # Split into contiguous runs by edge sequence.
                run: list[RouteEdge] = []
                runs: list[list[RouteEdge]] = []
                for edge in edges:
                    if run and edge.sequence != run[-1].sequence + 1:
                        runs.append(run)
                        run = []
                    run.append(edge)
                if run:
                    runs.append(run)

                for run in runs:
                    geometry = _stitch(run, to_shape)
                    if len(geometry) < 2:
                        continue
                    segments.append({
                        "ramal_label": route.ramal_label,
                        "edge_count": len(run),
                        "length_m": round(_polyline_length_m(geometry)),
                        "geometry": geometry,
                    })

            if segments:
                users.append({
                    "device_id": device_id,
                    "trip_count": len(trips),
                    "segments": segments,
                })

        return {"users": users, "ramal_count": len(routes)}
    finally:
        db.close()


# --- DB inspector: devices + their traces -----------------------------------

@db_router.get("/inspect/devices")
def inspect_devices() -> dict:
    """List every device ordered by last connection, with its recorded traces
    grouped underneath. Used to find a device id to impersonate on the phone for
    voting (pick one that has >= min_trips clean trips on a line)."""
    from sqlalchemy import func, select

    from database.models import Device, Line, Trip, TripSession, TripSessionPoint
    from geodata.edge_overlap import DEFAULT_MIN_TRIPS

    db = _session()
    try:
        # Sessions with their line name.
        sess_rows = db.execute(
            select(
                TripSession.id, TripSession.device_id, TripSession.status,
                TripSession.processing_status, TripSession.started_at, Line.name,
            ).join(Line, TripSession.line_id == Line.id, isouter=True)
        ).all()
        # Point count per session.
        pt_counts = dict(db.execute(
            select(TripSessionPoint.session_id, func.count())
            .group_by(TripSessionPoint.session_id)
        ).all())
        # Sessions that produced a clean (matched) trip.
        clean_sessions = set(db.execute(
            select(Trip.session_id).where(Trip.computed_path.isnot(None))
        ).scalars().all())

        by_device: dict[str, list] = {}
        for sid, device_id, status, proc, started_at, line_name in sess_rows:
            by_device.setdefault(device_id, []).append({
                "session_id": str(sid),
                "line_name": line_name,
                "status": _status(status),
                "processing_status": _status(proc),
                "points": int(pt_counts.get(sid, 0)),
                "clean": sid in clean_sessions,
                "started_at": started_at.isoformat() if started_at else None,
            })

        devices = db.execute(
            select(Device).order_by(Device.last_seen_at.desc())
        ).scalars().all()

        out = []
        for dev in devices:
            sessions = by_device.get(dev.id, [])
            # Per-line clean-trip tally → voting eligibility.
            per_line: dict[str, dict] = {}
            for s in sessions:
                ln = s["line_name"] or "(no line)"
                slot = per_line.setdefault(ln, {"sessions": 0, "clean_trips": 0})
                slot["sessions"] += 1
                if s["clean"]:
                    slot["clean_trips"] += 1
            lines = [
                {"line_name": ln, **vals,
                 "eligible": vals["clean_trips"] >= DEFAULT_MIN_TRIPS}
                for ln, vals in sorted(per_line.items())
            ]
            out.append({
                "id": dev.id,
                "platform": _status(dev.platform) if dev.platform else None,
                "last_seen_at": dev.last_seen_at.isoformat() if dev.last_seen_at else None,
                "session_count": len(sessions),
                "clean_trip_count": sum(1 for s in sessions if s["clean"]),
                "eligible_any": any(line["eligible"] for line in lines),
                "lines": lines,
                "sessions": sessions,
            })
        return {"devices": out, "min_trips": DEFAULT_MIN_TRIPS}
    finally:
        db.close()


@db_router.get("/inspect/device-traces")
def inspect_device_traces(device_id: str) -> dict:
    """One device's recorded sessions as polylines, for the inspector map.
    `device_id` is a query param (sim ids contain ':' and spaces)."""
    from sqlalchemy import select

    from database.models import TripSession, TripSessionPoint

    db = _session()
    try:
        features = []
        sessions = db.execute(
            select(TripSession.id).where(TripSession.device_id == device_id)
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
                    "properties": {"kind": "device_trace", "session_id": str(sid)},
                })
        return {"type": "FeatureCollection", "features": features}
    finally:
        db.close()


# --- refresh the API server's transit graph ---------------------------------

@db_router.post("/rebuild-graph")
def rebuild_directions_graph() -> dict:
    """Proxy to the API server's transit-graph rebuild.

    The directions graph is an in-memory cache living in the API server process
    (default http://127.0.0.1:8000, override with APP_SERVER_URL) — separate
    from simlab and the database. After route data changes (promote/build), it
    must be refreshed there or A→B routing keeps using the old lines. This is a
    server-to-server call so the browser doesn't hit a cross-origin block."""
    import json
    import os
    import urllib.request

    base = os.environ.get("APP_SERVER_URL", "http://127.0.0.1:8000").rstrip("/")
    url = f"{base}/directions/graph/rebuild"
    try:
        req = urllib.request.Request(
            url, data=b"", method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            return {"ok": True, "url": url, "result": json.load(resp)}
    except Exception as e:
        return {"ok": False, "url": url, "error": str(e)}
