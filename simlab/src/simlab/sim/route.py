"""Ground-truth route loading and arc-length parametrization."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

from geodata.geo_math import haversine_m

LonLat = tuple[float, float]


@dataclass
class ParamRoute:
    """A route parametrized by arc length, for position lookups."""

    coords: list[LonLat]
    cumulative_m: list[float]

    @property
    def length_m(self) -> float:
        return self.cumulative_m[-1]

    def position_at(self, distance_m: float) -> LonLat:
        """Point at the given arc length (clamped to the route)."""
        d = max(0.0, min(distance_m, self.length_m))
        cum = self.cumulative_m
        lo, hi = 0, len(cum) - 1
        while lo < hi:
            mid = (lo + hi) // 2
            if cum[mid] < d:
                lo = mid + 1
            else:
                hi = mid
        i = max(1, lo)
        seg = cum[i] - cum[i - 1]
        t = 0.0 if seg == 0 else (d - cum[i - 1]) / seg
        a, b = self.coords[i - 1], self.coords[i]
        return (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))

    def heading_at(self, distance_m: float) -> tuple[float, float]:
        """Unit (east, north) heading at the given arc length."""
        d = max(0.0, min(distance_m, self.length_m - 1e-9))
        cum = self.cumulative_m
        i = next((k for k in range(1, len(cum)) if cum[k] > d), len(cum) - 1)
        a, b = self.coords[i - 1], self.coords[i]
        east = (b[0] - a[0]) * 111_320.0 * math.cos(math.radians(a[1]))
        north = (b[1] - a[1]) * 111_320.0
        norm = math.hypot(east, north) or 1.0
        return (east / norm, north / norm)

    def slice(self, start_m: float, end_m: float) -> list[LonLat]:
        """Sub-polyline between two arc lengths."""
        start_m = max(0.0, min(start_m, self.length_m))
        end_m = max(start_m, min(end_m, self.length_m))
        points = [self.position_at(start_m)]
        for coord, cum in zip(self.coords, self.cumulative_m):
            if start_m < cum < end_m:
                points.append(coord)
        points.append(self.position_at(end_m))
        return points


def parametrize(coords: list[LonLat]) -> ParamRoute:
    cumulative = [0.0]
    for a, b in zip(coords, coords[1:]):
        cumulative.append(cumulative[-1] + haversine_m(a[0], a[1], b[0], b[1]))
    return ParamRoute(coords=list(coords), cumulative_m=cumulative)


def load_route(path: str | Path) -> ParamRoute:
    """Load the first LineString from a geojson file."""
    data = json.loads(Path(path).read_text())
    features = data.get("features", [data] if data.get("type") == "Feature" else [])
    for feature in features:
        geometry = feature.get("geometry", {})
        if geometry.get("type") == "LineString":
            coords = [(c[0], c[1]) for c in geometry["coordinates"]]
            return parametrize(coords)
        if geometry.get("type") == "MultiLineString":
            coords = [(c[0], c[1]) for line in geometry["coordinates"] for c in line]
            return parametrize(coords)
    raise ValueError(f"no LineString found in {path}")
