"""Helpers for snapping reconstructed routes back to the road grid."""

from __future__ import annotations

from .. import match


def dedupe_consecutive_coordinates(
    coordinates: list[list[float]],
) -> list[list[float]]:
    """Remove consecutive duplicate coordinates from a route."""

    deduped: list[list[float]] = []
    for lon, lat in coordinates:
        point = [float(lon), float(lat)]
        if not deduped or deduped[-1] != point:
            deduped.append(point)
    return deduped


def snap_route_to_road_grid(
    route_coordinates: list[list[float]],
    *,
    costing: str = "bus",
    search_radius: int = 60,
    gps_accuracy: int = 20,
) -> list[list[float]]:
    """Snap a reconstructed route back onto the road network via Valhalla."""

    if len(route_coordinates) < 2:
        raise ValueError("Route must contain at least 2 coordinates before snapping")

    trace_points = [
        {"lat": lat, "lon": lon}
        for lon, lat in route_coordinates
    ]
    result = match.trace_match(
        trace_points,
        costing=costing,
        search_radius=search_radius,
        gps_accuracy=gps_accuracy,
    )

    snapped = [
        [float(lon), float(lat)]
        for lat, lon in result.shape_coords
    ]
    snapped = dedupe_consecutive_coordinates(snapped)
    if len(snapped) < 2:
        raise ValueError("Road-grid snapping produced fewer than 2 coordinates")
    return snapped
