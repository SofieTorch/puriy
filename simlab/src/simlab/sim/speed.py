"""Bus speed profile: cruise speed with demand stops and intersections.

Produces arc-length position as a function of time for one trip, which
the GPS layer samples at the device's reporting rate. Trufis stop on
demand (no fixed stops), modelled as randomly-spaced dwell events.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from ..scenario import SpeedModel


@dataclass
class SpeedProfile:
    """Positions sampled at a fixed internal tick (1s)."""

    positions_m: list[float]   # arc-length position at each second
    tick_s: float = 1.0

    @property
    def duration_s(self) -> float:
        return (len(self.positions_m) - 1) * self.tick_s

    def position_at(self, t_s: float) -> float:
        if t_s <= 0:
            return self.positions_m[0]
        idx = t_s / self.tick_s
        i = int(idx)
        if i >= len(self.positions_m) - 1:
            return self.positions_m[-1]
        frac = idx - i
        return self.positions_m[i] + frac * (self.positions_m[i + 1] - self.positions_m[i])


def simulate_speed_profile(
    start_m: float,
    end_m: float,
    model: SpeedModel,
    rng: random.Random,
) -> SpeedProfile:
    """Simulate one trip's movement from start_m to end_m arc length."""
    cruise = max(
        model.min_speed_mps,
        min(model.max_speed_mps, rng.gauss(model.base_speed_mps, model.speed_stddev_mps)),
    )

    # Pre-draw dwell events along the stretch.
    events: list[tuple[float, float]] = []  # (position_m, dwell_s)
    pos = start_m
    while True:
        pos += rng.expovariate(1.0 / model.stop_spacing_m)
        if pos >= end_m:
            break
        events.append((pos, rng.uniform(model.stop_dwell_min_s, model.stop_dwell_max_s)))
    pos = start_m
    while True:
        pos += rng.expovariate(1.0 / model.intersection_spacing_m)
        if pos >= end_m:
            break
        events.append((pos, rng.uniform(0.0, model.intersection_dwell_max_s)))
    events.sort()

    positions = [start_m]
    current = start_m
    dwell_remaining = 0.0
    event_index = 0
    # Walk 1-second ticks; speed varies slowly around the cruise speed.
    speed = cruise
    while current < end_m:
        if dwell_remaining > 0:
            dwell_remaining = max(0.0, dwell_remaining - 1.0)
        else:
            speed = max(
                model.min_speed_mps,
                min(model.max_speed_mps, speed + rng.gauss(0.0, 0.4)),
            )
            step = speed
            next_pos = current + step
            if event_index < len(events) and next_pos >= events[event_index][0]:
                next_pos, dwell_remaining = events[event_index]
                event_index += 1
            current = min(next_pos, end_m)
        positions.append(current)
        if len(positions) > 6 * 3600:  # safety: no trip longer than 6h
            break
    return SpeedProfile(positions_m=positions)
