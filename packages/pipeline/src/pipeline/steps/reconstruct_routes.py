"""Build consensus routes from cleaned trips and save to database.

Per-line, the pipeline:

1. Loads cleaned traces.
2. Clusters them into ramales (variants of the same line that follow
   meaningfully different geometries — e.g. line 230 has a "directo"
   ramal and a "vía Simón Lopez" ramal). Each cluster gets a stable
   label (`main`, `r2`, `r3`, …) inherited from previous runs when
   geometry matches, fresh otherwise.
3. For each cluster, runs the reconstruction strategy and applies the
   single-polyline + RF-19 change-detection rules scoped to that ramal:
   no existing route for the label → create v1; existing within
   threshold → bump `last_compared_at`; existing beyond threshold →
   supersede + new version.
4. Existing ramales whose cluster fell below `min_trips` in this run
   are left untouched (a temporary contribution dip shouldn't drop a
   published ramal).
"""

import logging
from datetime import datetime
from uuid import UUID

from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import LineString
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from database import Line, LineStatus, Route, RouteEdge, RouteSource, RouteStatus, Trip, TripStatus
from geodata.evaluate import (
    discrete_frechet_distance_m,
    load_reconstruction_traces_from_db,
)
from geodata.match import trace_match
from geodata.migrate_votes import migrate_votes_to_new_route
from geodata.ramales import cluster_traces_into_ramales
from geodata.reconstruction import get_reconstruction_strategies
from geodata.streets import resolve_endpoint_zones, summarise_streets

logger = logging.getLogger(__name__)

#: Default Fréchet-distance threshold (metres) above which a freshly
#: reconstructed route is considered "significantly different" from the
#: existing active route, triggering a supersede + new version (RF-19).
DEFAULT_CHANGE_THRESHOLD_M = 50.0

#: Default Fréchet-distance threshold (metres) for grouping traces into
#: ramales. Chosen as ~200m (≈ 2 Cochabamba blocks): tight enough to
#: keep separate variants apart, loose enough to absorb GPS noise.
DEFAULT_RAMAL_DISTANCE_THRESHOLD_M = 200.0


def _load_existing_ramales(
    db: Session, line_id: UUID,
) -> dict[str, tuple[Route, list[list[float]]]]:
    """Return active routes for `line_id` keyed by `ramal_label`.

    Each value is `(route, polyline_coords)`. The DB-level partial
    unique index `uq_route_active_per_ramal` guarantees at most one
    active route per (line, ramal) pair, so the dict has no collisions.
    """
    rows = db.execute(
        select(Route)
        .where(Route.line_id == line_id, Route.status != RouteStatus.SUPERSEDED)
    ).scalars().all()

    out: dict[str, tuple[Route, list[list[float]]]] = {}
    for route in rows:
        coords: list[list[float]] = []
        for edge in sorted(route.edges, key=lambda e: e.sequence):
            if edge.path is None:
                continue
            shape = to_shape(edge.path)
            for c in shape.coords:
                coords.append([c[0], c[1]])
        out[route.ramal_label] = (route, coords)
    return out


def _save_reconstruction(
    db: Session,
    line_id: UUID,
    ramal_label: str,
    geojson: dict,
    strategy_key: str,
    trace_count: int,
) -> Route | None:
    """Save a candidate GeoJSON as a new Route for `(line_id, ramal_label)`.

    The strategy's GeoJSON must contain exactly one Feature — fragmented
    reconstructions are rejected (caller pre-checks too; this is the
    defensive enforcement). Per-edge geometry is recovered by
    trace-matching the polyline through Valhalla once. Returns the new
    `Route` (already committed and refreshed) or `None` if rejected.
    """
    features = geojson.get("features", [])
    if len(features) != 1:
        return None

    # Supersede the existing active route for THIS ramal only — other
    # ramales of the same line are independent version chains.
    old_route = db.execute(
        select(Route).where(
            Route.line_id == line_id,
            Route.ramal_label == ramal_label,
            Route.status != RouteStatus.SUPERSEDED,
        )
    ).scalars().first()
    if old_route is not None:
        old_route.status = RouteStatus.SUPERSEDED
        # Flush so the partial unique index sees the supersede before we
        # insert the replacement (otherwise the constraint would block).
        db.flush()

    max_version = db.execute(
        select(func.max(Route.version)).where(
            Route.line_id == line_id,
            Route.ramal_label == ramal_label,
        )
    ).scalar() or 0
    next_version = max_version + 1

    feature = features[0]
    coords = feature.get("geometry", {}).get("coordinates", [])

    route = Route(
        line_id=line_id,
        version=next_version,
        ramal_label=ramal_label,
        source=RouteSource.COMPUTED,
        strategy_key=strategy_key,
        status=RouteStatus.PENDING,
        trip_count=trace_count,
        fragment_index=0,
        fragment_count=1,
    )
    db.add(route)
    db.flush()

    # Trace-match the polyline through Valhalla to get per-edge paths.
    points = [{"lon": c[0], "lat": c[1]} for c in coords]
    match_result = trace_match(
        points,
        trace_id=f"route-{line_id}-{ramal_label}-v{next_version}",
        costing="bus",
        search_radius=60,
        gps_accuracy=20,
    )

    if match_result and match_result.edges:
        for seq, edge in enumerate(match_result.edges):
            edge_coords = match_result.shape_coords[
                edge["begin_shape_index"] : edge["end_shape_index"] + 1
            ]
            if len(edge_coords) < 2:
                continue
            # shape_coords come from `_decode_polyline6`, which yields
            # (lat, lon) tuples; shapely's LineString and PostGIS both
            # expect (lon, lat). Swap before persisting or queries
            # like ST_DWithin against (lon, lat) GPS points won't match.
            path = LineString([(c[1], c[0]) for c in edge_coords])
            db.add(RouteEdge(
                route_id=route.id,
                sequence=seq,
                valhalla_edge_id=edge.get("edge_id"),
                forward=not edge.get("reversed", False),
                path=from_shape(path, srid=4326),
                confidence=1.0,
            ))
        # Human-readable street names from the same matched edges.
        route.street_summary = summarise_streets(match_result.edges)
    else:
        # Fallback when Valhalla is unavailable / can't match: persist
        # the raw polyline as a single edge with no `valhalla_edge_id`.
        path = LineString([(c[0], c[1]) for c in coords])
        db.add(RouteEdge(
            route_id=route.id,
            sequence=0,
            valhalla_edge_id=None,
            forward=True,
            path=from_shape(path, srid=4326),
            confidence=1.0,
        ))

    # Reverse-geocode the endpoints regardless of map-matching success —
    # the start/end coords are always available from the candidate.
    if coords:
        route.endpoint_zones = resolve_endpoint_zones(coords[0], coords[-1])

    if old_route is not None:
        migrate_votes_to_new_route(db, old_route.id, route.id)

    db.commit()
    db.refresh(route)
    return route


