# Reconstruction minimum-requirements experiments

**Goal:** find the *minimum* crowdsourced-GPS conditions for a proper route
reconstruction.

**You define the positioning.** Set up a base scenario with your rider groups
placed in their zones (`travel_window`) across the ramales — that *is* the
spatial layout you're testing. The factorial keeps that whole structure (every
route/ramal, every group, every zone) and sweeps the inputs that govern each
trace.

## One factorial, not separate sweeps

The factors **interact** — the minimum number of traces depends on how much each
trace covers and where. So we don't sweep them one at a time; we generate the
full **combination** and read the response surface off the results:

| factor | values |
|---|---|
| **traces** (per group) | `1, 2, 3, 5, 8, 13, 21, 34` — absolute, geometric (dense at the low end, where the cliff is) |
| **mean trip distance** | full zone · 0.5 · 0.3 of the reference zone (written as metres) |
| **position shape** | uniform · center · edges (only crossed with the partial means) |

`std` is held proportional to the mean (variance = std²). Each cell sets the same
`traces` on every group (the controlled variable) and `voters = 0`.

So a cell is e.g. `{base}_F010_t2_m3535_center` — *2 traces/group, avg 3535 m,
center-weighted*. ≈**56 scenarios**; tune `_TRIPS` / `_MEAN_FRACS` / `_SHAPES`
in `simlab/experiments.py` to grow or shrink it.

**Coverage is an output, not a knob.** `completeness`, `ramales_found`,
`trace_distance_*` are read *per cell* — you move the inputs and measure what
reconstructs.

## Thresholds baked into the engine (what to expect)

- Each segment needs **≥ 2 traces** covering it (`min_support_abs = 2`).
- Clustering needs **≥ 3 traces** (≥ 2 when a group is ≤ 6).
- Filling a coverage gap needs **≥ 3 traces** spanning it
  (`cross_bridge_min_traces = 3`); a *true zero-trace* gap correctly stays a gap.

So expect a quality cliff when a zone drops below ~2–3 traces — which is exactly
why the trace axis is dense down low.

## Metrics (read these per cell)

From the run **Summary** (`metrics_summary.json`; columns on every `metrics.csv`
row):

- **`completeness`** — share of the rider-defined envelope reconstructed. **The
  primary signal.**
- **`coverage_envelope`** — that envelope as a fraction of the full route(s).
- **`trace_distance_median_m` / `_mean_m` / `_std_m`** — metres each matched
  trace spans (board→alight). Read *with* `completeness`: full completeness +
  short per-trace means the route was tiled from many partials, not whole traces.
- **`ramales_found` / `ramales_expected`** — variant recall.
- **`reconstructed_routes`** — raw count; > expected = fragmented.
- **`best_frechet_overlap_m`** — accuracy guardrail.

The **minimum** is the Pareto frontier of the surface: the fewest traces / shortest
mean / most-biased shape that still reconstructs cleanly. It can *move with the
position shape* — a *center*-weighted zone starves its edges and needs more
traces than a *uniform* one. That shift is a finding, not noise.

## Workflow (Experiments panel)

1. **Build your base** — rider groups in their zones across the ramales.
2. **⚗ Generate experiments** — creates the factorial `{base}_F001 … _F056`.
3. **▶ Run whole factorial** — runs them on the server (survives a refresh).
   Each appears under the `⚗ {base}` group in **Runs** with the *measured*
   `cov %` and `ram found/expected` inline.
4. **Read the surface** — find the cell where `completeness` ≈ 1 and
   `ramales_found` = `ramales_expected` with the fewest traces / shortest mean.
   That cell *is* the minimum recipe (there's no separate "D" step any more).
5. **🗑 Manage…** — bulk-delete scenarios when done.

## Per-group trace shape (base scenario)

Each rider group sets, in the builder:

- **Traces** — how many independent GPS traces it contributes.
- **Avg trip distance** + **Trip distance std** — the per-trace length
  distribution (0 = full zone).
- **Trace position** — a draggable density profile for where trips concentrate
  along the zone (uniform / center / edges / start / end presets).

The factorial overrides `traces`, the distance model and `trip_position_weights`
per cell, but keeps each group's zone.

## Voting (a separate study)

The factorial above sets `voters = 0` — it's about reconstruction. Voting is its
own axis, modelled so that **trace volume and voter volume are independent**:

- **`traces`** is the fixed reconstruction budget.
- **`voters`** are *carved from* that budget — each voter is a "regular" formed
  by aggregating `votes.eligibility_min_trips` of the group's **existing** traces
  onto one device (so it has the history to vote). This only relabels trace
  ownership, so the traces the reconstruction sees are unchanged. Clamped to
  `traces // min_trips`; a shortfall is reported per group
  (*"Couldn't form all voters. Expected: X, assigned: Y …"*).
- **`vote_position_weights`** — a second density profile (the builder's amber
  editor) selecting *which* traces become voters, so voting can concentrate in a
  zone independently of the trace distribution ("regulars cluster here").
- Eligibility is **structural** (a device with ≥ `min_trips` traces) — there's no
  time window. Every eligible voter votes; **turnout** (voters who voted / riders)
  is a *measured output*, not an input.

To study voting, set `voters` (and optionally the vote profile) per group and read
**turnout** plus route confirmation in the run results.

## Generating

- **UI** (per base): the **⚗ Generate experiments** button (above).
- **CLI**: `cd simlab && uv run python experiments/generate_scenarios.py`.

Both use `simlab.experiments.experiment_variants`. Edit the axis lists at the top
of `simlab/experiments.py` to tune the grid.
