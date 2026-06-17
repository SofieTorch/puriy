"""Coverage metrics for a reconstruction run.

`completeness` = of the route stretch the rider groups were *defined* to cover
(the union of their travel windows, across all ramales, merged so a shared
trunk counts once), how much did the reconstruction actually recover. Capped to
the rider-defined envelope on purpose: a scenario may only exercise a section.

`coverage_envelope` = that envelope as a fraction of the full drawn route(s).
"""

from __future__ import annotations

import math

from geodata.geo_math import interpolate_route

_CELL_M = 20.0
_STEP_M = 8.0


def slice_by_fraction(coords, f0: float, f1: float):
    """Sub-polyline of `coords` between arc-length fractions f0..f1."""
    dense = interpolate_route([[c[0], c[1]] for c in coords], _STEP_M)
    n = len(dense)
    if n < 2:
        return [(c[0], c[1]) for c in coords]
    lo = max(0, min(n - 1, round(f0 * (n - 1))))
    hi = max(lo + 1, min(n - 1, round(f1 * (n - 1))))
    return [(p[0], p[1]) for p in dense[lo : hi + 1]]


def _cells(polylines, ref_lat: float, *, dilate: bool = False) -> set:
    """Set of ~_CELL_M grid cells touched by the (densified) polylines."""
    mlon = 111_320 * math.cos(math.radians(ref_lat))
    mlat = 110_540
    cells: set = set()
    for line in polylines:
        dense = (interpolate_route([[p[0], p[1]] for p in line], _STEP_M)
                 if len(line) >= 2 else line)
        for lon, lat in dense:
            cells.add((int(lon * mlon // _CELL_M), int(lat * mlat // _CELL_M)))
    if not dilate:
        return cells
    out: set = set()
    for x, y in cells:
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                out.add((x + dx, y + dy))
    return out


def merged_completeness(envelope_polylines, recon_polylines, ref_lat: float):
    """(completeness, envelope_cell_count). Grid-merge the envelope across
    ramales (shared trunk counted once) and the reconstruction, then take the
    covered share. Returns (None, 0) if there is no envelope."""
    env = _cells(envelope_polylines, ref_lat)
    if not env:
        return None, 0
    recon = _cells(recon_polylines, ref_lat, dilate=True)
    return len(env & recon) / len(env), len(env)


def coverage_metrics(personas, rideable, default_route, recon_routes) -> dict:
    """Compute completeness + coverage_envelope for a run.

    personas: scenario PersonaSpec list (have .route, .travel_window).
    rideable: {route_name: shapely route} of ridden base routes.
    default_route: route name used when a persona's route is None.
    recon_routes: reconstructed ConsensusRoute list (have .geometry).
    """
    if not rideable:
        return {"completeness": None, "coverage_envelope": None}
    ref_lat = list(rideable.values())[0].coords[0][1]

    envelope = []
    for spec in personas:
        name = getattr(spec, "route", None) or default_route
        route = rideable.get(name)
        if route is None:
            continue
        lo, hi = spec.travel_window
        envelope.append(slice_by_fraction(list(route.coords), lo, hi))

    recon_polys = [[(lon, lat) for lon, lat in r.geometry]
                   for r in recon_routes if len(r.geometry) >= 2]

    completeness, env_cells = merged_completeness(envelope, recon_polys, ref_lat)

    full_cells = _cells([[(c[0], c[1]) for c in r.coords] for r in rideable.values()],
                        ref_lat)
    coverage_envelope = (env_cells / len(full_cells)) if full_cells else None

    return {
        "completeness": round(completeness, 3) if completeness is not None else None,
        "coverage_envelope": round(coverage_envelope, 3)
        if coverage_envelope is not None else None,
    }
