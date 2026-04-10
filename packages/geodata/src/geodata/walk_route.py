"""Pedestrian routing via Valhalla's /route API."""

from dataclasses import dataclass

import httpx

from .match import VALHALLA_URL, _decode_polyline6


@dataclass
class WalkResult:
    """Result of a pedestrian route query."""

    coords: list[tuple[float, float]]  # (lon, lat) pairs
    distance_m: float
    duration_s: float


def walk_route(
    origin: tuple[float, float],
    destination: tuple[float, float],
) -> WalkResult:
    """Find a walking route between two points using Valhalla.

    Parameters
    ----------
    origin : tuple[float, float]
        (lon, lat) of the starting point.
    destination : tuple[float, float]
        (lon, lat) of the ending point.

    Returns
    -------
    WalkResult
        Walking path geometry, distance in meters, and duration in seconds.
    """
    body = {
        "locations": [
            {"lon": origin[0], "lat": origin[1]},
            {"lon": destination[0], "lat": destination[1]},
        ],
        "costing": "pedestrian",
        "directions_options": {"units": "meters"},
    }

    resp = httpx.post(f"{VALHALLA_URL}/route", json=body, timeout=30.0)
    resp.raise_for_status()
    data = resp.json()

    leg = data["trip"]["legs"][0]
    summary = data["trip"]["summary"]

    # Decode polyline6 shape — returns (lat, lon), flip to (lon, lat)
    raw_coords = _decode_polyline6(leg["shape"])
    coords = [(lon, lat) for lat, lon in raw_coords]

    # Summary length is in km when units=meters (Valhalla quirk), convert to m
    distance_m = summary["length"] * 1000.0
    duration_s = summary["time"]

    return WalkResult(coords=coords, distance_m=distance_m, duration_s=duration_s)
