"""Generate the reconstruction minimum-requirements experiment scenarios.

Writes scenarios/exp_*.yaml from the shared matrix in simlab.experiments,
applied to a clean single-line base (150 blanco_galindo, modest default noise).
The same matrix powers the web "Generate experiments" button (which derives the
base from the selected scenario instead). See experiments/EXPERIMENTS.md.

Run:  uv run python experiments/generate_scenarios.py
"""

from __future__ import annotations

from pathlib import Path

from simlab.experiments import experiment_variants
from simlab.scenario import ScenarioConfig

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = ROOT / "scenarios"

# Clean single-line base: only its route + (default) noise are inherited.
BASE = {
    "name": "exp",
    "routes": [{
        "name": "main",
        "path": "transit-lab/seed/routes/150_blanco_galindo_cuatro_esquinas.geojson",
        "role": "main",
    }],
    "seed": 7,
    "personas": [{"name": "riders", "count": 8,
                  "noise_multiplier": 1.0, "sampling_rate_s": 2.0}],
}


def main() -> None:
    SCENARIOS.mkdir(exist_ok=True)
    written = []
    for data in experiment_variants(BASE, "exp"):
        ScenarioConfig.model_validate(data).to_yaml(SCENARIOS / f"{data['name']}.yaml")
        written.append(data["name"])
    print(f"wrote {len(written)} scenarios:")
    for name in written:
        print(" ", name)


if __name__ == "__main__":
    main()
