"""Simplify recording session paths using PostGIS ST_Simplify (Douglas-Peucker)."""

from typing import Any

from shapely import from_wkt, wkb
from shapely.geometry import LineString
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from database.models.recording import LocationPoint, RecordingSession


def _match_kept_point_ids(
    original_points: list[LocationPoint],
    simplified_coords: list[tuple[float, float]],
) -> set[int]:
    """
    Match simplified vertices to original points; return IDs of points to keep.

    RDP keeps a subset of original vertices. For each simplified vertex, find the
    closest original point along the path order (to preserve sequence).
    """
    if not original_points or not simplified_coords:
        return set()

    kept_ids: set[int] = set()
    last_idx = -1

    for lon, lat in simplified_coords:
        best_idx: int | None = None
        best_dist: float = float("inf")

        for j in range(last_idx + 1, len(original_points)):
            p = original_points[j]
            dx = lon - p.longitude
            dy = lat - p.latitude
            dist = dx * dx + dy * dy
            if dist < best_dist:
                best_dist = dist
                best_idx = j

        if best_idx is not None:
            kept_ids.add(original_points[best_idx].id)
            last_idx = best_idx

    return kept_ids


def simplify_recording_session(
    db: Session,
    session_id: int,
    tolerance: float = 0.00005,
) -> dict[str, Any]:
    """
    Apply PostGIS ST_Simplify (Douglas-Peucker) to a recording session.

    - Overwrites computed_path with the simplified linestring
    - Deletes location points that were filtered out by RDP

    Tolerance is in degrees (WGS84); ~0.00005 ≈ 5 m at mid-latitudes.

    Returns a summary: points_before, points_after, points_removed.
    """
    session = db.get(RecordingSession, session_id)
    if not session:
        raise ValueError(f"Recording session {session_id} not found")

    points = db.execute(
        select(LocationPoint)
        .where(LocationPoint.session_id == session_id)
        .order_by(LocationPoint.timestamp)
    ).scalars().all()

    if len(points) < 2:
        return {"points_before": len(points), "points_after": len(points), "points_removed": 0}

    points_before = len(points)

    # Build linestring from points (or use existing computed_path if present)
    if session.computed_path is not None:
        if hasattr(session.computed_path, "data"):
            geom = wkb.loads(bytes(session.computed_path.data))
        else:
            geom = session.computed_path
        if not isinstance(geom, LineString):
            coords = [(p.longitude, p.latitude) for p in points]
            linestring_wkt = f"SRID=4326;LINESTRING({', '.join(f'{lon} {lat}' for lon, lat in coords)})"
        else:
            linestring_wkt = f"SRID=4326;{geom.wkt}"
    else:
        coords = [(p.longitude, p.latitude) for p in points]
        linestring_wkt = f"SRID=4326;LINESTRING({', '.join(f'{lon} {lat}' for lon, lat in coords)})"

    # Run ST_Simplify in PostGIS
    result = db.execute(
        text(
            """
            SELECT ST_AsEWKT(ST_Simplify(ST_GeomFromEWKT(:wkt)::geometry, :tolerance))
            """
        ),
        {"wkt": linestring_wkt, "tolerance": tolerance},
    )
    row = result.fetchone()
    if not row or not row[0]:
        return {"points_before": points_before, "points_after": points_before, "points_removed": 0}

    simplified_wkt = row[0]
    wkt_part = simplified_wkt.split(";", 1)[-1] if ";" in simplified_wkt else simplified_wkt
    simplified_geom = from_wkt(wkt_part)
    simplified_coords = list(simplified_geom.coords) if isinstance(simplified_geom, LineString) else []

    kept_ids = _match_kept_point_ids(points, simplified_coords)

    # Delete location points not in kept set
    to_delete = [p for p in points if p.id not in kept_ids]
    for p in to_delete:
        db.delete(p)

    # Update session computed_path with simplified geometry
    session.computed_path = func.ST_GeomFromEWKT(simplified_wkt)

    db.flush()
    points_after = len(kept_ids)

    return {
        "points_before": points_before,
        "points_after": points_after,
        "points_removed": points_before - points_after,
    }
