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

from ..strategies import RoutebuilderDivergenceStrategy

logger = logging.getLogger(__name__)


def _available_strategies() -> dict:
    """geodata's notebook strategies plus the pipeline-local routebuilder
    strategy (which geodata can't host — it depends on routebuilder)."""
    strategies = dict(get_reconstruction_strategies())
    rb = RoutebuilderDivergenceStrategy()
    strategies[rb.key] = rb
    return strategies


def _reconstruct_line_level(
    db: Session,
    line_id: UUID,
    strategy,
    traces: list,
    params: dict,
    existing_per_ramal: dict,
    strategy_key: str,
    change_threshold_m: float,
    rematch: dict | None = None,
) -> dict:
    """Persist a self-clustering strategy's output. Such a strategy
    (``clusters_internally``) reconstructs ALL the line's traces at once and
    emits one feature per ramal; each is created / left unchanged / superseded
    with the same logic as the per-cluster path. Returns a counters dict."""
    call_params = {
        **params,
        "existing_ramales": [
            (label, coords) for label, (_, coords) in existing_per_ramal.items()
        ],
    }
    result = strategy.reconstruct(line_id, traces, call_params)
    counters = {
        "created": 0, "unchanged": 0, "superseded": 0,
        "fragmented": 0, "edges": 0,
    }
    features = (result.geojson.get("features") if result and result.geojson else []) or []
    for feature in features:
        label = (feature.get("properties") or {}).get("ramal_label") or "main"
        coords = [
            [c[0], c[1]]
            for c in feature.get("geometry", {}).get("coordinates", [])
            if len(c) >= 2
        ]
        if len(coords) < 2:
            counters["fragmented"] += 1
            continue
        single = {"type": "FeatureCollection", "features": [feature]}
        existing_pair = existing_per_ramal.get(label)
        if existing_pair is None:
            saved = _save_reconstruction(
                db, line_id, label, single, strategy_key, len(traces), rematch=rematch
            )
            if saved is not None:
                counters["created"] += 1
                counters["edges"] += len(saved.edges)
            continue
        existing_route, existing_coords = existing_pair
        distance_m = discrete_frechet_distance_m(existing_coords, coords)
        if distance_m < change_threshold_m:
            existing_route.last_compared_at = datetime.utcnow()
            db.commit()
            counters["unchanged"] += 1
            continue
        saved = _save_reconstruction(
            db, line_id, label, single, strategy_key, len(traces), rematch=rematch
        )
        if saved is not None:
            counters["superseded"] += 1
            counters["edges"] += len(saved.edges)
    return counters

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
    rematch: dict | None = None,
) -> Route | None:
    """Save a candidate GeoJSON as a new Route for `(line_id, ramal_label)`.

    The strategy's GeoJSON must contain exactly one Feature — fragmented
    reconstructions are rejected (caller pre-checks too; this is the
    defensive enforcement). Per-edge geometry is recovered by
    trace-matching the polyline through Valhalla once.

    `rematch` overrides that re-match's Valhalla params
    (``{"search_radius", "gps_accuracy", "turn_penalty_factor"}``). It defaults
    to the loose production values, which suit real phone GPS but snap the
    *already-clean* consensus spine onto parallel streets and zigzag it. Clean
    (simulated) sources should pass tight params identical to their clean step
    so the persisted geometry matches the rendered consensus exactly. Returns
    the new `Route` (already committed and refreshed) or `None` if rejected.
    """
    rematch = rematch or {}
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

    # Trace-match the polyline through Valhalla — but ONLY to LABEL the edges
    # (edge_id, street names), never to replace the geometry. The strategy's
    # consensus polyline is already clean and road-following; re-matching it can
    # bridge gaps with straight lines and distort it (the Valhalla `shape_coords`
    # between two consensus points may cut across a block). So we persist the
    # CONSENSUS coordinates, partitioned per matched edge: each input point
    # carries the `edge_index` it snapped onto, and concatenating the resulting
    # edges reproduces the consensus exactly while still attaching edge IDs.
    points = [{"lon": c[0], "lat": c[1]} for c in coords]
    match_result = trace_match(
        points,
        trace_id=f"route-{line_id}-{ramal_label}-v{next_version}",
        costing="bus",
        search_radius=rematch.get("search_radius", 60),
        gps_accuracy=rematch.get("gps_accuracy", 20),
        turn_penalty_factor=rematch.get("turn_penalty_factor", 0),
    )

    edges = match_result.edges if match_result else []
    matched_points = match_result.matched_points if match_result else []

    if edges and len(matched_points) == len(coords):
        # Group consecutive consensus points by the edge they matched onto.
        # `coords` are [lon, lat] (consensus geometry) — used as-is, no swap.
        groups: list[list] = []          # [ [edge_index, [pt, pt, ...]], ... ]
        last_valid = 0
        for pt, mp in zip(coords, matched_points):
            ei = mp.get("edge_index")
            if not isinstance(ei, int) or ei < 0 or ei >= len(edges):
                ei = last_valid          # carry forward across unmatched points
            else:
                last_valid = ei
            if not groups or groups[-1][0] != ei:
                if groups:               # share the boundary point for continuity
                    groups[-1][1].append(pt)
                groups.append([ei, [pt]])
            else:
                groups[-1][1].append(pt)

        seq = 0
        for ei, pts in groups:
            if len(pts) < 2:
                continue
            edge = edges[ei]
            path = LineString([(p[0], p[1]) for p in pts])
            db.add(RouteEdge(
                route_id=route.id,
                sequence=seq,
                valhalla_edge_id=edge.get("edge_id"),
                forward=not edge.get("reversed", False),
                path=from_shape(path, srid=4326),
                confidence=1.0,
            ))
            seq += 1
        # Human-readable street names from the matched edges.
        route.street_summary = summarise_streets(edges)
    else:
        # Fallback when Valhalla is unavailable / can't label the polyline:
        # persist the consensus as a single edge with no `valhalla_edge_id`.
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
    rematch_search_radius: int = 60,
    rematch_gps_accuracy: int = 20,
    rematch_turn_penalty_factor: int = 0,
) -> dict:
    """Reconstruct routes per-ramal for every APPROVED line with enough trips.

    For each line: cluster traces into ramales, then for each cluster
    decide between create / unchanged / supersede using the existing
    single-polyline + RF-19 logic, scoped to that ramal.
    """
    strategies = _available_strategies()
    strategy = strategies.get(strategy_key)
    if not strategy:
        return {"error": f"Unknown strategy: {strategy_key}", "lines_processed": 0}
    line_level = getattr(strategy, "clusters_internally", False)

    # Valhalla params for re-matching the consensus spine into per-edge geometry
    # (see _save_reconstruction). Defaults are the loose production values; the
    # simlab path overrides them with its tight clean-step params for parity.
    rematch = {
        "search_radius": rematch_search_radius,
        "gps_accuracy": rematch_gps_accuracy,
        "turn_penalty_factor": rematch_turn_penalty_factor,
    }

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

            if line_level:
                # Self-clustering strategy (routebuilder): it discovers ramales
                # itself over ALL the line's traces — skip geodata clustering.
                params = strategy.default_params() if hasattr(strategy, 'default_params') else {}
                if strategy_params:
                    params.update(strategy_params)
                c = _reconstruct_line_level(
                    db, lid, strategy, traces, params, existing_per_ramal,
                    strategy_key, change_threshold_m, rematch=rematch,
                )
                ramales_created += c["created"]
                ramales_superseded += c["superseded"]
                ramales_unchanged += c["unchanged"]
                ramales_skipped_fragmented += c["fragmented"]
                routes_created += c["created"] + c["superseded"]
                edges_total += c["edges"]
                continue

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
                        strategy_key, len(cluster_traces), rematch=rematch,
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
                    strategy_key, len(cluster_traces), rematch=rematch,
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
