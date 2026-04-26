"""Import fare zones from OpenStreetMap administrative boundaries via Overpass API."""

import json
from typing import Any

import httpx
from shapely.geometry import MultiPolygon, Polygon, shape
from shapely.ops import unary_union
from geoalchemy2.shape import from_shape
from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import FareZone

OVERPASS_URL = "https://overpass-api.de/api/interpreter"


def _query_overpass(department: str, admin_level: int) -> dict[str, Any]:
    """Query Overpass API for admin boundary relations."""
    query = f"""
    [out:json][timeout:120];
    area["name"="{department}"]["admin_level"="4"]->.dept;
    relation["admin_level"="{admin_level}"]["boundary"="administrative"](area.dept);
    out body;
    >;
    out skel qt;
    """
    response = httpx.post(
        OVERPASS_URL,
        data={"data": query},
        timeout=180,
    )
    response.raise_for_status()
    return response.json()


def _build_polygons(data: dict[str, Any]) -> list[tuple[str, MultiPolygon]]:
    """Parse Overpass JSON response into named MultiPolygon geometries."""
    nodes: dict[int, tuple[float, float]] = {}
    ways: dict[int, list[tuple[float, float]]] = {}
    relations: list[dict[str, Any]] = []

    for element in data.get("elements", []):
        if element["type"] == "node":
            nodes[element["id"]] = (element["lon"], element["lat"])
        elif element["type"] == "way":
            coords = []
            for nd_id in element.get("nodes", []):
                if nd_id in nodes:
                    coords.append(nodes[nd_id])
            ways[element["id"]] = coords
        elif element["type"] == "relation":
            relations.append(element)

    results: list[tuple[str, MultiPolygon]] = []
    for relation in relations:
        name = relation.get("tags", {}).get("name")
        if not name:
            continue

        outer_rings: list[list[tuple[float, float]]] = []
        for member in relation.get("members", []):
            if member.get("type") == "way" and member.get("role") in ("outer", ""):
                way_coords = ways.get(member["ref"], [])
                if way_coords:
                    outer_rings.append(way_coords)

        if not outer_rings:
            continue

        # Assemble rings by connecting ways end-to-end
        polygons = _assemble_rings(outer_rings)
        if polygons:
            multi = MultiPolygon(polygons) if len(polygons) > 1 else MultiPolygon([polygons[0]])
            if multi.is_valid:
                results.append((name, multi))
            else:
                fixed = multi.buffer(0)
                if fixed.is_valid and not fixed.is_empty:
                    if isinstance(fixed, Polygon):
                        fixed = MultiPolygon([fixed])
                    results.append((name, fixed))

    return results


def _assemble_rings(way_segments: list[list[tuple[float, float]]]) -> list[Polygon]:
    """Assemble way segments into closed polygon rings."""
    if not way_segments:
        return []

    # Try to merge segments into closed rings
    remaining = list(way_segments)
    rings: list[list[tuple[float, float]]] = []

    while remaining:
        current = list(remaining.pop(0))
        changed = True
        while changed:
            changed = False
            for i, segment in enumerate(remaining):
                if not segment:
                    continue
                # Try to connect end-to-start
                if _coords_close(current[-1], segment[0]):
                    current.extend(segment[1:])
                    remaining.pop(i)
                    changed = True
                    break
                # Try to connect end-to-end (reversed)
                elif _coords_close(current[-1], segment[-1]):
                    current.extend(reversed(segment[:-1]))
                    remaining.pop(i)
                    changed = True
                    break
                # Try to connect start-to-end
                elif _coords_close(current[0], segment[-1]):
                    current = list(segment[:-1]) + current
                    remaining.pop(i)
                    changed = True
                    break
                # Try to connect start-to-start (reversed)
                elif _coords_close(current[0], segment[0]):
                    current = list(reversed(segment[1:])) + current
                    remaining.pop(i)
                    changed = True
                    break

        # Close the ring if not already closed
        if len(current) >= 4 and not _coords_close(current[0], current[-1]):
            current.append(current[0])

        if len(current) >= 4:
            try:
                poly = Polygon(current)
                if poly.is_valid and poly.area > 0:
                    rings.append(current)
            except Exception:
                pass

    polygons = []
    for ring in rings:
        try:
            poly = Polygon(ring)
            if poly.is_valid and poly.area > 0:
                polygons.append(poly)
        except Exception:
            pass

    return polygons


def _coords_close(a: tuple[float, float], b: tuple[float, float], tol: float = 1e-7) -> bool:
    """Check if two coordinates are approximately equal."""
    return abs(a[0] - b[0]) < tol and abs(a[1] - b[1]) < tol


def import_fare_zones_from_osm(
    db: Session,
    *,
    department: str = "Cochabamba",
    admin_level: int = 8,
) -> dict[str, int]:
    """Import fare zones from OSM administrative boundaries.

    Queries the Overpass API for admin boundaries within the given department
    and upserts FareZone records (matched by name).

    Returns a dict with 'created' and 'updated' counts.
    """
    print(f"Querying Overpass API for admin_level={admin_level} in {department}...")
    data = _query_overpass(department, admin_level)

    print(f"Received {len(data.get('elements', []))} elements, building polygons...")
    named_polygons = _build_polygons(data)

    if not named_polygons:
        print("No valid polygons found.")
        return {"created": 0, "updated": 0}

    print(f"Found {len(named_polygons)} zone(s): {', '.join(name for name, _ in named_polygons)}")

    created = 0
    updated = 0

    for name, polygon in named_polygons:
        existing = db.execute(
            select(FareZone).where(FareZone.name == name)
        ).scalars().first()

        boundary = from_shape(polygon, srid=4326)

        if existing:
            existing.boundary = boundary
            updated += 1
        else:
            zone = FareZone(name=name, boundary=boundary)
            db.add(zone)
            created += 1

    db.commit()
    return {"created": created, "updated": updated}