def execute(
    db: Session,
    *,
    line_id: UUID | None = None,
    strategy_key: str = "edge_sequence_overlap_assembly_preview",
    min_trips: int = 3,
    strategy_params: dict | None = None,
    change_threshold_m: float = DEFAULT_CHANGE_THRESHOLD_M,
    ramal_distance_threshold_m: float = DEFAULT_RAMAL_DISTANCE_THRESHOLD_M,
) -> dict:
    """Reconstruct routes per-ramal for every APPROVED line with enough trips.

    For each line: cluster traces into ramales, then for each cluster
    decide between create / unchanged / supersede using the existing
    single-polyline + RF-19 logic, scoped to that ramal.
    """
    strategies = get_reconstruction_strategies()
    strategy = strategies.get(strategy_key)
    if not strategy:
        return {"error": f"Unknown strategy: {strategy_key}", "lines_processed": 0}

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
    lines_skipped_fragmented = 0
    ramales_created = 0
    ramales_unchanged = 0
    ramales_superseded = 0
    ramales_skipped_fragmented = 0
    lines_with_multiple_ramales = 0
    errors = []

    for lid, _trip_count in lines:
        try:
            traces = load_reconstruction_traces_from_db(line_id=lid)
            if len(traces) < min_trips:
                lines_skipped += 1
                continue

            existing_per_ramal = _load_existing_ramales(db, lid)

            clusters = cluster_traces_into_ramales(
                traces,
                distance_threshold_m=ramal_distance_threshold_m,
                min_cluster_size=min_trips,
                existing_ramales=[
                    (label, coords) for label, (_, coords) in existing_per_ramal.items()
                ],
            )
            if not clusters:
                lines_skipped += 1
                continue
            if len(clusters) > 1:
                lines_with_multiple_ramales += 1

            params = strategy.default_params() if hasattr(strategy, 'default_params') else {}
            if strategy_params:
                params.update(strategy_params)

            for cluster in clusters:
                cluster_traces = [t for t in traces if t.trace_id in set(cluster.trace_ids)]
                result = strategy.reconstruct(lid, cluster_traces, params)
                if not result or not result.geojson:
                    continue

                # Single-polyline invariant per ramal.
                candidate_features = result.geojson.get("features") or []
                if len(candidate_features) != 1:
                    ramales_skipped_fragmented += 1
                    continue

                existing_pair = existing_per_ramal.get(cluster.label)
                if existing_pair is None:
                    saved = _save_reconstruction(
                        db, lid, cluster.label, result.geojson,
                        strategy_key, len(cluster_traces),
                    )
                    if saved is not None:
                        ramales_created += 1
                        routes_created += 1
                        edges_total += len(saved.edges)
                    continue

                existing_route, existing_coords = existing_pair
                candidate_coords = [
                    [c[0], c[1]]
                    for c in candidate_features[0].get("geometry", {}).get("coordinates", [])
                    if len(c) >= 2
                ]
                distance_m = discrete_frechet_distance_m(existing_coords, candidate_coords)
                logger.info(
                    "reconstruct_routes: line_id=%s ramal=%s frechet=%.2fm threshold=%.2fm",
                    lid, cluster.label, distance_m, change_threshold_m,
                )

                if distance_m < change_threshold_m:
                    existing_route.last_compared_at = datetime.utcnow()
                    db.commit()
                    ramales_unchanged += 1
                    continue

                saved = _save_reconstruction(
                    db, lid, cluster.label, result.geojson,
                    strategy_key, len(cluster_traces),
                )
                if saved is not None:
                    ramales_superseded += 1
                    routes_created += 1
                    edges_total += len(saved.edges)

        except Exception as e:
            errors.append({"line_id": str(lid), "error": str(e)})

    return {
        "strategy": strategy_key,
        "lines_processed": len(lines),
        "lines_skipped": lines_skipped,
        "lines_skipped_fragmented": lines_skipped_fragmented,
        "lines_with_multiple_ramales": lines_with_multiple_ramales,
        "ramales_created": ramales_created,
        "ramales_unchanged": ramales_unchanged,
        "ramales_superseded": ramales_superseded,
        "ramales_skipped_fragmented": ramales_skipped_fragmented,
        "routes_created": routes_created,
        "edges_total": edges_total,
        "change_threshold_m": change_threshold_m,
        "ramal_distance_threshold_m": ramal_distance_threshold_m,
        "errors": errors if errors else None,
    }
