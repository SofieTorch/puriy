"""Simulate noisy GPS tracks along a route."""

import math
import random
from datetime import datetime, timedelta

from shapely.geometry import Point as _ShapelyPoint

from .geo_math import heading_and_perp, interpolate_route, offset_lon_lat
from .telemetry import tracer


def generate_tracks(
    route: list[list[float]],
    config: dict,
    seed: int | None = 42,
    noise_zones: list[dict] | None = None,
) -> list[dict]:
    """Generate simulated GPS tracks along *route* (list of [lon, lat]).

    Parameters
    ----------
    route : list of [lon, lat]
        The base route to simulate tracks along.
    config : dict
        Configuration dict with "sim_params" and "noise" keys,
        matching the JSON format saved by the notebook.
    seed : int or None
        Random seed for reproducibility.  ``None`` or ``-1`` means random.
    noise_zones : list of dict, optional
        Each entry must have a ``"polygon"`` key (a Shapely geometry) and a
        ``"multiplier"`` key (float >= 1).  When a point falls inside a zone
        the effective isotropic sigma is multiplied by the zone's value.
        Overlapping zones use the maximum multiplier.

    Returns
    -------
    list of dict
        Each dict has: track_id, point_index, timestamp, longitude, latitude,
        and ``accuracy`` (1-sigma horizontal accuracy in metres, matching the
        convention used by Android/iOS) when isotropic noise is active.
    """
    if len(route) < 2:
        raise ValueError("Route needs at least 2 points")

    span = tracer.start_span(
        "generate_tracks",
        attributes={
            "route.points": len(route),
            "config.num_tracks": int(config.get("sim_params", {}).get("Number of tracks", 5)),
            "seed": seed if seed is not None else -1,
        },
    )

    sp = config.get("sim_params", {})
    noise = config.get("noise", {})

    num_tracks = int(sp.get("Number of tracks", 5))
    sampling_rate_s = float(sp.get("Sampling rate (s)", 2.0))
    base_speed_mps = float(sp.get("Base speed (m/s)", 8.0))
    speed_jitter_pct = float(sp.get("Speed jitter (%)", 12.0))
    target_points = int(sp.get("Target pts/track (0=auto)", 0))

    if seed is not None and seed >= 0:
        effective_seed = seed
    else:
        effective_seed = None

    # Noise params helpers
    def _on(key: str, default: bool = True) -> bool:
        return noise.get(key, {}).get("Enabled", default)

    def _p(key: str, param: str, default: float = 0.0) -> float:
        return float(noise.get(key, {}).get(param, default))

    gaussian_m = _p("gaussian", "Sigma (m)", 3.0)
    perpendicular_m = _p("perpendicular", "Sigma (m)", 2.0)
    zigzag_amp_m = _p("zigzag", "Amplitude (m)", 1.5)
    zigzag_period = max(2, int(_p("zigzag", "Period (points)", 8)))
    jump_prob = _p("jumps", "Probability", 0.02)
    jump_dist_mean = _p("jumps", "Distance (m)", 40.0)
    missing_prob = _p("missing", "Probability", 0.03)
    drift_step = _p("biased_drift", "Drift (m/pt)", 0.05)
    drift_bearing = math.radians(_p("biased_drift", "Bearing (deg)", 70.0))
    lat_drift_total = _p("lateral_drift", "Total (m)", 3.0)
    ts_jitter = _p("timestamp_jitter", "Sigma (s)", 0.15)

    # OU drift parameters — disabled by default so old configs are unaffected
    ou_enabled = _on("ou_drift", default=False)
    ou_mean = _p("ou_drift", "Mean sigma (m)", 5.0)
    ou_theta = _p("ou_drift", "Reversion rate", 0.05)   # mean-reversion speed, 0-1
    ou_vol = _p("ou_drift", "Volatility", 2.0)           # OU noise volatility
    ou_max = _p("ou_drift", "Max sigma (m)", 50.0)

    records: list[dict] = []
    start_time = datetime.utcnow().replace(microsecond=0)

    for track_idx in range(num_tracks):
        track_seed = (
            None if effective_seed is None else effective_seed + track_idx * 1009
        )
        rng = random.Random(track_seed)

        speed_factor = max(0.1, 1 + rng.gauss(0, speed_jitter_pct / 100.0))
        step_m = max(0.5, base_speed_mps * speed_factor * sampling_rate_s)
        base_points = interpolate_route(route, step_m)

        if target_points > 1 and len(base_points) > target_points:
            idxs = [
                round(i * (len(base_points) - 1) / (target_points - 1))
                for i in range(target_points)
            ]
            base_points = [base_points[i] for i in idxs]

        drift_acc_m = 0.0
        # OU state — initialise near the mean with a small random offset
        ou_sigma = (
            max(1.0, min(ou_max, rng.gauss(ou_mean, ou_mean * 0.2)))
            if ou_enabled else 0.0
        )

        # noisy_points stores (lon, lat, elapsed_s, effective_sigma)
        noisy_points: list[tuple[float, float, float, float]] = []
        elapsed_s = 0.0

        for i, (lon, lat) in enumerate(base_points):
            _, perp = heading_and_perp(base_points, i)
            east_m = 0.0
            north_m = 0.0

            # ------------------------------------------------------------------
            # Compute effective isotropic sigma for this point.
            # OU drift (when enabled) drives a slowly-varying sigma that
            # replaces the fixed gaussian sigma.  Zone multipliers are then
            # applied on top of whichever base is active.
            # ------------------------------------------------------------------
            if ou_enabled:
                ou_sigma += ou_theta * (ou_mean - ou_sigma) + ou_vol * rng.gauss(0, 1)
                ou_sigma = max(1.0, min(ou_max, ou_sigma))
                effective_sigma = ou_sigma
            elif _on("gaussian") and gaussian_m > 0:
                effective_sigma = gaussian_m
            else:
                effective_sigma = 0.0

            # Zone multiplier — evaluated against the original route point
            # (before any noise is applied), using the maximum multiplier when
            # a point falls inside multiple overlapping zones.
            if noise_zones and effective_sigma > 0:
                _pt = _ShapelyPoint(lon, lat)
                _zone_mult = 1.0
                for _zone in noise_zones:
                    if _zone["polygon"].contains(_pt):
                        _zone_mult = max(_zone_mult, float(_zone.get("multiplier", 1.0)))
                effective_sigma *= _zone_mult

            # Apply isotropic Gaussian noise with the final effective sigma
            if effective_sigma > 0:
                east_m += rng.gauss(0, effective_sigma)
                north_m += rng.gauss(0, effective_sigma)

            # ------------------------------------------------------------------
            # Remaining noise types (independent of OU / zones)
            # ------------------------------------------------------------------
            if _on("perpendicular") and perpendicular_m > 0:
                perp_offset = rng.gauss(0, perpendicular_m)
                east_m += perp[0] * perp_offset
                north_m += perp[1] * perp_offset

            if _on("zigzag") and zigzag_amp_m > 0:
                zigzag_offset = zigzag_amp_m * math.sin(
                    (2 * math.pi * i) / zigzag_period
                )
                east_m += perp[0] * zigzag_offset
                north_m += perp[1] * zigzag_offset

            if (
                _on("jumps")
                and jump_prob > 0
                and rng.random() < jump_prob
                and jump_dist_mean > 0
            ):
                jump_angle = rng.uniform(0, 2 * math.pi)
                jump_dist = max(
                    0.0, rng.gauss(jump_dist_mean, jump_dist_mean * 0.35)
                )
                east_m += math.cos(jump_angle) * jump_dist
                north_m += math.sin(jump_angle) * jump_dist

            if _on("biased_drift"):
                drift_acc_m += drift_step
                east_m += math.sin(drift_bearing) * drift_acc_m
                north_m += math.cos(drift_bearing) * drift_acc_m

            if (
                _on("lateral_drift")
                and len(base_points) > 1
                and lat_drift_total != 0
            ):
                lateral_progress = i / (len(base_points) - 1)
                lateral_offset = lateral_progress * lat_drift_total
                east_m += perp[0] * lateral_offset
                north_m += perp[1] * lateral_offset

            nlon, nlat = offset_lon_lat(lon, lat, east_m, north_m)

            if i > 0:
                jitter = (
                    rng.gauss(0, ts_jitter) if _on("timestamp_jitter") else 0.0
                )
                elapsed_s += max(0.2, sampling_rate_s + jitter)

            noisy_points.append((nlon, nlat, elapsed_s, effective_sigma))

        if _on("missing"):
            kept_points = []
            for i, point in enumerate(noisy_points):
                if (
                    i in (0, len(noisy_points) - 1)
                    or rng.random() >= missing_prob
                ):
                    kept_points.append(point)
            if len(kept_points) < 2 and len(noisy_points) >= 2:
                kept_points = [noisy_points[0], noisy_points[-1]]
        else:
            kept_points = noisy_points

        track_start = start_time + timedelta(minutes=track_idx)
        for point_idx, (plon, plat, t_s, eff_sig) in enumerate(kept_points):
            timestamp = track_start + timedelta(seconds=t_s)
            record: dict = {
                "track_id": track_idx + 1,
                "point_index": point_idx + 1,
                "timestamp": timestamp.isoformat(),
                "longitude": plon,
                "latitude": plat,
            }
            if eff_sig > 0:
                record["accuracy"] = round(eff_sig, 1)
            records.append(record)

    span.set_attribute("points.total", len(records))
    span.end()

    return records
