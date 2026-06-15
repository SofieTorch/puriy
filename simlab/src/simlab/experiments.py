"""Reconstruction minimum-requirements experiments — one factorial sweep.

The factors that govern reconstruction *interact* (the minimum number of traces
depends on how much each trace covers and where), so we don't sweep them
separately. We generate the full combination (cartesian product) of the real
inputs and read the response surface off the results:

- **traces** — absolute number of independent GPS traces per group (1 → 100,
  geometric so the low end, where the quality cliff lives, is dense).
- **mean trip distance** — full zone, or a partial fraction of the zone
  (`mean_trip_distance_m`); std held proportional.
- **position shape** — where partial trips concentrate (uniform / center /
  edges …); only meaningful when trips are partial.

`completeness`, `ramales_found`, `trace_distance_*` are *outputs* read per cell.
Voting is a separate study: these scenarios set `voters = 0`. See
experiments/EXPERIMENTS.md.
"""

from __future__ import annotations

import math
from pathlib import Path
from statistics import median
from typing import Any

from .sim.route import load_route

REPO_ROOT = Path(__file__).resolve().parents[3]

# --- factorial axes (tune these to grow/shrink the grid) ---------------------
# Absolute traces per group — geometric, dense at the low end (the cliff).
_TRIPS = [1, 2, 3, 5, 8, 13, 21, 34]
# Partial mean trip distance as a fraction of the scenario's reference zone
# (full coverage is always included as its own cell).
_MEAN_FRACS = [0.5, 0.3]
# Position shapes to cross with the partial means (subset of _pos_shapes()).
_SHAPES = ["uniform", "center", "edges"]
# Std of trip length as a fraction of the mean (variance = std²).
_STD_FRAC = 0.3
# Position bins (mirror builder.js _POS_BINS).
_POS_BINS = 12

# Keys from a base persona that the new model replaces — dropped per variant.
_LEGACY = {"count", "trips_per_week", "vote_propensity",
           "partial_trip_prob", "min_trip_fraction"}


def _pos_shapes() -> dict[str, list[float]]:
    """Density profiles over _POS_BINS bins, mirroring builder.js _POS_SHAPES
    (sampled at each bin centre t = (i+0.5)/N)."""
    n = _POS_BINS
    def sample(fn):
        return [round(max(0.0, fn((i + 0.5) / n)), 4) for i in range(n)]
    return {
        "uniform": sample(lambda t: 1.0),
        "center": sample(lambda t: math.exp(-((t - 0.5) ** 2) / (2 * 0.18 ** 2))),
        "edges": sample(lambda t: 0.08 + abs(t - 0.5) * 2),
        "start": sample(lambda t: max(0.05, 1 - t)),
        "end": sample(lambda t: max(0.05, t)),
    }


def _routes_by_name(base: dict) -> tuple[dict[str, dict], str]:
    """Map route name → route dict, plus the default (first rideable) name."""
    routes = list(base.get("routes") or [])
    if not routes and base.get("route_geojson"):
        routes = [{"name": "main", "path": base["route_geojson"], "role": "main"}]
    by_name = {r["name"]: r for r in routes}
    rideable = [r for r in routes if r.get("role") != "detour"]
    default = (rideable or routes or [{"name": "main"}])[0]["name"]
    return by_name, default


def _zone_length_m(persona: dict, by_name: dict[str, dict], default_route: str,
                   cache: dict[str, float]) -> float:
    """Length in metres of a group's zone = (window span) × route length."""
    route = by_name.get(persona.get("route") or default_route)
    if not route:
        return 0.0
    path = route["path"]
    if path not in cache:
        p = Path(path)
        cache[path] = load_route(p if p.is_absolute() else REPO_ROOT / p).length_m
    w = persona.get("travel_window") or [0.0, 1.0]
    return abs(float(w[1]) - float(w[0])) * cache[path]


def _reference_zone_m(personas: list[dict], by_name: dict[str, dict],
                      default_route: str, cache: dict[str, float]) -> float:
    """Median zone length across groups — the scale the mean axis is built on."""
    lengths = [_zone_length_m(p, by_name, default_route, cache) for p in personas]
    lengths = [length for length in lengths if length > 0]
    return median(lengths) if lengths else 0.0


def experiment_variants(base: dict[str, Any], base_id: str) -> list[dict[str, Any]]:
    """The full factorial: traces × (full | mean × position shape), preserving
    the base scenario's structure (every route/ramal, every group with its
    zone). Each group gets the same `traces` (the controlled variable) and
    `voters = 0`."""
    personas = base.get("personas") or [{"name": "riders"}]
    by_name, default_route = _routes_by_name(base)
    len_cache: dict[str, float] = {}
    ref = _reference_zone_m(personas, by_name, default_route, len_cache)
    shapes = _pos_shapes()

    drop = {"name", "description", "personas", "sim_days", "vote_day"}
    globals_ = {k: v for k, v in base.items() if k not in drop}

    def variant(label, desc, traces, mean_m, std_m, weights):
        pers = []
        for p in personas:
            q = {k: v for k, v in p.items() if k not in _LEGACY}
            q.update(traces=traces, voters=0,
                     mean_trip_distance_m=mean_m, trip_distance_std_m=std_m)
            if weights is not None:
                q["trip_position_weights"] = list(weights)
            pers.append(q)
        return {**globals_, "name": f"{base_id}_{label}",
                "description": f"[{base_id}] {desc}",
                "personas": pers, "sim_days": 7, "vote_day": 7}

    out: list[dict[str, Any]] = []
    n = 1
    for traces in _TRIPS:
        # Full-coverage cell — position/shape are moot when trips ride the zone.
        out.append(variant(f"F{n:03d}_t{traces}_full",
                           f"{traces} traces/group, full-zone trips.",
                           traces, None, 0.0, None))
        n += 1
        for mf in _MEAN_FRACS:
            mean_m = round(mf * ref)
            std_m = round(_STD_FRAC * mean_m)
            for shape in _SHAPES:
                out.append(variant(
                    f"F{n:03d}_t{traces}_m{mean_m}_{shape}",
                    f"{traces} traces/group, avg {mean_m} m, {shape} distribution.",
                    traces, mean_m, std_m, shapes[shape]))
                n += 1
    return out
