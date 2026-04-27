"""GeoJSON parsing utilities."""

import json


def parse_route_from_geojson(raw: str) -> list[list[float]]:
    """Extract a LineString route from a GeoJSON string.

    Accepts FeatureCollection, Feature, or bare LineString geometry.
    Returns a list of [lon, lat] coordinate pairs.
    """
    payload = json.loads(raw)
    geometry = None
    if payload.get("type") == "FeatureCollection":
        for feature in payload.get("features", []):
            geom = feature.get("geometry", {})
            if geom.get("type") == "LineString":
                geometry = geom
                break
    elif payload.get("type") == "Feature":
        geometry = payload.get("geometry", {})
    elif payload.get("type") == "LineString":
        geometry = payload

    if not geometry or geometry.get("type") != "LineString":
        raise ValueError("GeoJSON must contain a LineString geometry")

    coords = geometry.get("coordinates", [])
    route: list[list[float]] = []
    for coord in coords:
        if not isinstance(coord, (list, tuple)) or len(coord) < 2:
            continue
        route.append([float(coord[0]), float(coord[1])])
    return route


def parse_routes_from_geojson(raw: str) -> list[list[list[float]]]:
    """Extract all LineString routes from a GeoJSON string.

    Like :func:`parse_route_from_geojson` but returns one coordinate list per
    LineString feature, preserving multi-fragment reconstructions.
    """
    payload = json.loads(raw)

    geometries: list[dict] = []
    if payload.get("type") == "FeatureCollection":
        for feature in payload.get("features", []):
            geom = feature.get("geometry", {})
            if geom.get("type") == "LineString":
                geometries.append(geom)
    elif payload.get("type") == "Feature":
        geom = payload.get("geometry", {})
        if geom.get("type") == "LineString":
            geometries.append(geom)
    elif payload.get("type") == "LineString":
        geometries.append(payload)

    if not geometries:
        raise ValueError("GeoJSON must contain at least one LineString geometry")

    routes: list[list[list[float]]] = []
    for geometry in geometries:
        route: list[list[float]] = []
        for coord in geometry.get("coordinates", []):
            if not isinstance(coord, (list, tuple)) or len(coord) < 2:
                continue
            route.append([float(coord[0]), float(coord[1])])
        if route:
            routes.append(route)

    if not routes:
        raise ValueError("GeoJSON must contain at least one LineString geometry")

    return routes
