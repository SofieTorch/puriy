# simlab

Simulation lab for the route-reconstruction flow. Replaces
`transit-lab/` (left untouched): instead of marimo notebooks, a
deterministic scenario runner plus a FastAPI + MapLibre web UI.

A *scenario* (YAML in `scenarios/`) describes a line, personas with
trip habits, GPS noise, a bus speed model, votes/fares parameters and
optional detours. A *run* executes the full flow and writes one
artifact per stage to `runs/<run_id>/`:

```
00_ground_truth.geojson    01_raw_traces.geojson    02_matched_traces.geojson
03_ramales.geojson         04_consensus.geojson     05_votes.geojson
06_resolution.json         07_fares.geojson         metrics.json / metrics.csv
manifest.json              scenario.yaml
```

Same scenario + same seed → same artifacts (thesis-grade
reproducibility).

## What the simulation models

- **Speed**: per-trip cruise speed (~8 m/s ± jitter), Poisson-spaced
  demand stops with dwell, intersection pauses.
- **GPS**: eight independently-switchable noise layers (gaussian,
  cross-track, zigzag, jumps, missing points, biased drift, lateral
  drift, timestamp jitter) with calm defaults; per-persona noise
  multiplier (cheap phones). The builder shows a **live preview** of
  sample traces as you adjust any control.
- **Personas & calendar**: devices with trips/week over a simulated
  21-day calendar and partial trips (board/alight mid-route). Trips
  always travel forward along their base route — a line's return leg
  takes different streets in practice, so it's modelled as its own
  base route with its own rider groups.
- **Votes** (mirrors the production rules): a device is eligible only
  with ≥3 cleaned trips in the last 14 days, and votes only on edges
  within 50 m of its own trips. Edge → route resolution replicates the
  pipeline thresholds (≥3 votes & 60% per edge; 80% of edges per route).
- **Fares**: boarding/alighting points + amounts with a few misreports.
- **Detours**: a stretch of route shifts sideways for a date range and
  a fraction of trips.

## Run it

```bash
# prerequisite: Valhalla on :8002 (cd infra/local && docker compose up -d)

# headless (batch experiments / thesis tables)
uv run python -m simlab.runner scenarios/150_noisy_partial.yaml

# web UI
uv run uvicorn simlab.web.app:app --port 8050
# open http://localhost:8050 — pick a scenario, run it, toggle stage
# layers, read metrics, export PNG/CSV
```

## Scenario builder (web UI)

“＋ New” / “✎ Edit” open the builder, with live preview on the map:

- **Base routes** (one or more): pick a seed geojson, upload your own
  (saved to `simlab/routes/`), or **draw one directly on the map**
  (✏ button — click to add vertices, Backspace undo, Enter/✔ finish,
  Esc cancel; the drawing is saved as a named geojson). Each route has
  a **role**: `main`, `ramal` (permanent variant, reconstructed as its
  own ramal), or `detour` (temporarily replaces another route during
  [from_day, to_day) for a fraction of trips).
- **Rider groups**: each group is assigned to one base route and gets
  count, trips/week, sampling rate, GPS-noise multiplier, vote
  propensity, a **travel window** (the stretch of *its* route it
  rides — highlighted in the group's color; trips and votes stay
  inside it), and its own **fare areas** along that route (translucent
  bands; a trip pays the most expensive area it crosses, or the global
  base fare).
- GPS noise, bus speed/stops, voting rules, seed/days.

Saving validates the config (pydantic) and writes
`scenarios/<name>.yaml`, immediately runnable from the picker or CLI.
Metrics evaluate each reconstructed route against its best-matching
ground variant, so ramal scenarios are judged per variant.

The consensus layer colors edges by confidence (red→green) and dashes
inferred (gap-bridged) edges; the votes layer colors by tally status.

## DB adapters (optional)

`simlab.adapters.db` can persist simulated trips as
`TripSession`+points (RAW — ready for the real pipeline), votes as
`EdgeVote` rows, and fare reports — everything tagged
`device_model="simulator"` / `sim:` ids so it can be wiped.

## Tests

```bash
uv run pytest          # sim core + vote eligibility boundaries
uv run pytest -m valhalla   # runner e2e (needs Valhalla)
```
