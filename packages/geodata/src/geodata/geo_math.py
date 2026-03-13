"""Pure geo-math helpers (no database or external dependencies)."""

import math


def haversine_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Great-circle distance in metres between two WGS-84 points."""
    r = 6_371_000
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = (
        math.sin(dp / 2) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    )
    return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def offset_lon_lat(
    lon: float, lat: float, east_m: float, north_m: float
) -> tuple[float, float]:
    """Shift a WGS-84 point by *east_m* / *north_m* metres (flat-earth approx)."""
    lat_out = lat + (north_m / 111_320.0)
    cos_lat = max(1e-6, abs(math.cos(math.radians(lat_out))))
    lon_out = lon + (east_m / (111_320.0 * cos_lat))
    return lon_out, lat_out


def heading_and_perp(
    route: list[list[float]], idx: int
) -> tuple[tuple[float, float], tuple[float, float]]:
    """Return unit (heading, perpendicular) vectors at *idx* along *route*.

    Each vector is (east, north) in metres-scale units.
    """
    if len(route) < 2:
        return (1.0, 0.0), (0.0, 1.0)
    i0 = max(0, idx - 1)
    i1 = min(len(route) - 1, idx + 1)
    lon0, lat0 = route[i0]
    lon1, lat1 = route[i1]
    mean_lat = math.radians((lat0 + lat1) / 2.0)
    east = (lon1 - lon0) * 111_320.0 * math.cos(mean_lat)
    north = (lat1 - lat0) * 111_320.0
    norm = max(1e-6, math.sqrt(east**2 + north**2))
    hd = (east / norm, north / norm)
    perp = (-hd[1], hd[0])
    return hd, perp


def interpolate_route(
    route: list[list[float]], step_m: float
) -> list[list[float]]:
    """Re-sample *route* (list of [lon, lat]) at roughly *step_m* spacing."""
    if len(route) < 2:
        return route
    seg_lengths = []
    for i in range(len(route) - 1):
        lon0, lat0 = route[i]
        lon1, lat1 = route[i + 1]
        seg_lengths.append(haversine_m(lon0, lat0, lon1, lat1))
    total = sum(seg_lengths)
    if total <= 0:
        return [route[0], route[-1]]

    points_count = max(2, int(total / max(0.5, step_m)) + 1)
    targets = [total * i / (points_count - 1) for i in range(points_count)]
    interpolated: list[list[float]] = []
    seg_idx = 0
    seg_start_dist = 0.0
    for target in targets:
        while (
            seg_idx < len(seg_lengths) - 1
            and seg_start_dist + seg_lengths[seg_idx] < target
        ):
            seg_start_dist += seg_lengths[seg_idx]
            seg_idx += 1
        lon0, lat0 = route[seg_idx]
        lon1, lat1 = route[seg_idx + 1]
        seg_len = max(1e-6, seg_lengths[seg_idx])
        frac = max(0.0, min(1.0, (target - seg_start_dist) / seg_len))
        lon = lon0 + (lon1 - lon0) * frac
        lat = lat0 + (lat1 - lat0) * frac
        interpolated.append([lon, lat])
    return interpolated
