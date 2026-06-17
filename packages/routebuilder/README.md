# routebuilder

Consensus route reconstruction from map-matched GPS traces. Replaces the
`edge_sequence_overlap_assembly_preview` strategy in `geodata` (left
untouched) with an edge-frequency support-graph algorithm that is robust
in the realistic regime: 3–6 noisy, partial traces per line.

## Why the old approach failed

The old strategy assembled overlapping edge sequences greedily. Failure
modes (all reproduced in tests here):

- **Spurious cross-streets**: a single trace's GPS jump snapped onto a
  side street survived the 34% support threshold and got merged in.
- **Blind geometry concatenation**: disconnected consecutive edges were
  appended anyway, drawing roads nobody traversed.
- **Partial traces mishandled**: global support fractions punished route
  ends covered by fewer (shorter) trips.

## How this one works

```
raw GPS traces
  → cleaning.py      Valhalla HMM matching (wraps geodata.match), point
                     thinning, quality gates
  → direction.py     split forward/reverse runs by directed-edge agreement
  → ramales.py       cluster variants (partial-aware directed Hausdorff +
                     complete linkage)
  → graph.py         directed-edge support graph, localized support
                     (per-edge coverage denominators → fair to partial
                     traces), pruning
  → consensus.py     consensus endpoints, widest (bottleneck) path,
                     Valhalla gap bridging, connected geometry assembly
  → ramales.py       divergence detection: competing branches with
                     disjoint trace support split into separate ramales
```

Output per ramal: ordered `(valhalla_edge_id, forward)` sequence +
guaranteed-connected LineString + per-edge confidence — drop-in
compatible with `Route`/`RouteEdge` and the existing vote migration.

Key invariants (unit-tested):
- consecutive edges' geometries always meet within 15 m; gaps are either
  bridged via Valhalla `/route` (marked `inferred`, confidence 0) or the
  route honestly splits into fragments — geometry is never invented;
- every non-inferred consensus edge is supported by ≥2 traces (or by the
  majority of traces covering that part of the route).

## Usage

```python
from routebuilder.config import ReconstructionConfig
from routebuilder.engine import reconstruct_from_raw
from routebuilder.valhalla import make_bridge_fn

config = ReconstructionConfig()
output = reconstruct_from_raw(
    raw_traces,                      # dict[trace_id, list[RawPoint]]
    config=config,
    bridge_fn=make_bridge_fn(config.consensus),
)
for route in output.routes:
    print(route.ramal_label, len(route.edges), route.diagnostics)
```

DB adapters (standalone core, thin edges): `adapters/db_load.py` reads
`Trip`/`TripPoint` rows into `MatchedTrace`s; `adapters/db_persist.py`
writes a `ConsensusRoute` as a PENDING `Route` (+`RouteEdge`s) and
continues the version chain. The production pipeline is NOT wired to
this package yet — that swap is a separate, later change.

## Tests

```bash
uv run pytest                  # unit tests (no services needed)
uv run pytest -m valhalla      # e2e against seed routes (needs Valhalla on :8002)
```

The e2e suite simulates noisy/partial/clean traces along
`transit-lab/seed/routes/*.geojson`, reconstructs, and asserts metric
bounds (Fréchet, coverage, edge precision — see
`evaluation/harness.py`).
