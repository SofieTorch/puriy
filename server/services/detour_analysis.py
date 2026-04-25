"""Detour analysis — compute divergence/convergence points between a detour and a line's normal route."""

import os
from uuid import UUID

import httpx
from geoalchemy2 import WKBElement
from shapely import wkb
from shapely.geometry import LineString, Point
from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models.route import Route, RouteEdge, RouteStatus

NOMINATIM_URL = os.environ.get("NOMINATIM_URL", "http://localhost:8004")
DIVERGENCE_THRESHOLD_M = 50.0  # meters — beyond this, points are "off route"


def _haversine_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Approximate haversine distance in meters."""
    import math

    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _point_distance_to_line(point: Point, line: LineString) -> float:
    """Approximate distance in meters from a point to the nearest point on a line."""
    nearest = line.interpolate(line.project(point))
    return _haversine_m(point.x, point.y, nearest.x, nearest.y)


def get_line_route_geometry(db: Session, line_id: UUID) -> LineString | None:
    """Assemble the active route geometry for a line from its edges."""
    route = (
        db.execute(
            select(Route)
            .where(Route.line_id == line_id, Route.status != RouteStatus.SUPERSEDED)
            .order_by(Route.version.desc())
        )
        .scalars()
        .first()
    )
    if not route:
        return None

    edges = (
        db.execute(
            select(RouteEdge)
            .where(RouteEdge.route_id == route.id)
            .order_by(RouteEdge.sequence)
        )
        .scalars()
        .all()
    )

    all_coords: list[tuple[float, float]] = []
    for edge in edges:
        if edge.path is None:
            continue
        if isinstance(edge.path, WKBElement):
            shape = wkb.loads(bytes(edge.path.data))
        else:
            shape = edge.path
        coords = list(shape.coords)
        if all_coords and coords:
            all_coords.extend(coords[1:])
        else:
            all_coords.extend(coords)

    return LineString(all_coords) if len(all_coords) >= 2 else None


def compute_divergence_indices(
    detour_path: LineString,
    normal_route: LineString,
    threshold_m: float = DIVERGENCE_THRESHOLD_M,
) -> tuple[int | None, int | None]:
    """Find the indices where the detour diverges from and rejoins the normal route.

    Returns (diverge_index, converge_index) into the detour path coordinates.
    """
    detour_coords = list(detour_path.coords)

    diverge_idx = None
    converge_idx = None

    # Walk forward to find divergence
    for i, (lon, lat) in enumerate(detour_coords):
        dist = _point_distance_to_line(Point(lon, lat), normal_route)
        if dist > threshold_m:
            diverge_idx = max(0, i - 1)  # include the last on-route point
            break

    # Walk backward to find convergence
    for i in range(len(detour_coords) - 1, -1, -1):
        lon, lat = detour_coords[i]
        dist = _point_distance_to_line(Point(lon, lat), normal_route)
        if dist > threshold_m:
            converge_idx = min(len(detour_coords) - 1, i + 1)  # include the first on-route point
            break

    return diverge_idx, converge_idx


def reverse_geocode_street(lon: float, lat: float) -> str | None:
    """Get street name for a coordinate via Nominatim."""
    try:
        resp = httpx.get(
            f"{NOMINATIM_URL}/reverse",
            params={"lat": lat, "lon": lon, "format": "json", "zoom": 18, "addressdetails": "1"},
            headers={"User-Agent": "CbbaMobility/1.0 (transit-app)"},
            timeout=5.0,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        return data.get("address", {}).get("road")
    except Exception:
        return None


def analyze_detour(
    db: Session,
    detour_path_geom: WKBElement | LineString,
    line_id: UUID,
) -> dict:
    """Analyze a detour path against the line's normal route.

    Returns dict with: detour_path (coords), diverges_at, rejoins_at.
    """
    # Parse detour geometry
    if isinstance(detour_path_geom, WKBElement):
        detour_shape = wkb.loads(bytes(detour_path_geom.data))
    else:
        detour_shape = detour_path_geom

    all_coords = list(detour_shape.coords)

    # Get normal route
    normal_route = get_line_route_geometry(db, line_id)

    diverges_at = None
    rejoins_at = None
    detour_segment = [[c[0], c[1]] for c in all_coords]  # fallback: full path

    if normal_route and len(all_coords) >= 2:
        diverge_idx, converge_idx = compute_divergence_indices(detour_shape, normal_route)

        if diverge_idx is not None and converge_idx is not None and diverge_idx < converge_idx:
            # Trim to only the divergent segment
            trimmed = all_coords[diverge_idx : converge_idx + 1]
            if len(trimmed) >= 2:
                detour_segment = [[c[0], c[1]] for c in trimmed]

            diverge_coord = all_coords[diverge_idx]
            converge_coord = all_coords[converge_idx]
            diverges_at = reverse_geocode_street(diverge_coord[0], diverge_coord[1])
            rejoins_at = reverse_geocode_street(converge_coord[0], converge_coord[1])

    return {
        "detour_path": detour_segment,
        "diverges_at": diverges_at,
        "rejoins_at": rejoins_at,
    }
