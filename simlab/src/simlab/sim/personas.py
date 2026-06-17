"""Personas: simulated riders with devices, habits and trip histories.

Votes in the real system require a trip history (≥3 cleaned trips on
the line in the last 2 weeks), so the simulation generates trips over
a calendar of ``sim_days`` days, not just a bag of traces.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from ..scenario import PersonaSpec, ScenarioConfig
from .route import ParamRoute

SERVICE_START_H = 6
SERVICE_END_H = 21


@dataclass
class Persona:
    device_id: str
    spec: PersonaSpec


@dataclass
class SimTrip:
    trip_id: str
    device_id: str
    persona_name: str
    day: int                      # 0-based day within the simulation
    started_at: datetime
    forward: bool
    board_m: float                # arc length along the trip's route
    alight_m: float
    route_name: str = "main"      # base route the group rides
    is_detour: bool = False
    points: list = field(default_factory=list)   # filled by the GPS layer


def build_personas(config: ScenarioConfig) -> list[Persona]:
    """One device per trace: a group contributing N traces starts as N
    one-trip devices. Voters (multi-trace regulars) are formed afterwards by
    aggregating some of these onto shared devices — see ``form_voters``."""
    personas: list[Persona] = []
    for spec in config.personas:
        for i in range(spec.traces):
            personas.append(Persona(device_id=f"sim:{spec.name}:{i}", spec=spec))
    return personas


def generate_trip_history(
    personas: list[Persona],
    routes: dict[str, ParamRoute] | ParamRoute,
    config: ScenarioConfig,
    rng: random.Random,
    *,
    sim_start: datetime | None = None,
) -> list[SimTrip]:
    """One trip per device (one independent trace). The trip's length + position
    come from the per-group distance/position model (see ``_trip_extent``). The
    day is only for timestamp realism — eligibility is structural, not windowed.

    ``routes`` maps RouteSpec names to parametrized routes (a bare ParamRoute is
    accepted for single-route use and tests).
    """
    sim_start = sim_start or datetime(2026, 5, 1, tzinfo=UTC)
    if isinstance(routes, ParamRoute):
        routes = {spec.name: routes for spec in config.personas} | {"main": routes}
    days = max(1, config.sim_days)
    trips: list[SimTrip] = []

    for persona in personas:
        spec = persona.spec
        route_name = spec.route or "main"
        route = routes[route_name]
        day = rng.randrange(days)
        hour = rng.uniform(SERVICE_START_H, SERVICE_END_H)
        started_at = sim_start + timedelta(days=day, hours=hour)
        # Routes are directional: the return leg of a line is its own base
        # route. A group runs one way — forward (drawn order) or backward.
        forward = spec.direction != "backward"

        w0, w1 = spec.travel_window
        w0, w1 = max(0.0, min(w0, w1)), min(1.0, max(w0, w1))
        board_frac, alight_frac = _trip_extent(spec, w0, w1, route.length_m, rng)

        trips.append(SimTrip(
            trip_id=f"{persona.device_id}:t{len(trips)}",
            device_id=persona.device_id,
            persona_name=spec.name,
            day=day,
            started_at=started_at,
            forward=forward,
            board_m=board_frac * route.length_m,
            alight_m=alight_frac * route.length_m,
            route_name=route_name,
        ))

    trips.sort(key=lambda t: t.started_at)
    return trips


def _weight_at(weights: list[float], t: float) -> float:
    """Density `weights` (bins start→end) evaluated at fraction t∈[0,1].
    Empty/all-zero = uniform (1.0)."""
    if not weights or not any(w > 0 for w in weights):
        return 1.0
    n = len(weights)
    idx = min(n - 1, max(0, int(t * n)))
    return max(0.0, weights[idx])


def form_voters(
    trips: list[SimTrip],
    routes: dict[str, ParamRoute] | ParamRoute,
    config: ScenarioConfig,
    rng: random.Random,
) -> list[str]:
    """Turn each group's `voters` regulars into eligible voters by *aggregating*
    `eligibility_min_trips` of its existing traces onto one device — selected by
    `vote_position_weights` (where the regulars concentrate). This only relabels
    `device_id`; the trace geometry/count the reconstruction sees is unchanged.

    Returns human-readable warnings for groups that couldn't supply enough
    traces in their vote zone. Mutates `trips` in place.
    """
    if isinstance(routes, ParamRoute):
        routes = {spec.name: routes for spec in config.personas} | {"main": routes}
    specs = {spec.name: spec for spec in config.personas}
    min_trips = max(1, config.votes.eligibility_min_trips)

    by_group: dict[str, list[SimTrip]] = {}
    for t in trips:
        by_group.setdefault(t.persona_name, []).append(t)

    shortfalls: list[str] = []
    total_want = 0
    total_made = 0
    for name, spec in specs.items():
        want = int(spec.voters or 0)
        if want <= 0:
            continue
        total_want += want
        group_trips = by_group.get(name, [])
        route = routes.get(spec.route or "main")
        length = route.length_m if route else 0.0
        w0, w1 = spec.travel_window
        w0, w1 = max(0.0, min(w0, w1)), min(1.0, max(w0, w1))
        span = max(w1 - w0, 1e-9)

        # Each trip's pick-weight = vote profile at its centre within the zone.
        pool: list[tuple[SimTrip, float]] = []
        for t in group_trips:
            centre = (t.board_m + t.alight_m) / 2 / length if length > 0 else 0.5
            frac = min(1.0, max(0.0, (centre - w0) / span))
            wgt = _weight_at(spec.vote_position_weights, frac)
            if wgt > 0:
                pool.append((t, wgt))

        can_form = min(want, len(pool) // min_trips)
        total_made += can_form
        if can_form < want:
            reason = ("no traces in its vote zone" if not pool
                      else f"only {len(pool)} traces in its vote zone, needs "
                           f"{want * min_trips}")
            shortfalls.append(
                f"group {name!r}: short {want - can_form} voter(s) — {reason}")

        # Weighted selection without replacement → min_trips per voter device.
        items = list(pool)
        for k in range(can_form):
            chosen: list[SimTrip] = []
            for _ in range(min_trips):
                total = sum(w for _, w in items)
                r = rng.random() * total
                acc = 0.0
                pick = len(items) - 1
                for i, (_, w) in enumerate(items):
                    acc += w
                    if r <= acc:
                        pick = i
                        break
                chosen.append(items.pop(pick)[0])
            voter_id = f"sim:{name}:voter{k}"
            for t in chosen:
                t.device_id = voter_id

    if shortfalls:
        return [f"Couldn't form all voters. Expected: {total_want}, "
                f"assigned: {total_made}.", *shortfalls]
    return []


def _sample_position(lo: float, hi: float, weights, rng: random.Random) -> float:
    """A point in [lo, hi] for a trip's centre, sampled from the density profile
    `weights` (bin weights start→end; empty/zero = uniform)."""
    if hi <= lo:
        return (lo + hi) / 2
    total = sum(w for w in weights if w > 0) if weights else 0.0
    if total <= 0:
        t = rng.random()
    else:
        # pick a bin proportional to its weight, then uniform within it.
        n = len(weights)
        r = rng.random() * total
        cum = 0.0
        idx = n - 1
        for i, w in enumerate(weights):
            cum += max(0.0, w)
            if r <= cum:
                idx = i
                break
        t = (idx + rng.random()) / n
    return lo + t * (hi - lo)


def _trip_extent(spec, w0: float, w1: float, route_len_m: float,
                 rng: random.Random) -> tuple[float, float]:
    """(board_frac, alight_frac) for one trip inside the window [w0, w1].

    Length ~ Normal(mean, std) when mean_trip_distance_m is set (clamped to the
    zone); otherwise the trip rides the whole window. The centre is then placed
    along the zone per spec.trip_position_weights.
    """
    window_len = max(w1 - w0, 1e-6)
    if not (spec.mean_trip_distance_m and route_len_m > 0):
        return w0, w1  # no distance model → ride the whole zone
    mean_f = spec.mean_trip_distance_m / route_len_m
    std_f = spec.trip_distance_std_m / route_len_m
    length = rng.gauss(mean_f, std_f) if std_f > 0 else mean_f
    length = min(window_len, max(0.02, length))
    center = _sample_position(w0 + length / 2, w1 - length / 2,
                              spec.trip_position_weights, rng)
    return center - length / 2, center + length / 2
