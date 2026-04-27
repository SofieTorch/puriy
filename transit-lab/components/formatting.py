"""Display formatting utilities for transit-lab notebooks."""

from geodata.geo_math import haversine_m


def format_duration(seconds: int | float | None) -> str:
    if seconds is None:
        return "\u2014"
    seconds = int(seconds)
    h, r = divmod(seconds, 3600)
    m, s = divmod(r, 60)
    if h:
        return f"{h}h {m}m"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"


def format_distance(meters: float | None) -> str:
    if meters is None:
        return "\u2014"
    if meters >= 1000:
        return f"{meters / 1000:.1f} km"
    return f"{int(meters)} m"


def path_length_m(coords: list[list[float]]) -> float:
    """Total great-circle length of a coordinate path in metres."""
    total = 0.0
    for i in range(1, len(coords)):
        total += haversine_m(coords[i - 1][0], coords[i - 1][1], coords[i][0], coords[i][1])
    return total
