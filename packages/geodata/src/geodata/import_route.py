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

from .geojson import parse_route_from_geojson
from .match import trace_match


def import_route_from_geojson(
    db: Session,
    geojson_str: str,
    line_id: UUID,
    *,
    costing: str = "bus",
    search_radius: int = 60,
    gps_accuracy: int = 20,
) -> Route:
    """Import a GeoJSON route as an inferred Route with Valhalla edges.

    Parameters
    ----------
    db : Session
        SQLAlchemy session.
    geojson_str : str
        Raw GeoJSON string (FeatureCollection, Feature, or bare LineString).
    line_id : UUID
        Line to attach this route to. Must already exist.
    costing : str
        Valhalla costing model (default: "bus").
    search_radius : int
        Valhalla search radius in meters.
    gps_accuracy : int
        Valhalla GPS accuracy in meters.

    Returns
    -------
    Route
        The persisted route with its edges.
    """
    line = db.get(Line, line_id)
    if not line:
        raise ValueError(f"Line {line_id} not found")

    coords = parse_route_from_geojson(geojson_str)
    if len(coords) < 2:
        raise ValueError("Route must have at least 2 coordinate points")

    # Map-match through Valhalla to get road-network edges
    shape = [{"lat": lat, "lon": lon} for lon, lat in coords]
    result = trace_match(
        shape,
        trace_id=f"import-{line_id}",
        costing=costing,
        search_radius=search_radius,
        gps_accuracy=gps_accuracy,
    )

    if not result.edges:
        raise ValueError("Valhalla returned no edges for this route")

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

    route = Route(
        line_id=line_id,
        version=next_version,
        source=RouteSource.IMPORTED,
        status=RouteStatus.PENDING,
        trip_count=0,
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

    # Migrate votes from superseded routes
    db.flush()
    for prev in previous:
        from .migrate_votes import migrate_votes_to_new_route

        migrate_votes_to_new_route(db, prev.id, route.id)

    db.commit()
    db.refresh(route)
    return route


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
