"""Estimate a simulator config from a real recorded trace.

This is the inverse of :func:`geodata.simulate.generate_tracks`: given a real
GPS trace it recovers a ``config`` dict (same shape the simulator consumes) via
method-of-moments, so that synthetic tracks generated from it are
*statistically* similar to the real one.

The clean reference centerline is obtained by map-matching the trace with
Valhalla (``trace_attributes``) rather than from any stored "clean" geometry.

Identifiability caveats (these knobs are deliberately collapsed):
- ``perpendicular`` noise is folded into ``gaussian`` — both produce the same
  cross-track signal and cannot be separated from a single trace.
- ``biased_drift`` is folded into ``lateral_drift`` — both appear as a linear
  cross-track trend along the trace.
Both are therefore returned disabled; the recovered config is *equivalent*, not
the unique original.
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

import numpy as np

from .geo_math import haversine_m, heading_and_perp
from .match import trace_match
from .telemetry import tracer

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _normalize_points(points: list[dict]) -> list[dict]:
    """Coerce trace records into ``{lon, lat, ts}`` dicts (ts is a datetime or None)."""
    out: list[dict] = []
    for p in points:
        lon = p.get("longitude", p.get("lon"))
        lat = p.get("latitude", p.get("lat"))
        if lon is None or lat is None:
            raise ValueError("each point needs longitude/latitude (or lon/lat)")
        ts = p.get("timestamp", p.get("time"))
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts)
        elif isinstance(ts, (int, float)):
            ts = datetime.fromtimestamp(float(ts))
        out.append({"lon": float(lon), "lat": float(lat), "ts": ts})
    return out


def _signed_cross_track(centerline: list[list[float]], raw: list[list[float]]) -> np.ndarray:
    """Signed perpendicular offset (m) of each raw point from its snapped point."""
    cross = np.empty(len(centerline))
    for i in range(len(centerline)):
        lon_s, lat_s = centerline[i]
        lon_r, lat_r = raw[i]
        cos_lat = math.cos(math.radians(lat_s))
        east = (lon_r - lon_s) * 111_320.0 * cos_lat
        north = (lat_r - lat_s) * 111_320.0
        _, perp = heading_and_perp(centerline, i)
        cross[i] = east * perp[0] + north * perp[1]
    return cross


def fit_config_from_trace(
    points: list[dict],
    *,
    costing: str = "bus",
    search_radius: int = 60,
    gps_accuracy: int = 20,
    trace_id: str | None = None,
    num_tracks: int = 20,
    zigzag_prominence: float = 6.0,
    jump_sigma_threshold: float = 4.0,
) -> dict:
    """Recover a simulator config from a real GPS trace.

    Parameters
    ----------
    points : list of dict
        Real trace points. Each needs ``longitude``/``latitude`` (or ``lon``/
        ``lat``) and ideally a ``timestamp`` (ISO string, datetime, or epoch).
    costing, search_radius, gps_accuracy : Valhalla map-matching options.
    trace_id : optional cache key passed through to :func:`trace_match`.
    num_tracks : value written to ``"Number of tracks"`` in the output config.
    zigzag_prominence : how many times the spectral noise floor (median bin) the
        dominant frequency must reach for zigzag to be considered present.
    jump_sigma_threshold : cross-track residual beyond this many sigmas counts
        as a GPS jump rather than ordinary gaussian noise.

    Returns
    -------
    dict
        A config dict in the exact shape :func:`generate_tracks` consumes.
    """
    pts = _normalize_points(points)
    if len(pts) < 4:
        raise ValueError("need at least 4 points to estimate a config")

    with tracer.start_as_current_span(
        "fit_config_from_trace",
        attributes={"points.raw": len(pts)},
    ) as span:
        # 1. Clean centerline via Valhalla map-matching.
        match_input = [{"lat": p["lat"], "lon": p["lon"]} for p in pts]
        for entry, p in zip(match_input, pts):
            if p["ts"] is not None:
                entry["time"] = int(p["ts"].timestamp())
        matched = trace_match(
            match_input,
            trace_id=trace_id,
            costing=costing,
            search_radius=search_radius,
            gps_accuracy=gps_accuracy,
        )

        centerline: list[list[float]] = []
        raw_aligned: list[list[float]] = []
        for i, mp in enumerate(matched.matched_points):
            if mp.get("type") != "matched" or "lon" not in mp or "lat" not in mp:
                continue
            centerline.append([float(mp["lon"]), float(mp["lat"])])
            raw_aligned.append([pts[i]["lon"], pts[i]["lat"]])
        if len(centerline) < 4:
            raise ValueError(
                f"only {len(centerline)} points map-matched; cannot fit a config"
            )

        # 2. Timing: sampling rate, timestamp jitter, missing-point probability.
        epochs = [p["ts"].timestamp() for p in pts if p["ts"] is not None]
        sampling_rate = 2.0
        ts_jitter = 0.15
        missing_prob = 0.0
        if len(epochs) == len(pts) and len(epochs) >= 3:
            dts = np.diff(np.array(epochs))
            dts = dts[dts > 0]
            if dts.size:
                sampling_rate = float(np.median(dts))
                regular = dts[dts < 1.5 * sampling_rate]
                if regular.size >= 2:
                    ts_jitter = float(np.std(regular))
                # gaps wider than ~1.5 intervals imply dropped points
                missing_counts = np.maximum(0, np.round(dts / sampling_rate) - 1)
                kept = float(dts.size)
                dropped = float(missing_counts.sum())
                if kept + dropped > 0:
                    missing_prob = dropped / (kept + dropped)

        # 3. Speed: snapped path length / elapsed time + per-step variability.
        path_len = sum(
            haversine_m(
                centerline[i][0], centerline[i][1],
                centerline[i + 1][0], centerline[i + 1][1],
            )
            for i in range(len(centerline) - 1)
        )
        base_speed = 8.0
        speed_jitter_pct = 12.0
        if len(epochs) == len(pts) and len(epochs) >= 2:
            elapsed = epochs[-1] - epochs[0]
            if elapsed > 0:
                base_speed = path_len / elapsed
            step_speeds = []
            for i in range(len(centerline) - 1):
                step_speeds.append(
                    haversine_m(
                        centerline[i][0], centerline[i][1],
                        centerline[i + 1][0], centerline[i + 1][1],
                    )
                )
            step_speeds = np.array(step_speeds) / max(sampling_rate, 0.2)
            if step_speeds.size and step_speeds.mean() > 0:
                speed_jitter_pct = float(
                    np.std(step_speeds) / step_speeds.mean() * 100.0
                )

        # 4. Cross-track offset decomposition.
        cross = _signed_cross_track(centerline, raw_aligned)
        n = cross.size
        idx = np.arange(n)

        # 4a. Linear trend -> lateral drift (folds in biased drift).
        slope, intercept = np.polyfit(idx, cross, 1)
        detrended = cross - (slope * idx + intercept)
        lateral_total = float(slope * (n - 1))

        # 4b. Dominant periodic component -> zigzag.
        sig = detrended - detrended.mean()
        zigzag_enabled = False
        zigzag_amp = 1.5
        zigzag_period = 8
        residual = detrended
        if n >= 8 and np.any(sig):
            fft = np.fft.rfft(sig)
            spectrum = np.abs(fft)
            freqs = np.fft.rfftfreq(n, d=1.0)
            ac_power = spectrum[1:]
            # A genuine oscillation makes one bin tower over the noise floor;
            # compare the peak to the median bin (prominence), which survives
            # broadband gaussian/jump energy far better than a fraction-of-total test.
            noise_floor = max(float(np.median(ac_power)), 1e-9)
            k = int(np.argmax(ac_power)) + 1
            period = 1.0 / freqs[k] if freqs[k] > 0 else 0.0
            amp = 2.0 * spectrum[k] / n
            if (
                freqs[k] > 0
                and spectrum[k] >= zigzag_prominence * noise_floor
                and 2.0 <= period <= n / 2.0
                and amp > 0.5
            ):
                phase = math.atan2(fft[k].imag, fft[k].real)
                fitted = amp * np.cos(2 * math.pi * idx / period + phase)
                residual = detrended - fitted
                zigzag_enabled = True
                zigzag_amp = float(amp)
                zigzag_period = int(round(period))

        # 4c. Jumps: residuals far in the tail are jumps, not gaussian noise.
        robust_sigma = float(np.median(np.abs(residual - np.median(residual)))) * 1.4826
        robust_sigma = max(robust_sigma, 1e-6)
        jump_mask = np.abs(residual - np.median(residual)) > jump_sigma_threshold * robust_sigma
        jump_prob = float(jump_mask.sum()) / n
        jump_dist = float(np.mean(np.abs(residual[jump_mask]))) if jump_mask.any() else 40.0

        # 4d. Remaining spread -> gaussian (folds in perpendicular noise).
        gaussian_sigma = float(np.std(residual[~jump_mask])) if (~jump_mask).any() else float(np.std(residual))

        span.set_attributes({
            "fit.matched_points": n,
            "fit.sampling_rate_s": sampling_rate,
            "fit.base_speed_mps": base_speed,
            "fit.gaussian_sigma_m": gaussian_sigma,
            "fit.lateral_drift_m": lateral_total,
            "fit.zigzag": zigzag_enabled,
            "fit.jump_prob": jump_prob,
            "fit.missing_prob": missing_prob,
        })

    return {
        "sim_params": {
            "Number of tracks": int(num_tracks),
            "Sampling rate (s)": round(max(0.2, sampling_rate), 3),
            "Base speed (m/s)": round(max(0.5, base_speed), 3),
            "Speed jitter (%)": round(max(0.0, min(50.0, speed_jitter_pct)), 2),
            "Target pts/track (0=auto)": 0,
            "Mean trace proportion (0-1)": 1.0,
            "Stddev trace proportion": 0.0,
        },
        "noise": {
            "gaussian": {
                "Enabled": gaussian_sigma > 0.1,
                "Sigma (m)": round(max(0.0, gaussian_sigma), 3),
            },
            "perpendicular": {"Enabled": False, "Sigma (m)": 0.0},
            "zigzag": {
                "Enabled": zigzag_enabled,
                "Amplitude (m)": round(max(0.0, zigzag_amp), 3),
                "Period (points)": max(2, zigzag_period),
            },
            "jumps": {
                "Enabled": jump_prob > 0.0,
                "Probability": round(jump_prob, 4),
                "Distance (m)": round(max(0.0, jump_dist), 2),
            },
            "missing": {
                "Enabled": missing_prob > 0.0,
                "Probability": round(min(0.3, missing_prob), 4),
            },
            "biased_drift": {"Enabled": False, "Drift (m/pt)": 0.0, "Bearing (deg)": 0.0},
            "lateral_drift": {
                "Enabled": abs(lateral_total) > 0.5,
                "Total (m)": round(lateral_total, 3),
            },
            "timestamp_jitter": {
                "Enabled": ts_jitter > 0.01,
                "Sigma (s)": round(max(0.0, ts_jitter), 3),
            },
        },
    }


def fit_config_from_session(
    db: Session,
    session_id: UUID,
    *,
    costing: str = "bus",
    search_radius: int = 60,
    gps_accuracy: int = 20,
    num_tracks: int = 20,
) -> dict:
    """Load a TripSession's raw points and fit a simulator config from them."""
    from sqlalchemy import select

    from database.models import TripSessionPoint

    rows = (
        db.execute(
            select(TripSessionPoint)
            .where(TripSessionPoint.session_id == session_id)
            .order_by(TripSessionPoint.timestamp)
        )
        .scalars()
        .all()
    )
    if len(rows) < 4:
        raise ValueError(f"TripSession {session_id} has fewer than 4 points")

    points = [
        {"longitude": r.longitude, "latitude": r.latitude, "timestamp": r.timestamp}
        for r in rows
    ]
    return fit_config_from_trace(
        points,
        costing=costing,
        search_radius=search_radius,
        gps_accuracy=gps_accuracy,
        trace_id=str(session_id),
        num_tracks=num_tracks,
    )
