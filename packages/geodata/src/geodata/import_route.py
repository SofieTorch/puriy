"""Import external route GeoJSON files as inferred Routes with Valhalla edges."""

import json
from pathlib import Path
from uuid import UUID

from geoalchemy2.shape import from_shape
from shapely.geometry import LineString
from sqlalchemy.orm import Session

from database.models import (
    Line,
    Route,
    RouteEdge,
    RouteSource,
    RouteStatus,
)

from .geojson import parse_route_from_geojson, parse_routes_from_geojson
from .match import trace_match


def import_route_from_geojson(
    db: Session,
    geojson_str: str,
    line_id: UUID,
    *,
    costing: str = "bus",
    search_radius: int = 60,
    gps_accuracy: int = 20,
) -> Route | list[Route]:
    """Import a GeoJSON route as inferred Route(s) with Valhalla edges.

    If the GeoJSON contains multiple LineString features (e.g. a fragmented
    reconstruction), one Route per feature is created, all sharing the same
    version with distinct ``fragment_index`` values.

    Returns a single Route for single-feature input, or a list for multi-feature.
    """
    line = db.get(Line, line_id)
    if not line:
        raise ValueError(f"Line {line_id} not found")

    all_coords = parse_routes_from_geojson(geojson_str)
    for coords in all_coords:
        if len(coords) < 2:
            raise ValueError("Each route fragment must have at least 2 coordinate points")

    # Supersede any previous routes for this line
    previous = (
        db.query(Route)
        .filter(
            Route.line_id == line_id,
            Route.status != RouteStatus.SUPERSEDED,
        )
        .all()
    )
    next_version = 1
    for prev in previous:
        if prev.version >= next_version:
            next_version = prev.version + 1
        prev.status = RouteStatus.SUPERSEDED

    fragment_count = len(all_coords)
    routes: list[Route] = []

    for fragment_index, coords in enumerate(all_coords):
        # Map-match through Valhalla to get road-network edges
        shape = [{"lat": lat, "lon": lon} for lon, lat in coords]
        result = trace_match(
            shape,
            trace_id=f"import-{line_id}-f{fragment_index}",
            costing=costing,
            search_radius=search_radius,
            gps_accuracy=gps_accuracy,
        )

        if not result.edges:
            raise ValueError(f"Valhalla returned no edges for fragment {fragment_index}")

        route = Route(
            line_id=line_id,
            version=next_version,
            source=RouteSource.IMPORTED,
            status=RouteStatus.PENDING,
            trip_count=0,
            fragment_index=fragment_index,
            fragment_count=fragment_count,
        )
        db.add(route)
        db.flush()

        # Create RouteEdge for each Valhalla edge
        for seq, edge in enumerate(result.edges):
            begin_idx = edge.get("begin_shape_index", 0)
            end_idx = edge.get("end_shape_index", begin_idx)
            edge_coords = result.shape_coords[begin_idx : end_idx + 1]

            if len(edge_coords) < 2:
                continue

            edge_linestring = LineString(
                [(lon, lat) for lat, lon in edge_coords]
            )
            db.add(
                RouteEdge(
                    route_id=route.id,
                    sequence=seq,
                    valhalla_edge_id=edge.get("id"),
                    forward=edge.get("forward", True),
                    path=from_shape(edge_linestring, srid=4326),
                )
            )

        routes.append(route)

    # Migrate votes from superseded routes to the first fragment
    db.flush()
    if routes:
        for prev in previous:
            from .migrate_votes import migrate_votes_to_new_route

            migrate_votes_to_new_route(db, prev.id, routes[0].id)

    db.commit()
    for route in routes:
        db.refresh(route)

    return routes[0] if len(routes) == 1 else routes


def import_routes_from_directory(
    db: Session,
    directory: str | Path,
    *,
    costing: str = "bus",
    search_radius: int = 60,
    gps_accuracy: int = 20,
) -> list[tuple[str, Route]]:
    """Import all GeoJSON files from a directory, creating lines from properties.

    Each GeoJSON FeatureCollection is expected to have a feature with properties
    ``route_short_name`` and ``route_long_name`` (standard GTFS-derived format).

    Returns a list of (filename, RouteEstimation) tuples.
    """
    directory = Path(directory)
    results: list[tuple[str, Route]] = []

    for geojson_path in sorted(directory.glob("*.geojson")):
        raw = geojson_path.read_text(encoding="utf-8")
        payload = json.loads(raw)

        # Extract route metadata from GeoJSON properties
        short_name = geojson_path.stem
        long_name = None
        if payload.get("type") == "FeatureCollection":
            for feature in payload.get("features", []):
                props = feature.get("properties", {})
                if props.get("route_short_name"):
                    short_name = props["route_short_name"]
                if props.get("route_long_name"):
                    long_name = props["route_long_name"]
                break

        # Find or create the line
        line = db.query(Line).filter(Line.name == short_name).first()
        if not line:
            line = Line(name=short_name, description=long_name)
            db.add(line)
            db.flush()

        estimation = import_route_from_geojson(
            db,
            raw,
            line.id,
            costing=costing,
            search_radius=search_radius,
            gps_accuracy=gps_accuracy,
        )
        results.append((geojson_path.name, estimation))

    return results
