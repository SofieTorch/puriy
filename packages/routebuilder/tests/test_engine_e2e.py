"""End-to-end: simulated noisy traces on real Cochabamba routes →
map matching → consensus → metrics vs ground truth.

Requires a running Valhalla (infra/local, port 8002):
    cd packages/routebuilder && uv run pytest -m valhalla
"""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from geodata.geo_math import haversine_m
from geodata.simulate import generate_tracks

from routebuilder.cleaning import clean_trace
from routebuilder.config import ReconstructionConfig
from routebuilder.engine import reconstruct_from_matched, reconstruct_from_raw
from routebuilder.evaluation.harness import (
    clip_to_achievable,
    evaluate_route,
    load_ground_truth,
    matched_ground_truth,
)
from routebuilder.types import RawPoint
from routebuilder.valhalla import make_bridge_fn

SEED_ROUTES = Path(__file__).resolve().parents[3] / "transit-lab" / "seed" / "routes"

NOISY_CONFIG = {
    "sim_params": {
        "Number of tracks": 6,
        "Sampling rate (s)": 2.0,
        "Base speed (m/s)": 8.0,
        "Speed jitter (%)": 12.0,
        "Mean trace proportion (0-1)": 0.85,
        "Stddev trace proportion": 0.1,
    },
    "noise": {
        "gaussian": {"Enabled": True, "Sigma (m)": 4.0},
        "perpendicular": {"Enabled": True, "Sigma (m)": 3.0},
        "zigzag": {"Enabled": False},
        "jumps": {"Enabled": True, "Probability": 0.02, "Distance (m)": 40.0},
        "missing": {"Enabled": True, "Probability": 0.03},
        "biased_drift": {"Enabled": False},
        "lateral_drift": {"Enabled": False},
        "timestamp_jitter": {"Enabled": True, "Sigma (s)": 0.15},
    },
}


def _valhalla_up() -> bool:
    try:
        return httpx.get("http://localhost:8002/status", timeout=2.0).status_code == 200
    except httpx.HTTPError:
        return False


pytestmark = [
    pytest.mark.valhalla,
    pytest.mark.skipif(not _valhalla_up(), reason="Valhalla not running on :8002"),
]


def _records_to_raw_traces(records: list[dict], prefix: str = "") -> dict[str, list[RawPoint]]:
    # The geodata trace-match cache keys on trace_id, so ids must be
    # globally unique across routes/scenarios.
    base = datetime(2026, 6, 1, 8, 0, tzinfo=UTC)
    traces: dict[str, list[RawPoint]] = {}
    for rec in records:
        ts = rec.get("timestamp")
        if isinstance(ts, (int, float)):
            timestamp = base + timedelta(seconds=float(ts))
        elif isinstance(ts, datetime):
            timestamp = ts
        else:
            timestamp = None
        traces.setdefault(f"{prefix}{rec['track_id']}", []).append(
            RawPoint(lon=rec["longitude"], lat=rec["latitude"], timestamp=timestamp)
        )
    return traces


@pytest.mark.parametrize("route_file", [
    "150_blanco_galindo_cuatro_esquinas.geojson",
    "120_from_univalle_to_umss.geojson",
])
def test_noisy_partial_traces_reconstruct_cleanly(route_file):
    ground_truth = load_ground_truth(SEED_ROUTES / route_file)
    records = generate_tracks(ground_truth, NOISY_CONFIG, seed=7)
    raw_traces = _records_to_raw_traces(records, prefix=f"noisy:{route_file}:")
    assert len(raw_traces) == 6

    config = ReconstructionConfig()
    matched = [
        t for t in (
            clean_trace(tid, pts, config.cleaning) for tid, pts in raw_traces.items()
        ) if t is not None
    ]
    output = reconstruct_from_matched(
        matched,
        config=config,
        bridge_fn=make_bridge_fn(config.consensus),
    )

    assert output.routes, f"no routes reconstructed: {output.diagnostics}"
    # Largest route should be the main consensus.
    main = max(output.routes, key=lambda r: len(r.edges))

    truth_shape, truth_edges = matched_ground_truth(ground_truth, trace_id=f"gt-dense:{route_file}")
    # Partial traces leave the route's extremes unobserved; evaluate
    # against the stretch at least 2 traces actually covered.
    achievable = clip_to_achievable(truth_shape, matched)
    result = evaluate_route(main, achievable, truth_edges=truth_edges)

    assert result.max_junction_gap_m <= config.consensus.connect_tolerance_m
    # Shape fidelity over the common extent: bounded by legitimate
    # evidence-vs-drawn-groundtruth disagreements (~80m parallel-block
    # differences), not by reconstruction artifacts. Endpoint
    # truncation (parallel-carriageway ambiguity near termini) is
    # reported separately, bounded relative to route length.
    truth_len_m = sum(
        haversine_m(a[0], a[1], b[0], b[1])
        for a, b in zip(achievable, achievable[1:])
    )
    assert result.frechet_overlap_m < 150.0, result
    assert result.start_truncation_m < 0.10 * truth_len_m, result
    assert result.end_truncation_m < 0.10 * truth_len_m, result
    assert result.coverage > 0.85, result
    assert result.edge_precision is not None and result.edge_precision > 0.9, result


def test_clean_traces_high_fidelity():
    route_file = "150_blanco_galindo_cuatro_esquinas.geojson"
    ground_truth = load_ground_truth(SEED_ROUTES / route_file)
    clean_config = {
        "sim_params": {**NOISY_CONFIG["sim_params"], "Mean trace proportion (0-1)": 1.0,
                       "Stddev trace proportion": 0.0},
        "noise": {key: {"Enabled": False} for key in NOISY_CONFIG["noise"]},
    }
    records = generate_tracks(ground_truth, clean_config, seed=3)
    raw_traces = _records_to_raw_traces(records, prefix=f"clean:{route_file}:")

    config = ReconstructionConfig()
    output = reconstruct_from_raw(
        raw_traces, config=config, bridge_fn=make_bridge_fn(config.consensus)
    )
    assert output.routes
    main = max(output.routes, key=lambda r: len(r.edges))
    truth_shape, truth_edges = matched_ground_truth(ground_truth, trace_id=f"gt-dense:{route_file}")
    result = evaluate_route(main, truth_shape, truth_edges=truth_edges)

    assert result.frechet_m < 30.0, result  # clean + full traces: strict bound holds
    assert result.coverage > 0.95, result
    assert result.edge_precision is not None and result.edge_precision > 0.9, result
