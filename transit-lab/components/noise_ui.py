"""Build the noise configuration UI for the trajectory generator."""

import marimo as mo

_NOISE_MODELS = [
    ("gaussian", "Gaussian GPS noise",
     "Adds random isotropic noise to each point, simulating typical GPS inaccuracy.",
     [("Sigma (m)", 3.0, {"start": 0, "step": 0.5})]),
    ("perpendicular", "Perpendicular road noise",
     "Adds noise perpendicular to the road direction, simulating lane-width uncertainty.",
     [("Sigma (m)", 2.0, {"start": 0, "step": 0.5})]),
    ("zigzag", "Zig-zag noise",
     "Adds a periodic sine-wave offset perpendicular to the path, simulating systematic oscillation.",
     [("Amplitude (m)", 1.5, {"start": 0, "step": 0.5}),
      ("Period (points)", 8, {"start": 2, "step": 1})]),
    ("jumps", "Random jumps",
     "Occasionally teleports a point to a random nearby location, simulating GPS multipath errors.",
     [("Probability", 0.02, {"start": 0, "stop": 1, "step": 0.01}),
      ("Distance (m)", 40.0, {"start": 0, "step": 5})]),
    ("missing", "Missing points",
     "Randomly drops points from the track, simulating signal loss or sampling gaps.",
     [("Probability", 0.03, {"start": 0, "stop": 0.95, "step": 0.01})]),
    ("biased_drift", "Biased drift",
     "Accumulates a constant offset in a fixed direction over time, simulating receiver bias drift.",
     [("Drift (m/pt)", 0.05, {"start": 0, "step": 0.01}),
      ("Bearing (deg)", 70.0, {"start": 0, "stop": 360, "step": 5})]),
    ("lateral_drift", "Lateral drift",
     "Gradually shifts the track sideways along its length, simulating systematic lateral error.",
     [("Total (m)", 3.0, {"step": 0.5})]),
    ("timestamp_jitter", "Timestamp jitter",
     "Adds random variation to the time interval between points, simulating irregular sampling.",
     [("Sigma (s)", 0.15, {"start": 0, "step": 0.05})]),
]

_OU_DRIFT = (
    "ou_drift", "OU accuracy drift",
    "Slowly-varying GPS accuracy via an Ornstein-Uhlenbeck process. "
    "Replaces the fixed Gaussian sigma with a signal that drifts over time, "
    "simulating changing satellite geometry or urban-canyon entry/exit. "
    "Per-point accuracy is stored in the DB and passed to Valhalla.",
    [("Mean sigma (m)", 5.0, {"start": 1.0, "step": 0.5}),
     ("Reversion rate", 0.05, {"start": 0.01, "stop": 1.0, "step": 0.01}),
     ("Volatility", 2.0, {"start": 0.1, "step": 0.5}),
     ("Max sigma (m)", 50.0, {"start": 1.0, "step": 5.0})],
)


def build_noise_config(
    loaded_config: dict | None = None,
) -> dict[str, mo.ui.dictionary]:
    """Build the full noise configuration UI, optionally pre-filled from saved config."""
    ncfg = (loaded_config or {}).get("noise", {})

    def _nval(key: str, param: str, default):
        return ncfg.get(key, {}).get(param, default)

    def _build(key, label, description, params_spec, enabled_default=True):
        params = {}
        for param_name, default_val, kwargs in params_spec:
            params[param_name] = mo.ui.number(
                value=_nval(key, param_name, default_val), **kwargs
            )
        return mo.ui.dictionary(
            {
                "Enabled": mo.ui.checkbox(value=_nval(key, "Enabled", enabled_default)),
                "Description": mo.md(f"*{description}*").batch(),
                **params,
            },
            label=label,
        )

    config = {}
    for key, label, desc, params_spec in _NOISE_MODELS:
        config[key] = _build(key, label, desc, params_spec)

    key, label, desc, params_spec = _OU_DRIFT
    config["ou_drift"] = _build(key, label, desc, params_spec, enabled_default=False)
    return config
