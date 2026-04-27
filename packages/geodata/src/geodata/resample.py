"""Resample cleaned Trip points to uniform distance intervals.

Provides a pure ``resample_points`` function that can be used by
reconstruction strategies that need uniform-interval input (e.g. DBSCAN).
"""

from dataclasses import dataclass
from datetime import datetime, timezone

from database.models import TripPoint

from .geo_math import haversine_m


@dataclass
class ResampledPoint:
    timestamp: datetime
    latitude: float
    longitude: float


def resample_points(
    points: list[TripPoint],
    interval_meters: float,
) -> list[ResampledPoint]:
    """Resample a list of TripPoints to uniform distance intervals.

    A uniform grid is built from 0 to the total arc-length of the path, with
    steps of ``interval_meters``.  Latitude, longitude, and timestamp are all
    linearly interpolated between the two surrounding original points.

    Parameters
    ----------
    points : list[TripPoint]
        Cleaned trip points sorted by timestamp.
    interval_meters : float
        Desired spacing between output points in metres (e.g. 10, 20).

    Returns
    -------
    list[ResampledPoint]
        Uniformly-spaced points from the start to the end of the path.
    """
    if len(points) < 2:
        return [
            ResampledPoint(
                timestamp=points[0].timestamp,
                latitude=points[0].latitude,
                longitude=points[0].longitude,
            )
        ] if points else []

    sorted_pts = sorted(points, key=lambda p: p.timestamp)

    # Cumulative arc-length at each original point
    cum: list[float] = [0.0]
    for i in range(1, len(sorted_pts)):
        prev, cur = sorted_pts[i - 1], sorted_pts[i]
        cum.append(cum[-1] + haversine_m(prev.longitude, prev.latitude, cur.longitude, cur.latitude))

    total = cum[-1]
    if total <= 0:
        return []

    # Build uniform distance grid
    grid: list[float] = []
    d = 0.0
    while d <= total + 1e-6:
        grid.append(d)
        d += interval_meters

    orig_ts = [p.timestamp.timestamp() for p in sorted_pts]
    orig_lat = [p.latitude for p in sorted_pts]
    orig_lon = [p.longitude for p in sorted_pts]

    result: list[ResampledPoint] = []
    j = 0  # cursor into cum[] — avoids O(n²)

    for target_d in grid:
        while j < len(cum) - 2 and cum[j + 1] < target_d:
            j += 1

        d0, d1 = cum[j], cum[j + 1]
        span = d1 - d0
        frac = (target_d - d0) / span if span > 1e-9 else 0.0
        frac = max(0.0, min(1.0, frac))

        lat = orig_lat[j] + frac * (orig_lat[j + 1] - orig_lat[j])
        lon = orig_lon[j] + frac * (orig_lon[j + 1] - orig_lon[j])
        ts = orig_ts[j] + frac * (orig_ts[j + 1] - orig_ts[j])

        result.append(
            ResampledPoint(
                timestamp=datetime.fromtimestamp(ts, tz=timezone.utc),
                latitude=lat,
                longitude=lon,
            )
        )

    return result
