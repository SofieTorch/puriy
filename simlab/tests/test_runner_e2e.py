"""Runner end-to-end: scenario → all artifacts on disk, metrics in
bounds, full loop reaches CONFIRMED. Requires Valhalla on :8002."""

import json
from pathlib import Path

import httpx
import pytest

from simlab.runner import run_scenario
from simlab.scenario import ScenarioConfig

SCENARIOS = Path(__file__).resolve().parents[1] / "scenarios"


def _valhalla_up() -> bool:
    try:
        return httpx.get("http://localhost:8002/status", timeout=2.0).status_code == 200
    except httpx.HTTPError:
        return False


pytestmark = [
    pytest.mark.valhalla,
    pytest.mark.skipif(not _valhalla_up(), reason="Valhalla not running on :8002"),
]

EXPECTED_ARTIFACTS = [
    "manifest.json", "scenario.yaml",
    "00_ground_truth.geojson", "01_raw_traces.geojson",
    "02_matched_traces.geojson", "03_ramales.geojson",
    "04_consensus.geojson", "05_votes.geojson",
    "06_resolution.json", "07_fares.geojson",
    "metrics.json", "metrics.csv",
]


def test_clean_baseline_full_loop(tmp_path):
    config = ScenarioConfig.from_yaml(SCENARIOS / "150_clean_baseline.yaml")
    run_dir = run_scenario(config, runs_dir=tmp_path, run_id="test-clean")

    for name in EXPECTED_ARTIFACTS:
        assert (run_dir / name).exists(), f"missing artifact {name}"

    manifest = json.loads((run_dir / "manifest.json").read_text())
    assert all(s["status"] == "completed" for s in manifest["stages"]), manifest["stages"]

    metrics = json.loads((run_dir / "metrics.json").read_text())
    routes = metrics["routes"]
    assert routes, "no routes evaluated"
    assert metrics["summary"]["completeness"] is not None
    best = min(routes, key=lambda m: m["frechet_overlap_m"])
    assert best["frechet_overlap_m"] < 30.0, best
    assert best["edge_precision"] > 0.9, best
    assert best["max_junction_gap_m"] <= 15.0, best

    # The crowdsourced loop closes: votes confirmed at least one route.
    resolution = json.loads((run_dir / "06_resolution.json").read_text())
    assert "CONFIRMED" in resolution["routes"].values()
    assert resolution["edges_confirmed"] > 0
