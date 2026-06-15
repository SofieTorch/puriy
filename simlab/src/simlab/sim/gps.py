"""GPS sampling: speed profile positions + receiver noise.

The noise vocabulary follows geodata.simulate (gaussian, perpendicular,
jumps, missing, timestamp jitter), applied on top of speed-profile
positions instead of constant-speed interpolation. Each persona scales
the noise with its multiplier (cheap-phone personas are noisier).
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from datetime import datetime, timedelta

from ..scenario import ScenarioConfig
from .personas import SimTrip
from .route import ParamRoute
from .speed import simulate_speed_profile

M_PER_DEG_LAT = 111_320.0


@dataclass(frozen=True)
class GpsPoint:
    lon: float
    lat: float
    timestamp: datetime


def _offset(lon: float, lat: float, east_m: float, north_m: float) -> tuple[float, float]:
    return (
        lon + east_m / (M_PER_DEG_LAT * math.cos(math.radians(lat))),
        lat + north_m / M_PER_DEG_LAT,
    )


def simulate_trip_points(
    trip: SimTrip,
    route: ParamRoute,
    config: ScenarioConfig,
    rng: random.Random,
    *,
    noise_multiplier: float = 1.0,
    geometry_override: ParamRoute | None = None,
) -> list[GpsPoint]:
    """Generate the GPS points for one trip (fills trip.points too).

    ``geometry_override`` substitutes the route geometry (detours)
    while keeping board/alight arc lengths relative to the original.
    """
    geometry = geometry_override or route
    noise = config.noise
    sampling = max(0.5, trip_sampling_rate(trip, config))

    profile = simulate_speed_profile(trip.board_m, trip.alight_m, config.speed, rng)

    drift_bearing = math.radians(noise.biased_drift_bearing_deg)
    # Gauss-Markov (AR1) state for the slowly-drifting receiver error.
    # Real GPS error is temporally correlated, not white: consecutive
    # fixes are similar, so a trace wanders smoothly instead of
    # scattering perpendicular each sample (which produced the
    # tick/spike artifacts and gave the matcher jagged input). State
    # decays toward zero with correlation time tau; rho per step =
    # exp(-dt/tau). tau=0 reproduces the old white noise.
    tau = noise.gps_correlation_time_s
    gm_east = gm_north = gm_perp = 0.0
    if tau > 0 and noise.gaussian_enabled:
        gm_east = rng.gauss(0.0, noise.gaussian_sigma_m) * noise_multiplier
        gm_north = rng.gauss(0.0, noise.gaussian_sigma_m) * noise_multiplier
    if tau > 0 and noise.perpendicular_enabled:
        gm_perp = rng.gauss(0.0, noise.perpendicular_sigma_m) * noise_multiplier
    last_t = 0.0

    points: list[GpsPoint] = []
    t = 0.0
    index = 0
    while t <= profile.duration_s:
        index += 1
        if noise.missing_enabled and rng.random() < noise.missing_probability:
            t += sampling
            continue

        pos_m = profile.position_at(t)
        # Reverse runs traverse the same physical stretch backwards:
        # from alight_m down to board_m — NOT the mirrored stretch at
        # the other end of the route, which would leak trips outside
        # the group's travel window.
        geo_pos = pos_m if trip.forward else (trip.board_m + trip.alight_m) - pos_m
        lon, lat = geometry.position_at(geo_pos)
        east_h, north_h = geometry.heading_at(geo_pos)
        perp_e, perp_n = -north_h, east_h
        progress = t / max(profile.duration_s, 1e-9)
        dt = max(t - last_t, 1e-6)
        last_t = t
        rho = math.exp(-dt / tau) if tau > 0 else 0.0
        keep = math.sqrt(max(0.0, 1.0 - rho * rho))

        east = north = 0.0
        if noise.gaussian_enabled:
            sigma = noise.gaussian_sigma_m * noise_multiplier
            if tau > 0:
                gm_east = rho * gm_east + keep * rng.gauss(0.0, sigma)
                gm_north = rho * gm_north + keep * rng.gauss(0.0, sigma)
                east += gm_east
                north += gm_north
            else:
                east += rng.gauss(0.0, sigma)
                north += rng.gauss(0.0, sigma)
        if noise.perpendicular_enabled:
            psigma = noise.perpendicular_sigma_m * noise_multiplier
            if tau > 0:
                gm_perp = rho * gm_perp + keep * rng.gauss(0.0, psigma)
                perp = gm_perp
            else:
                perp = rng.gauss(0.0, psigma)
            east += perp_e * perp
            north += perp_n * perp
        if noise.zigzag_enabled and noise.zigzag_period_points >= 2:
            wave = noise.zigzag_amplitude_m * math.sin(
                2 * math.pi * index / noise.zigzag_period_points
            )
            east += perp_e * wave
            north += perp_n * wave
        if noise.jumps_enabled and rng.random() < noise.jump_probability:
            bearing = rng.uniform(0, 2 * math.pi)
            dist = rng.expovariate(1.0 / max(noise.jump_distance_m, 1e-9))
            east += math.cos(bearing) * dist
            north += math.sin(bearing) * dist
        if noise.biased_drift_enabled:
            drift = noise.biased_drift_m_per_point * index
            east += math.sin(drift_bearing) * drift
            north += math.cos(drift_bearing) * drift
        if noise.lateral_drift_enabled:
            lateral = noise.lateral_drift_total_m * progress
            east += perp_e * lateral
            north += perp_n * lateral

        jitter = (
            rng.gauss(0.0, noise.timestamp_jitter_s)
            if noise.timestamp_jitter_enabled
            else 0.0
        )
        timestamp = trip.started_at + timedelta(seconds=t + jitter)

        lon2, lat2 = _offset(lon, lat, east, north)
        points.append(GpsPoint(lon=lon2, lat=lat2, timestamp=timestamp))
        t += sampling

    trip.points = points
    return points


def trip_sampling_rate(trip: SimTrip, config: ScenarioConfig) -> float:
    for spec in config.personas:
        if spec.name == trip.persona_name:
            return spec.sampling_rate_s
    return 2.0
