"""Fare report simulation: boarding/alighting points + amounts.

Fare areas belong to each rider group (PersonaSpec.fare_areas) and are
defined along that group's base route: a trip pays the most expensive
area it traverses, or the global base fare when none applies.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime

from ..scenario import ScenarioConfig
from .personas import SimTrip
from .route import ParamRoute


@dataclass(frozen=True)
class FareReport:
    device_id: str
    trip_id: str
    reported_at: datetime
    boarding_lon: float
    boarding_lat: float
    alighting_lon: float
    alighting_lat: float
    amount_bob: float
    is_misreport: bool
    fare_area: str | None = None  # most expensive area traversed
    route_name: str = "main"


def simulate_fares(
    trips: list[SimTrip],
    routes: dict[str, ParamRoute] | ParamRoute,
    config: ScenarioConfig,
    rng: random.Random,
) -> list[FareReport]:
    fm = config.fares
    if isinstance(routes, ParamRoute):
        routes = {t.route_name: routes for t in trips}
    persona_by_name = {spec.name: spec for spec in config.personas}
    reports: list[FareReport] = []

    for trip in trips:
        spec = persona_by_name.get(trip.persona_name)
        report_prob = spec.fare_report_prob if spec else 0.3
        if rng.random() > report_prob:
            continue

        route = routes[trip.route_name]
        # A reverse run boards at the far end of the same physical
        # stretch and alights at the near end.
        board_m, alight_m = (
            (trip.board_m, trip.alight_m)
            if trip.forward
            else (trip.alight_m, trip.board_m)
        )
        b_lon, b_lat = route.position_at(board_m)
        a_lon, a_lat = route.position_at(alight_m)

        # The trip pays the most expensive fare area of its group's
        # route that it traverses; base fare when no area overlaps.
        lo = min(trip.board_m, trip.alight_m) / max(route.length_m, 1e-9)
        hi = max(trip.board_m, trip.alight_m) / max(route.length_m, 1e-9)
        amount = fm.base_fare_bob
        area_name: str | None = None
        for area in (spec.fare_areas if spec else []):
            a0, a1 = sorted((area.start_fraction, area.end_fraction))
            if a0 < hi and a1 > lo and area.amount_bob >= amount:
                amount = area.amount_bob
                area_name = area.name

        misreport = rng.random() < fm.misreport_prob
        if misreport:
            amount = round(max(0.5, amount + rng.choice([-1.0, 1.0, 2.0])), 2)

        reports.append(FareReport(
            device_id=trip.device_id,
            trip_id=trip.trip_id,
            reported_at=trip.started_at,
            boarding_lon=b_lon,
            boarding_lat=b_lat,
            alighting_lon=a_lon,
            alighting_lat=a_lat,
            amount_bob=round(amount, 2),
            is_misreport=misreport,
            fare_area=area_name,
            route_name=trip.route_name,
        ))
    return reports
