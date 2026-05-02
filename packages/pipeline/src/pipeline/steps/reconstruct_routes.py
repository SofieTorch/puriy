"""Build consensus routes from cleaned trips and save to database."""

import json
from uuid import UUID

from geoalchemy2.shape import from_shape
from shapely.geometry import LineString
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from database import Line, LineStatus, Route, RouteEdge, RouteSource, RouteStatus, Trip, TripStatus
from geodata.evaluate import load_reconstruction_traces_from_db
from geodata.match import trace_match
from geodata.migrate_votes import migrate_votes_to_new_route
from geodata.reconstruction import get_reconstruction_strategies


def _save_reconstruction(
    db: Session,
    line_id: UUID,
    geojson: dict,
    strategy_key: str,
    trace_count: int,
) -> list[Route]:
    """Save a ReconstructionResult's GeoJSON as Route + RouteEdge records.

    Each GeoJSON feature becomes a Route fragment. The directed edge IDs
    from the strategy are used directly (no re-matching via Valhalla).
    Per-edge geometry is recovered by trace-matching the fragment's
    LineString through Valhalla once.
    """
    features = geojson.get("features", [])
    if not features:
        return []

    # Supersede existing routes for this line
    old_routes = db.execute(
        select(Route).where(
            Route.line_id == line_id,
            Route.status != RouteStatus.SUPERSEDED,
        )
    ).scalars().all()
    for old in old_routes:
        old.status = RouteStatus.SUPERSEDED

    # Determine next version
    max_version = db.execute(
        select(func.max(Route.version)).where(Route.line_id == line_id)
    ).scalar() or 0
    next_version = max_version + 1

    created_routes: list[Route] = []
    fragment_count = len(features)

    for feature in features:
        props = feature.get("properties", {})
        coords = feature.get("geometry", {}).get("coordinates", [])
        directed_edge_ids = props.get("consensus_directed_edge_ids", [])
        fragment_index = props.get("fragment_index", 0)

        route = Route(
            line_id=line_id,
            version=next_version,
            source=RouteSource.COMPUTED,
            strategy_key=strategy_key,
            status=RouteStatus.PENDING,
            trip_count=trace_count,
            fragment_index=fragment_index,
            fragment_count=fragment_count,
        )
        db.add(route)
        db.flush()

        # Trace-match the fragment geometry to get per-edge paths
        points = [{"lon": c[0], "lat": c[1]} for c in coords]
        match_result = trace_match(
            points,
            trace_id=f"route-{line_id}-v{next_version}-f{fragment_index}",
            costing="bus",
            search_radius=60,
            gps_accuracy=20,
        )

        if match_result and match_result.edges:
            for seq, edge in enumerate(match_result.edges):
                edge_coords = match_result.shape_coords[
                    edge.begin_shape_index : edge.end_shape_index + 1
                ]
                if len(edge_coords) < 2:
                    continue
                path = LineString(edge_coords)
                route_edge = RouteEdge(
                    route_id=route.id,
                    sequence=seq,
                    valhalla_edge_id=edge.edge_id,
                    forward=not edge.reversed,
                    path=from_shape(path, srid=4326),
                    confidence=1.0,
                )
                db.add(route_edge)
        else:
            # Fallback: save entire fragment as a single edge
            path = LineString([(c[0], c[1]) for c in coords])
            route_edge = RouteEdge(
                route_id=route.id,
                sequence=0,
                valhalla_edge_id=None,
                forward=True,
                path=from_shape(path, srid=4326),
                confidence=1.0,
            )
            db.add(route_edge)

        created_routes.append(route)

    # Migrate votes from old routes
    if old_routes and created_routes:
        migrate_votes_to_new_route(db, old_routes[0].id, created_routes[0].id)

    db.commit()
    for r in created_routes:
        db.refresh(r)

    return created_routes


def execute(
    db: Session,
    *,
    line_id: UUID | None = None,
    strategy_key: str = "edge_sequence_overlap_assembly_preview",
    min_trips: int = 3,
    strategy_params: dict | None = None,
) -> dict:
    strategies = get_reconstruction_strategies()
    strategy = strategies.get(strategy_key)
    if not strategy:
        return {"error": f"Unknown strategy: {strategy_key}", "lines_processed": 0}

    # Find APPROVED lines with enough clean trips
    query = (
        select(Line.id, func.count(Trip.id).label("trip_count"))
        .join(Trip, Trip.line_id == Line.id)
        .where(
            Line.status == LineStatus.APPROVED,
            Trip.status == TripStatus.CLEAN,
        )
        .group_by(Line.id)
        .having(func.count(Trip.id) >= min_trips)
    )
    if line_id:
        query = query.where(Line.id == line_id)

    lines = db.execute(query).all()

    routes_created = 0
    edges_total = 0
    lines_skipped = 0
    errors = []

    for lid, trip_count in lines:
        try:
            # Skip lines that already have an active route
            existing = db.execute(
                select(Route).where(
                    Route.line_id == lid,
                    Route.status != RouteStatus.SUPERSEDED,
                )
            ).scalars().first()
            if existing:
                lines_skipped += 1
                continue

            traces = load_reconstruction_traces_from_db(line_id=lid)
            if len(traces) < min_trips:
                lines_skipped += 1
                continue

            params = strategy.default_params() if hasattr(strategy, 'default_params') else {}
            if strategy_params:
                params.update(strategy_params)

            result = strategy.reconstruct(lid, traces, params)
            if not result or not result.geojson:
                lines_skipped += 1
                continue

            saved = _save_reconstruction(db, lid, result.geojson, strategy_key, len(traces))
            routes_created += len(saved)
            edges_total += sum(len(r.edges) for r in saved)

        except Exception as e:
            errors.append({"line_id": str(lid), "error": str(e)})

    return {
        "strategy": strategy_key,
        "lines_processed": len(lines),
        "lines_skipped": lines_skipped,
        "routes_created": routes_created,
        "edges_total": edges_total,
        "errors": errors if errors else None,
    }
