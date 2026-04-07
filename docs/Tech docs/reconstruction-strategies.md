# Route Reconstruction Strategies

This document describes the route reconstruction strategies implemented in the `geodata.reconstruction` package. Each strategy takes a set of cleaned GPS traces belonging to a single transit line and produces a single reconstructed route geometry (GeoJSON LineString).

All strategies implement the `ReconstructionStrategy` protocol defined in `geodata.reconstruction.base` and are registered in `geodata.reconstruction.registry`.

## Table of Contents

- [Overview](#overview)
- [Shared Infrastructure](#shared-infrastructure)
- [Strategy 1: Route File Preview](#strategy-1-route-file-preview)
- [Strategy 2: Pairwise Overlap Join](#strategy-2-pairwise-overlap-join)
- [Strategy 3: DBSCAN Consensus](#strategy-3-dbscan-consensus)
- [Strategy 4: DBSCAN Grid-Search Consensus](#strategy-4-dbscan-grid-search-consensus)
- [Strategy 5: KDE Density Ridge](#strategy-5-kde-density-ridge)
- [Strategy 6: Valhalla Edge-Graph Consensus](#strategy-6-valhalla-edge-graph-consensus)
- [Strategy 7: Segment-Vote Consensus](#strategy-7-segment-vote-consensus)
- [Comparative Summary](#comparative-summary)
- [Literature References](#literature-references)

---

## Overview

The strategies fall into three families, following the taxonomy established by Biagioni & Eriksson (2012):

| Family | Strategies | Core idea |
|---|---|---|
| **Trace-merging** | Pairwise Overlap Join | Merge raw traces sequentially by matching overlapping endpoints |
| **Clustering (k-means family)** | DBSCAN Consensus, DBSCAN Grid-Search | Pool all points, cluster with DBSCAN, link cluster centroids |
| **Kernel Density Estimation** | KDE Density Ridge | Build a 2D density grid, threshold, extract the density ridge |
| **Map-matching consensus** | Edge-Graph Consensus, Segment-Vote Consensus | Match traces to OSM edges via HMM, build a weighted graph, find the consensus path |

Additionally, the **Route File Preview** serves as a ground-truth baseline for visual comparison.

### Input data

All strategies receive `ReconstructionTrace` objects, where each trace is a list of `ReconstructionPoint(longitude, latitude, point_index, timestamp)`. In the transit-lab pipeline, these points come from `TripPoint` records, which are **already map-matched (snapped) to the OSM road network** via Valhalla's Meili HMM. The raw, unprocessed GPS points are stored separately as `TripSessionPoint` records. This pre-snapping is an advantage for strategies that work on point geometry (DBSCAN, KDE, Overlap Join), since GPS noise has already been reduced.

---

## Shared Infrastructure

### Road-grid snapping (`_road_grid.py`)

Several strategies (DBSCAN, DBSCAN Grid-Search, KDE) produce a route from cluster centroids or density ridges that doesn't exactly follow the road network. As a post-processing step, these routes are passed through `snap_route_to_road_grid()`, which map-matches the reconstructed route back onto OSM roads via Valhalla. This step uses three parameters shared across strategies:

| Parameter | Default | Description |
|---|---|---|
| `snap_costing` | `"bus"` | Valhalla routing profile. `"bus"` restricts matching to bus-accessible roads. |
| `snap_search_radius` | `60` | How far from each route point Valhalla looks for a candidate road edge (metres). |
| `snap_gps_accuracy` | `20` | Expected positional error, used by the HMM emission probability. |

### MST Diameter Ordering

Used by DBSCAN Consensus, DBSCAN Grid-Search, and KDE Density Ridge to order an unordered set of points into a sequential route. The algorithm:

1. Compute pairwise distances between all points.
2. Build a **Minimum Spanning Tree** (MST) using Prim's algorithm.
3. Find the **tree diameter** — the longest path between any two nodes — via two BFS/DFS passes from arbitrary start.
4. The diameter path gives the sequential order of points along the route.

This approach was introduced in the codebase as an improvement over simple mean-point-index ordering, which fails when traces are partial (starting mid-route). The MST diameter learns the route's geometric backbone from the centroid cloud itself.

**Origin:** MST construction is classical graph theory (Prim, 1957; Kruskal, 1956). The two-pass diameter trick is a standard tree algorithm. Their combination for route ordering from spatial point clouds is an application-specific composition.

---

## Strategy 1: Route File Preview

**Key:** `route_file_preview`
**Source:** `reconstruction/route_file_preview/strategy.py`

### Description

Loads a pre-existing route from a GeoJSON file. No computation is performed. Used as a **ground-truth baseline** for visual comparison against other strategies in the reconstruction lab notebook.

### Parameters

| Parameter | Default | Description |
|---|---|---|
| `route_file` | `""` | Path to a `.geojson` file containing the route geometry. |

### Considers the road network?

No. Reads a static file.

### Behaviour with noisy traces

Not applicable — ignores traces entirely.

---

## Strategy 2: Pairwise Overlap Join

**Key:** `overlap_join_preview`
**Source:** `reconstruction/overlap_join_preview/strategy.py`

### How It Works

1. **Seed:** Start with the longest trace as the initial route.
2. **Greedy merge loop:** For each remaining trace, evaluate all four merge orientations:
   - Forward trace appended to route end
   - Forward trace prepended to route start
   - Reversed trace appended to route end
   - Reversed trace prepended to route start
3. **Overlap detection:** For each candidate, scan from the maximum possible overlap length downward. For a given overlap length *k*, check whether every corresponding point pair (suffix of the left sequence vs. prefix of the right) falls within `overlap_tolerance_meters` using haversine distance. The first valid overlap (longest) is accepted.
4. **Merge selection:** Among the four candidates per trace, pick the one with the best sort key: `(overlap_length, -mean_distance, -endpoint_gap, merged_length)`.
5. **Merge:** Concatenate the sequences, eliminating the overlapping suffix.
6. Repeat until all traces are merged.

### Parameters

| Parameter | Default | Description |
|---|---|---|
| `overlap_tolerance_meters` | `25.0` | Maximum haversine distance between paired points for an overlap to be accepted. Looser values allow more merges but introduce more spatial error. |
| `min_overlap_points` | `1` | Minimum overlap length (in points) for a merge. Higher values require stronger overlap evidence. |

### Considers the road network?

**No.** Works entirely on raw point coordinates. The output follows the original GPS geometry and is not snapped to any road grid.

### Behaviour with noisy traces

Poor. Every GPS point is used as-is — no noise filtering occurs. Noisy points propagate directly into the merged route. The overlap detection may also fail if noise disrupts the suffix-prefix alignment.

### Strengths

- No external dependencies (no Valhalla, no DBSCAN).
- Simple, interpretable algorithm.
- Can work with very few traces (even 2).

### Limitations

- **Greedy and order-dependent:** A bad early merge propagates errors permanently.
- **No road alignment:** Output zigzags across the actual road geometry.
- **Sensitive to trace orientation and starting points:** If traces don't share clear suffix-prefix overlaps (e.g., one trace starts mid-route), the algorithm may produce a fragmented or duplicated route.
- **O(n * m) per merge step:** For *n* remaining traces with *m* points each, each merge evaluates all candidates with all overlap lengths.

### Literature

This strategy follows the **trace-merging** family described by Biagioni & Eriksson (2012), which includes algorithms by Cao & Krumm (2009) and Niehoefer et al. (2009). The greedy suffix-prefix merging is related to sequence assembly in bioinformatics (overlap-layout-consensus), adapted here for spatial sequences.

**Differences from literature:** The Cao & Krumm algorithm includes a "clarification" preprocessing step — a particle simulation that pulls nearby traces together to reduce GPS noise before merging. Our implementation omits this step, relying instead on the fact that input points are already pre-snapped to OSM roads. The Niehoefer et al. variant refines edge positions during merging, which we also do not perform.

---

## Strategy 3: DBSCAN Consensus

**Key:** `dbscan_consensus_preview`
**Source:** `reconstruction/dbscan_preview/strategy.py`
**Core algorithm:** `geodata/cluster.py`

### How It Works

1. **Pool** all points from all traces into a single cloud. Each point carries: `(latitude, longitude, point_index, trace_index)`.
2. **DBSCAN clustering** with the haversine metric directly on WGS-84 coordinates (converted to radians). The `eps` parameter is converted from metres to radians via `eps_meters / 6,371,000`. Points not reaching the core-point threshold are labelled as noise and discarded.
3. **Cluster statistics:** For each cluster, compute:
   - Centroid (mean latitude, mean longitude of member points)
   - Mean point index across member points
   - Number of distinct contributing traces
4. **Cluster ordering** via learned centerline (MST diameter):
   - Build pairwise haversine distance matrix between centroids.
   - Compute MST, extract the diameter path as the route backbone.
   - Project every centroid onto this backbone polyline, sort by arclength.
   - If the learned order is reversed relative to mean point indices, flip it.
   - Fallback for ≤2 clusters: sort by mean point index.
5. **Road-grid snapping:** Pass the ordered centroids through Valhalla map-matching to produce a road-aligned route.

### Parameters

| Parameter | Default | Description |
|---|---|---|
| `eps_meters` | `5.0` | DBSCAN neighbourhood radius. **Smaller** = tighter clusters, more noise, more detail. **Larger** = bigger clusters, fewer noise points, but centroids drift away from tight turns. |
| `min_samples` | `2` (auto: `max(2, n_traces // 3)`) | Core-point threshold. A point must appear within `eps` of at least `min_samples` other points to anchor a cluster. **Higher** = stricter noise rejection, but may lose route endpoints where fewer traces overlap. |
| `snap_costing` | `"bus"` | Valhalla routing profile for road snapping. |
| `snap_search_radius` | `60` | Search radius for road snapping (metres). |
| `snap_gps_accuracy` | `20` | GPS accuracy hint for road snapping. |

### Considers the road network?

**Partially.** Clustering is purely geometric (no road awareness). The road network is only used in the final snapping step. This means centroids at curves will be pulled *inside* the curve (away from the road), and the snapping step must correct this.

### Behaviour with noisy traces

Moderate. DBSCAN natively labels sparse/isolated points as noise, which provides built-in noise rejection. However, `eps` is a global parameter — areas with tightly spaced parallel roads need small `eps`, while sparse suburban areas need large `eps`. A single value forces a trade-off.

### Strengths

- Well-understood algorithm with solid theoretical foundations.
- Built-in noise rejection via DBSCAN's noise labelling.
- MST diameter ordering is robust to partial traces.
- Relatively fast (DBSCAN with ball-tree is O(n log n) on average).

### Limitations

- **Centroid drift on curves:** The centroid of a cluster at a bend lies inside the curve, not on the road. Road-snapping partially compensates but may fail on sharp turns.
- **Single global `eps`:** Cannot adapt to varying road density across the route.
- **MST ordering breaks on loops:** If the route has large loops, the tree diameter doesn't correspond to the actual route traversal order.
- **Route truncation:** Endpoints with low trace coverage may be labelled as noise, truncating the reconstructed route.
- **Requires ≥2 clusters:** If all points collapse into a single cluster (very large `eps`), the strategy fails.

### Literature

DBSCAN was introduced by Ester et al. (1996), "A Density-Based Algorithm for Discovering Clusters in Large Spatial Databases with Noise" (KDD '96). The use of DBSCAN with haversine distance for geographic point clustering is well-established in spatial data mining.

**Differences from literature:** The Biagioni & Eriksson survey places clustering approaches in the "k-means family" (Edelkamp & Schrödl, 2003), which uses k-means with distance and bearing constraints. Our implementation differs in three ways:
1. **DBSCAN instead of k-means:** DBSCAN doesn't require pre-specifying the number of clusters, handles noise natively, and finds clusters of arbitrary shape.
2. **MST diameter ordering instead of mean-point-index sorting:** The original k-means approach links clusters by mean point index, which fails for partial traces. Our MST backbone approach learns the route geometry from the centroids themselves.
3. **Post-hoc road snapping:** Edelkamp & Schrödl link clusters into road segments directly. We produce a raw centroid polyline and snap it to OSM in a separate step.

---

## Strategy 4: DBSCAN Grid-Search Consensus

**Key:** `dbscan_grid_search_preview`
**Source:** `reconstruction/dbscan_grid_search_preview/strategy.py`

### How It Works

1. **Generate parameter grid:** Create a list of `(eps, min_samples)` combinations from the configured ranges.
2. **For each combination:** Run the DBSCAN consensus algorithm (same as Strategy 3) and score the result.
3. **Scoring:** Each candidate route is evaluated on three metrics:
   - **Route support ratio:** Resample the candidate route at fixed intervals (`route_support_step_meters`). For each sampled point, check if it falls within `overlap_tolerance_meters` of any original trace geometry (projected to local metres using Shapely). The fraction of supported points measures "is every part of this route backed by trace evidence?"
   - **Overlap ratio:** For every original GPS point across all traces, check if it falls within `overlap_tolerance_meters` of the candidate route. Measures "does this route capture most of the observed points?"
   - **Overlap error:** Mean distance (metres) of overlapping points to the route. Lower is better.
4. **Ranking:** Candidates are sorted by: `(route_support_ratio, overlap_ratio, -overlap_error, -noise_points, -route_point_count)`.
5. **Snap best candidate** to the road grid.

### Parameters

| Parameter | Default | Description |
|---|---|---|
| `eps_start_meters` | `5.0` | Start of the `eps` search range. |
| `eps_stop_meters` | `40.0` | End of the `eps` search range. |
| `eps_step_meters` | `5.0` | Step between `eps` candidates. |
| `min_samples_min` | `1` | Start of `min_samples` range. |
| `min_samples_max` | `0` (auto: `min(12, n_traces)`) | End of `min_samples` range. `0` = auto-calculate from trace count. |
| `overlap_tolerance_meters` | `25.0` | Buffer distance for both scoring metrics. |
| `route_support_step_meters` | `10.0` | Resampling interval for route support evaluation. Smaller = more precise but slower. |
| `snap_costing` | `"bus"` | Valhalla routing profile for road snapping. |
| `snap_search_radius` | `60` | Search radius for road snapping. |
| `snap_gps_accuracy` | `20` | GPS accuracy hint for road snapping. |

### Considers the road network?

**Partially.** Same as DBSCAN Consensus — clustering is purely geometric; road network only enters during the final snapping step.

### Behaviour with noisy traces

Moderate to good. By evaluating multiple parameter combinations, the grid search can find the `(eps, min_samples)` pair that best balances noise rejection against route coverage. However, the same traces are used for both clustering and evaluation, so there is no cross-validation — the best score may correspond to overfitting to noise patterns.

### Strengths

- Automates parameter tuning for DBSCAN.
- The dual scoring (route support + overlap) provides a balanced evaluation.
- Inherits DBSCAN's noise rejection.

### Limitations

- **Inherits all DBSCAN limitations** (centroid drift, global `eps`, MST ordering issues).
- **Computationally expensive:** With default params: 8 eps values × 12 min_samples = 96 DBSCAN runs, each with O(n × m) scoring.
- **Scoring can be misleading:** Overlap ratio rewards short routes in dense areas. Route support ratio partially compensates, but both use the same tolerance, so they're correlated.
- **No cross-validation:** Same data for clustering and evaluation → risk of overfitting to noise.

### Literature

This strategy combines DBSCAN (Ester et al., 1996) with a grid-search hyperparameter optimization. Grid search is a standard technique in machine learning (see Bergstra & Bengio, 2012, "Random Search for Hyper-Parameter Optimization," though we use exhaustive grid rather than random search).

**Differences from literature:** The scoring metrics (route support ratio and overlap ratio) are custom-designed for this specific problem. The route support ratio is conceptually similar to the "coverage" metrics used in map inference evaluation (Biagioni & Eriksson, 2012), while the overlap ratio corresponds to a form of recall. The combination is novel.

---

## Strategy 5: KDE Density Ridge

**Key:** `kde_density_ridge_preview`
**Source:** `reconstruction/kde_preview/strategy.py`

### How It Works

1. **Pool** all trace points into a single point cloud.
2. **Project** to local XY metres using an equirectangular projection centred on the point cloud centroid.
3. **Build a 2D histogram** on a regular grid with the configured cell size. The grid is padded by 3× the bandwidth to prevent edge clipping.
4. **Gaussian smoothing:** Apply `scipy.ndimage.gaussian_filter` with `sigma = bandwidth_meters / cell_size_meters`. This approximates a proper 2D Gaussian KDE.
5. **Threshold:** Identify cells where density ≥ `density_threshold × max_density`.
6. **Connected components:** Use `scipy.ndimage.label` to find connected regions. Keep only the largest component (the main transit corridor).
7. **Ridge extraction (dual slicing):**
   - **Row-wise:** For each occupied row, compute the density-weighted centroid column position.
   - **Column-wise:** For each occupied column, compute the density-weighted centroid row position.
   - Merge both point sets and deduplicate on a 1-cell tolerance grid.
   This dual-slicing approach captures the centerline regardless of route orientation, including turns and L-shaped segments, without requiring morphological skeletonization (which would need scikit-image).
8. **Spatial subsampling:** If the ridge has more than 1,200 points, merge nearby points on a coarser grid to keep MST ordering tractable.
9. **MST diameter ordering:** Order the ridge points sequentially (same algorithm as DBSCAN strategies).
10. **Convert** back to WGS-84 lon/lat coordinates.
11. **Snap to road grid** via Valhalla map-matching.

### Parameters

| Parameter | Default | Description |
|---|---|---|
| `cell_size_meters` | `5.0` | Grid cell size. Smaller = finer detail but larger grid and slower computation. A safety limit prevents grids larger than 20M cells. |
| `bandwidth_meters` | `15.0` | Gaussian kernel standard deviation. **Larger** = smoother density, connects nearby traces, bridges small gaps, but blurs the separation between parallel roads. **Smaller** = sharper density, preserves fine spatial detail. |
| `density_threshold` | `0.15` | Threshold as a fraction of the maximum density value. **Lower** = includes more of the transit corridor (captures route endpoints with low coverage), but also includes more noise. **Higher** = stricter noise rejection, but may truncate route ends. |
| `snap_costing` | `"bus"` | Valhalla routing profile for road snapping. |
| `snap_search_radius` | `60` | Search radius for road snapping. |
| `snap_gps_accuracy` | `20` | GPS accuracy hint for road snapping. |

### Considers the road network?

**Partially.** Density estimation and ridge extraction are purely geometric. The road network enters only during the final snapping step. However, because the input points are pre-snapped to OSM roads, the density naturally concentrates along actual road segments, giving this strategy an indirect awareness of the network geometry.

### Behaviour with noisy traces

Good. The Gaussian smoothing averages out point-level noise, and thresholding removes low-density areas that likely correspond to GPS errors or infrequently traversed detours. With pre-snapped input points, the density bands are already tight and road-aligned, making the threshold more reliable than on raw GPS data.

### Strengths

- **Aggregate approach:** Treats all points simultaneously rather than trace-by-trace, naturally averaging out noise — this is the property that made KDE the best-performing approach in Biagioni & Eriksson's evaluation.
- **No per-point clustering decisions:** Unlike DBSCAN, every point contributes to the density field proportionally, without a hard core-point threshold.
- **Threshold is intuitive:** A single parameter (fraction of max density) controls the noise/coverage trade-off.
- **Benefits from pre-snapped points:** The main weakness identified in the literature (GPS scatter) is already mitigated by the pipeline's earlier map-matching step.

### Limitations

- **Global density threshold:** The same threshold applies everywhere. Route endpoints with naturally lower trace coverage may be cut off. This is the exact limitation Biagioni & Eriksson identified as the key bottleneck for KDE methods.
- **Dual slicing is an approximation:** The row/column centroid approach produces a good centerline for routes aligned with the grid axes and for gradual turns, but may produce slight irregularities at very sharp turns or complex intersections.
- **Grid memory:** For very long routes (tens of kilometres) with fine cell sizes, the grid can become large. A safety limit of 20M cells is enforced.
- **Single component:** Only the largest connected component is kept. If the density threshold fragments the route into disconnected segments, only the main body is reconstructed.

### Literature

KDE-based map inference was introduced by Davies et al. (2006), "Scalable, Distributed, Real-Time Map Generation," which computes a kernel density estimate over a grid, thresholds to identify roads, and extracts centerlines via Voronoi graphs. This was evaluated as the best-performing approach in Biagioni & Eriksson (2012), achieving the highest F-scores across most matching thresholds.

**Differences from literature:**

1. **No Voronoi graph extraction:** Davies et al. extract road centerlines by computing the Voronoi graph along contour outlines (after binary thresholding). We use a density-weighted centroid slicing approach instead, which is simpler and avoids the need for Voronoi computation.
2. **No direction annotation:** Davies et al. use separate directional KDEs to annotate each road segment with permitted travel directions. We do not perform direction inference, since our goal is to reconstruct a single transit route rather than a full road map.
3. **No morphological operations:** The original algorithm uses contour following and antialiasing-style edge accounting. Our implementation uses Gaussian smoothing on a histogram (which is a standard KDE approximation) followed by direct ridge extraction.
4. **Pre-snapped input:** The original algorithm operates on raw GPS data, where GPS scatter is the primary challenge. Our input points are already map-matched to OSM, so the density bands are naturally tight and road-aligned, allowing for a lower bandwidth and more reliable thresholding.
5. **MST diameter ordering:** After extracting ridge points, we order them sequentially using the MST diameter heuristic. Davies et al. instead produce a full graph of road segments (which doesn't require sequential ordering). Our approach converts the ridge into a single route polyline.

---

## Strategy 6: Valhalla Edge-Graph Consensus

**Key:** `edge_graph_consensus_preview`
**Source:** `reconstruction/edge_graph_consensus_preview/strategy.py`

### How It Works

1. **Map-match every trace** individually through Valhalla's Meili HMM service. Each trace becomes an ordered sequence of OSM edge IDs with direction (e.g., `12345:f` for forward, `12345:r` for reverse).
2. **Collapse consecutive duplicates** in each trace's edge sequence — if a trace crosses the same edge multiple times in a row (common at intersections), keep only one occurrence.
3. **Build a weighted directed graph:**
   - **Node weights** (`Counter[edge_id]`): How many traces traversed each edge. Represents the popularity of each road segment.
   - **Edge weights** (`Counter[(edge_a, edge_b)]`): How many traces traversed `edge_a` immediately followed by `edge_b`. Represents the strength of transitions between consecutive road segments.
4. **Collect geometry samples:** For each edge, store the shape coordinates returned by Valhalla from each trace match. Select the representative geometry as the one with the most points (longest).
5. **Beam search for consensus path:**
   - **Start selection:** Rank all edges by `(node_weight, net_outgoing_flow, outgoing_weight)`. Take the top `start_candidates` edges as starting points.
   - **Path scoring:** `score = Σ node_weights + transition_weight × Σ edge_weights_along_path`.
   - **Expansion:** At each step, extend all paths in the beam by one edge (following graph successors). Keep the top `beam_width` paths. Skip edges already in the path (cycle avoidance).
   - **Termination:** Stop when no paths can be extended or path length reaches the total number of unique edges.
6. **Stitch geometries:** Concatenate the representative geometries along the consensus edge sequence into a single LineString. Adjacent geometries sharing an endpoint are seamlessly joined.

### Parameters

| Parameter | Default | Description |
|---|---|---|
| `costing` | `"bus"` | Valhalla routing profile for map-matching. Determines which roads are eligible. |
| `search_radius` | `60` | How far from each GPS point Valhalla searches for candidate road edges (metres). **Larger** = more robust to GPS drift, but may snap to the wrong parallel street. |
| `gps_accuracy` | `20` | Expected GPS positional error (metres). Informs the HMM emission probability. **Larger** = HMM trusts GPS less, favours road connectivity. |
| `beam_width` | `8` | Number of candidate paths kept at each beam-search step. **Higher** = more thorough search, less likely to prune the correct path early, but slower. |
| `start_candidates` | `5` | Number of starting edges to try. **Higher** = less sensitive to start selection. |
| `transition_weight` | `2.0` | Multiplier on transition (edge) weights vs. node weights in path scoring. **Higher** = favours paths following frequently observed transitions. **Lower** = favours paths through individually popular edges regardless of traversal order. |

### Considers the road network?

**Yes, natively.** The entire algorithm operates on OSM road edges. The output is inherently road-aligned because every edge in the consensus path is a real road segment from the OSM graph. No post-hoc road snapping is needed.

### Behaviour with noisy traces

Moderate. Valhalla's HMM map-matching absorbs some GPS noise during the trace-matching step. However, if Valhalla snaps a trace to the wrong street (common with parallel one-way streets or GPS drift into courtyards), those incorrect edges receive votes and can pollute the consensus graph.

### Strengths

- **Road-native:** Output is always a valid path on the OSM road network.
- **Leverages Valhalla's HMM:** Benefits from Meili's probabilistic map matching, which considers road connectivity, turn penalties, and GPS noise.
- **Handles partial traces well:** Each trace contributes its edges independently. A trace covering only part of the route still votes for those edges.
- **Transition weights encode sequential structure:** Unlike DBSCAN (which only considers point locations), this strategy considers the *order* in which road segments are traversed.

### Limitations

- **Depends on Valhalla match quality:** If Valhalla's HMM snaps to wrong roads (parallel streets, missing OSM data, poor GPS), those errors propagate as spurious votes.
- **No direction normalization:** Traces going forward and backward create different edge keys (`id:f` vs `id:r`). Without pre-filtering by direction, votes are split.
- **No support thresholding:** Every edge that appears even once is included. A single mismatched trace can introduce spurious edges.
- **Beam search is heuristic:** May miss the globally optimal path. The search terminates at `len(node_weights)` steps, which may be insufficient for routes reusing the same edges in different contexts.
- **Start selection bias:** Starts from the most popular edges. If the actual route start has low trace coverage, the algorithm may begin mid-route.

### Literature

HMM map-matching is based on Newson & Krumm (2009), "Hidden Markov Map Matching Through Noise and Sparseness" (ACM GIS). Valhalla's Meili engine implements this algorithm. Beam search originates from AI (Russell & Norvig, *Artificial Intelligence: A Modern Approach*).

**Differences from literature:**

1. **Consensus graph from matched edges:** The idea of building a weighted graph from map-matched traces and finding a consensus path is related to Ahmed & Wenk (2012), "Constructing Street Networks from GPS Trajectories." However, Ahmed & Wenk build a road network from scratch using geometric proximity, while our strategy leverages an existing OSM network via Valhalla and builds a consensus over *matched* edges.
2. **Beam search instead of shortest-path:** Ahmed & Wenk and most map inference algorithms use shortest-path or graph traversal algorithms. Our beam search with a composite score (node popularity + transition frequency) is a heuristic that prioritises frequently traversed paths over geometrically shortest ones.
3. **No explicit road map inference:** This strategy does not infer new roads. It selects a subset of existing OSM edges that best represents the transit route. This is a fundamentally narrower problem than general map inference.

---

## Strategy 7: Segment-Vote Consensus

**Key:** `segment_vote_consensus_preview`
**Source:** `reconstruction/segment_vote_consensus_preview/strategy.py`

This is the most sophisticated strategy, directly addressing several limitations of the Edge-Graph Consensus.

### How It Works

1. **Map-match every trace** through Valhalla's Meili HMM (same as Strategy 6).
2. **Collapse consecutive duplicate edges**, keeping paired geometries aligned.
3. **Canonicalize direction:** Compare each trace's edge ID sequence with its reverse (lexicographic tuple comparison). If the reversed sequence is lexicographically smaller, reverse the trace. This normalizes all traces to a consistent direction regardless of which way the bus was going.
4. **Vote with sets:** Each trace contributes its **unique set** of edge IDs and its **unique set** of consecutive edge pairs. A trace that loops over the same edge multiple times still only votes once — preventing frequency bias from loops.
5. **Support thresholding:**
   - **Edge support:** An edge must be supported by ≥ `min_edge_support` traces (auto: `ceil(n_matched × edge_support_fraction)`).
   - **Pair support:** An edge pair must be supported by ≥ `min_pair_support` traces (auto: `ceil(n_matched × pair_support_fraction)`).
   - Both source and target of a pair must individually survive edge filtering.
6. **Connected component detection:** BFS to find connected components in the filtered support graph. This handles route variants or disconnected segments arising from aggressive filtering.
7. **Beam search per component:** Run beam search within each connected component (same algorithm as Strategy 6), using component-local node and pair weights.
8. **Output multiple features:** Each connected component becomes a separate GeoJSON LineString feature, sorted by total support weight (strongest component first).

### Parameters

| Parameter | Default | Description |
|---|---|---|
| `costing` | `"bus"` | Valhalla routing profile. |
| `search_radius` | `60` | Map-matching search radius (metres). |
| `gps_accuracy` | `20` | GPS accuracy hint for HMM. |
| `beam_width` | `8` | Beam search width. |
| `transition_weight` | `2.0` | Transition weight in path scoring. |
| `min_edge_support` | `0` (auto) | Minimum trace count for an edge to survive. `0` = auto-calculate from fraction. **Higher** = stricter, keeps only well-attested edges. |
| `min_pair_support` | `0` (auto) | Minimum trace count for a consecutive edge pair to survive. `0` = auto-calculate. |
| `edge_support_fraction` | `0.34` | When auto: threshold = `ceil(matched_traces × fraction)`. At 0.34, an edge must appear in ~1/3 of traces. |
| `pair_support_fraction` | `0.34` | Same, for consecutive edge pairs. |

### Considers the road network?

**Yes, natively.** Same as Edge-Graph Consensus — operates entirely on OSM edges.

### Behaviour with noisy traces

Good. The combination of HMM map-matching + support thresholding provides two layers of noise rejection:
1. Valhalla's HMM absorbs GPS-level noise during matching.
2. The support threshold filters out edges that appear in fewer than ~1/3 of traces, removing spurious matches from individual traces.

### Strengths

- **Direction normalization:** Canonicalization handles mixed-direction traces without requiring pre-filtering.
- **Set-based voting prevents loop bias:** Unlike Edge-Graph Consensus where a looping trace inflates edge counts, set-based voting gives each trace equal influence.
- **Support thresholding:** Removes spurious edges from mismatched traces, producing a cleaner consensus graph.
- **Multi-component output:** If filtering fragments the route, each fragment is reconstructed independently rather than lost. This can reveal route variants or detect where trace coverage is insufficient.
- **Automatic threshold calibration:** The fraction-based auto-thresholding adapts to the number of available traces.

### Limitations

- **Canonicalization is fragile for asymmetric routes:** Lexicographic comparison of edge ID tuples is an arbitrary tie-breaker. If the forward and backward routes use different streets (one-way systems), canonicalization may incorrectly align some traces, mixing edges from both directions.
- **Set-based voting loses frequency signal:** Cannot distinguish "an edge every trace uses" from "an edge one trace loops over" — both count as 1 vote per trace. This is intentional noise reduction but sacrifices a potential confidence signal.
- **Global support threshold:** The default 34% fraction may cut off route endpoints where only a few traces begin or end. This causes the same route truncation problem as DBSCAN's `min_samples`.
- **Component fragmentation:** Aggressive filtering can split a valid route into disconnected components, producing multiple separate LineStrings rather than one continuous route.
- **Valhalla dependency:** Same fundamental dependency on match quality as Edge-Graph Consensus.

### Literature

This strategy combines HMM map-matching (Newson & Krumm, 2009) with segment-level voting, conceptually related to Davies et al. (2006), who use trace density on road segments to infer road networks.

**Differences from literature:**

1. **Canonical direction via lexicographic comparison:** We are not aware of a published algorithm using tuple-level lexicographic ordering for direction normalization. Most approaches either pre-filter by direction or use heading-based heuristics.
2. **Set-based voting instead of count-based:** The choice to count each edge once per trace (rather than once per traversal) is a design decision specific to our use case (informal transit with potential GPS loops). Most consensus approaches in the literature use raw frequency counts.
3. **Support thresholding with auto-calibration:** The fraction-based threshold (`ceil(n × 0.34)`) adapts to the dataset size. This is conceptually similar to the density thresholds in KDE methods but applied at the edge level rather than the spatial level.
4. **Connected component decomposition:** Handling route fragments as separate components is not commonly seen in transit route reconstruction. It is more common in general road network inference (e.g., Cao & Krumm, 2009).

---

## Comparative Summary

| Aspect | Overlap Join | DBSCAN | DBSCAN Grid | KDE Ridge | Edge-Graph | Segment-Vote |
|---|---|---|---|---|---|---|
| **Family** | Trace-merging | Clustering | Clustering | KDE | Map-matching | Map-matching |
| **Road-aligned output** | No | Post-snap | Post-snap | Post-snap | Native | Native |
| **Uses OSM network** | No | Snap only | Snap only | Snap only | Core | Core |
| **Direction handling** | Tries both | Ignores | Ignores | Ignores | None | Canonicalization |
| **Noise filtering** | None | DBSCAN labels | DBSCAN labels | Density threshold | None | Support threshold |
| **Ordering method** | Greedy merge | MST diameter | MST diameter | MST diameter | Beam search | Beam search |
| **Multi-component** | No | No | No | No | No | Yes |
| **Partial trace handling** | Poor | Moderate | Moderate | Moderate | Good | Good |
| **Loop handling** | Poor | Poor | Poor | Poor | Cycle-avoiding | Cycle-avoiding |
| **External dependency** | None | Valhalla (snap) | Valhalla (snap) | Valhalla (snap) | Valhalla (core) | Valhalla (core) |
| **Computational cost** | Low | Low | High | Low | Moderate | Moderate |
| **Parameter sensitivity** | Low | High | Low (auto-tuned) | Moderate | Moderate | Moderate |

### When to use each strategy

- **Route File Preview:** Ground-truth comparison baseline.
- **Overlap Join:** Quick baseline when no Valhalla is available and traces have clear sequential overlap.
- **DBSCAN Consensus:** Fast first approximation. Good when you have many traces with consistent coverage and want to quickly see the route shape.
- **DBSCAN Grid-Search:** When DBSCAN results are sensitive to parameters and you want automated tuning.
- **KDE Density Ridge:** Best geometric approach for pre-snapped data. Handles noise well by averaging. Good alternative when the Valhalla-based strategies struggle with OSM data quality.
- **Edge-Graph Consensus:** When traces are directionally consistent and you want a road-native result without manual parameter tuning.
- **Segment-Vote Consensus:** Most robust general-purpose strategy. Best for mixed-direction traces, partial traces, and noisy data.

---

## Literature References

### Core Algorithms

- **DBSCAN:** Ester, M., Kriegel, H.-P., Sander, J., & Xu, X. (1996). A Density-Based Algorithm for Discovering Clusters in Large Spatial Databases with Noise. *Proceedings of the 2nd International Conference on Knowledge Discovery and Data Mining (KDD '96)*, pp. 226–231.

- **HMM Map Matching:** Newson, P., & Krumm, J. (2009). Hidden Markov Map Matching Through Noise and Sparseness. *Proceedings of the 17th ACM SIGSPATIAL International Conference on Advances in Geographic Information Systems (ACM GIS '09)*, pp. 336–343.

- **Beam Search:** Russell, S., & Norvig, P. (2021). *Artificial Intelligence: A Modern Approach* (4th ed.). Pearson.

- **MST / Prim's Algorithm:** Prim, R. C. (1957). Shortest Connection Networks and Some Generalizations. *Bell System Technical Journal*, 36(6), pp. 1389–1401.

- **Fréchet Distance:** Eiter, T., & Mannila, H. (1994). Computing Discrete Fréchet Distance. *Technical Report CD-TR 94/64*, TU Vienna. (Used in `geodata.evaluate` for measuring reconstruction accuracy against ground truth.)

### Map Inference and Route Reconstruction

- **Biagioni & Eriksson Survey:** Biagioni, J., & Eriksson, J. (2012). Inferring Road Maps from Global Positioning System Traces: Survey and Comparative Evaluation. *Transportation Research Record: Journal of the Transportation Research Board*, No. 2291, pp. 61–71.

- **Davies et al. (KDE):** Davies, J. J., Beresford, A. R., & Hopper, A. (2006). Scalable, Distributed, Real-Time Map Generation. *IEEE Pervasive Computing*, 5(4), pp. 47–54.

- **Edelkamp & Schrödl (k-means):** Edelkamp, S., & Schrödl, S. (2003). Route Planning and Map Inference with Global Positioning Traces. In *Computer Science in Perspective*, pp. 128–145. Springer.

- **Cao & Krumm (trace-merging):** Cao, L., & Krumm, J. (2009). From GPS Traces to a Routable Road Map. *Proceedings of the 17th ACM SIGSPATIAL International Conference on Advances in Geographic Information Systems (ACM GIS '09)*, pp. 3–12.

- **Ahmed & Wenk (graph construction):** Ahmed, M., & Wenk, C. (2012). Constructing Street Networks from GPS Trajectories. *Proceedings of the 20th European Symposium on Algorithms (ESA '12)*, pp. 60–71.

- **Niehoefer et al. (trace-merging with classification):** Niehoefer, B., Burber, R., Reith, S., Laur, R., & Lang, W. (2009). GPS Community Map Generation for Enhanced Routing Methods Based on Trace-Collection by Mobile Phones. *Proceedings of the 1st International Conference on Advances in Satellite and Space Communications*, pp. 44–48.

### Supplementary

- **Lou et al. (sparse map-matching):** Lou, Y., Zhang, C., Zheng, Y., Xie, X., Wang, W., & Huang, Y. (2009). Map-Matching for Low-Sampling-Rate GPS Trajectories. *Proceedings of the 17th ACM SIGSPATIAL International Conference on Advances in Geographic Information Systems (ACM GIS '09)*, pp. 352–361.

- **Karagiorgou & Pfoser:** Karagiorgou, S., & Pfoser, D. (2012). On Vehicle Tracking Data-Based Road Network Generation. *Proceedings of the 20th International Conference on Advances in Geographic Information Systems (ACM SIGSPATIAL '12)*, pp. 89–98.

- **Chen et al. (taxi trajectories):** Chen, C., Zhang, D., Li, N., & Zhou, Z.-H. (2011). B-Planner: Planning Bidirectional Night Bus Routes Using Large-Scale Taxi GPS Traces. *IEEE Transactions on Intelligent Transportation Systems*, 15(4), pp. 1451–1465.
