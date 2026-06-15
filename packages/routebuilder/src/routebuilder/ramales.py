"""Ramal handling: variant clustering plus divergence-aware refinement.

Stage 1 (before consensus) groups traces into connected components of
a pairwise *compatibility* relation. Two traces are compatible when
they share enough corridor and neither makes a bounded excursion
(leaves the other's corridor and rejoins it) longer than a cap.
Global metrics (the old pipeline used full-trace Fréchet) get the
partial-trace regime wrong twice over: a truncated run of the same
route looks "far" (endpoint mismatch), and two runs with disjoint
windows look infinitely far — both split into bogus ramales. Here,
partial coverage is treated as *no information*, and disjoint-window
traces join the same component transitively through traces that span
both. Direction is handled *before* clustering.

Stage 2 (after consensus) catches what any pairwise threshold can't:
two ramales sharing 90% of their path and diverging on one stretch.
In the pruned support graph this shows up as two competing branches
between the same pair of junctions, each backed by its own (disjoint)
set of traces. When that happens the cluster is partitioned by branch
usage and consensus runs once per partition.
"""

from __future__ import annotations

from dataclasses import dataclass

import shapely
from geodata.geo_math import interpolate_route
from shapely.geometry import LineString

from .config import ConsensusConfig, RamalConfig
from .graph import SupportGraph, _project_m
from .types import DirectedEdge, LonLat, MatchedTrace


@dataclass
class RamalGroup:
    label: str
    traces: list[MatchedTrace]
    medoid_polyline: list[LonLat] | None = None


def cluster_ramales(
    traces: list[MatchedTrace],
    config: RamalConfig | None = None,
    *,
    existing_ramales: list[tuple[str, list[list[float]]]] | None = None,
) -> list[RamalGroup]:
    """Cluster one direction-group's traces into ramal groups.

    Connected components of the pairwise *compatibility* relation (see
    are_compatible): partial traces with disjoint windows are linked
    transitively through traces that span both, while genuinely
    divergent variants (bounded excursions longer than the cap) break
    the relation and form their own component. Undersized components
    are absorbed into the most-compatible large one.
    """
    config = config or RamalConfig()
    if not traces:
        return []

    min_size = config.min_cluster_size
    if len(traces) <= config.small_regime_max_traces:
        min_size = min(min_size, 2)
    if len(traces) < max(min_size, 2):
        return [RamalGroup(label="main", traces=list(traces), medoid_polyline=traces[0].matched_polyline)]

    n = len(traces)
    resampled = [
        [(p[0], p[1]) for p in interpolate_route(
            [[lon, lat] for lon, lat in t.matched_polyline], config.resample_interval_m
        )]
        for t in traces
    ]
    lines = [
        LineString([_project_m(p, resampled[i][0][1]) for p in resampled[i]])
        if len(resampled[i]) >= 2 else None
        for i in range(n)
    ]

    # Union-find over compatible pairs.
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    compatible_pairs: set[tuple[int, int]] = set()
    for i in range(n):
        for j in range(i + 1, n):
            if are_compatible(resampled[i], lines[j], resampled[j], lines[i], config):
                compatible_pairs.add((i, j))
                ri, rj = find(i), find(j)
                if ri != rj:
                    parent[rj] = ri

    components: dict[int, list[int]] = {}
    for i in range(n):
        components.setdefault(find(i), []).append(i)

    kept = {cid: idxs for cid, idxs in components.items() if len(idxs) >= min_size}
    if not kept:
        longest = max(range(n), key=lambda i: len(resampled[i]))
        return [RamalGroup(
            label="main",
            traces=list(traces),
            medoid_polyline=traces[longest].matched_polyline,
        )]

    # Absorb undersized components into the kept component their
    # members are most compatible with (count of compatible pairs).
    for cid, idxs in components.items():
        if cid in kept:
            continue
        def affinity(target_cid: int) -> int:
            members = set(kept[target_cid])
            return sum(
                1
                for i in idxs
                for j in members
                if (min(i, j), max(i, j)) in compatible_pairs
            )
        best = max(kept, key=affinity)
        kept[best].extend(idxs)

    ordered = sorted(kept.values(), key=len, reverse=True)
    groups: list[RamalGroup] = []
    used_labels: set[str] = set()
    for rank, idxs in enumerate(ordered):
        longest = max(idxs, key=lambda i: len(resampled[i]))
        label = _label_for(
            traces[longest].matched_polyline, rank, existing_ramales, config
        )
        while label in used_labels:  # two components matched one existing label
            label = f"r{len(used_labels) + 2}"
        used_labels.add(label)
        groups.append(RamalGroup(
            label=label,
            traces=[traces[i] for i in sorted(idxs)],
            medoid_polyline=traces[longest].matched_polyline,
        ))
    return groups


def are_compatible(
    a_points: list[LonLat],
    b_line: LineString | None,
    b_points: list[LonLat],
    a_line: LineString | None,
    config: RamalConfig,
) -> bool:
    """Same-ramal test for two traces (symmetric).

    Compatible when they share enough corridor AND neither contains a
    bounded excursion — a stretch that leaves the other's corridor and
    rejoins it — longer than max_branch_excursion_m. Excursions beyond
    the other trace's window ends don't count (that's partial
    coverage, not divergence).
    """
    return (
        _half_compatible(a_points, b_line, config)
        and _half_compatible(b_points, a_line, config)
    )


def _half_compatible(
    points: list[LonLat],
    other_line: LineString | None,
    config: RamalConfig,
) -> bool:
    if other_line is None or len(points) < 2:
        return False
    ref_lat = points[0][1]
    pts = shapely.points([_project_m(p, ref_lat) for p in points])
    distances = shapely.distance(other_line, pts)
    near = distances <= config.distance_threshold_m

    near_count = int(near.sum())
    if near_count * config.resample_interval_m < config.min_overlap_m:
        return False

    near_idx = [i for i, flag in enumerate(near) if flag]
    first, last = near_idx[0], near_idx[-1]
    # Longest run of far points strictly inside [first, last].
    run = longest_run = 0
    for i in range(first, last + 1):
        if near[i]:
            run = 0
        else:
            run += 1
            longest_run = max(longest_run, run)
    if longest_run * config.resample_interval_m > config.max_branch_excursion_m:
        return False

    # Terminal forks: a long far-run at either end is divergence too —
    # but only when the other route keeps going past the point where
    # this trace left it. A trace simply extending beyond the other's
    # terminus (or stopping short of it) is partial coverage, not a
    # fork. This is what separates ramales that share a trunk and
    # split near the end.
    cap = config.max_branch_excursion_m
    head_run_m = first * config.resample_interval_m
    if head_run_m > cap:
        attach_m = float(shapely.line_locate_point(other_line, pts[first]))
        if attach_m > cap:  # the other route existed well before we joined it
            return False
    tail_run_m = (len(points) - 1 - last) * config.resample_interval_m
    if tail_run_m > cap:
        attach_m = float(shapely.line_locate_point(other_line, pts[last]))
        if other_line.length - attach_m > cap:  # it kept going without us
            return False
    return True


def _label_for(
    medoid_polyline: list[LonLat],
    rank: int,
    existing_ramales: list[tuple[str, list[list[float]]]] | None,
    config: RamalConfig,
) -> str:
    if existing_ramales:
        for label, coords in existing_ramales:
            if len(coords) < 2 or len(medoid_polyline) < 2:
                continue
            ref_lat = coords[0][1]
            line = LineString([_project_m((c[0], c[1]), ref_lat) for c in coords])
            resampled = [
                (p[0], p[1]) for p in interpolate_route(
                    [[lon, lat] for lon, lat in medoid_polyline],
                    config.resample_interval_m,
                )
            ]
            if _half_compatible(resampled, line, config):
                return label
    return "main" if rank == 0 else f"r{rank + 1}"


# ---------------------------------------------------------------------------
# Stage 2: divergence detection on the pruned support graph
# ---------------------------------------------------------------------------

@dataclass
class Divergence:
    """A competing branch: evidence that one cluster is really two ramales."""

    branch_edges: list[DirectedEdge]
    branch_trace_ids: set[str]
    trunk_trace_ids: set[str]
    bypassed_edges: list[DirectedEdge]   # the path segment the branch competes with


def detect_divergence(
    pruned: SupportGraph,
    main_path: list[DirectedEdge],
    traces: list[MatchedTrace],
    config: ConsensusConfig | None = None,
) -> Divergence | None:
    """Find a competing branch against the consensus path.

    A divergence is a maximal chain of surviving off-path edges that
    re-attaches to the path on both sides, supported by at least
    ``divergence_min_traces`` traces that are (near-)disjoint from the
    traces traversing the bypassed trunk segment. Returns the largest
    such branch, or None.
    """
    config = config or ConsensusConfig()
    path_set = set(main_path)
    path_index = {edge: i for i, edge in enumerate(main_path)}
    off_path = [e for e in pruned.nodes if e not in path_set]
    if not off_path:
        return None

    # Group off-path edges into chains via arcs among themselves.
    chains = _connected_chains(off_path, pruned)

    best: Divergence | None = None
    for chain in chains:
        chain_set = set(chain)
        # Attachment points on the main path.
        entries = [
            path_index[u]
            for (u, v) in pruned.arcs
            if v in chain_set and u in path_set
        ]
        exits = [
            path_index[v]
            for (u, v) in pruned.arcs
            if u in chain_set and v in path_set
        ]
        if not entries and not exits:
            continue

        branch_traces: set[str] = set()
        for edge in chain:
            branch_traces |= pruned.nodes.get(edge, set())

        # The trunk the branch competes with:
        #  - entry AND exit → a bypass (a parallel stretch in the middle);
        #  - exit only → a head fork (the branch joins the path at the
        #    merge; the competing trunk is the path *before* the merge —
        #    e.g. two lines with different origins sharing a trunk to the
        #    end);
        #  - entry only → a tail fork (different destinations).
        segments: list[list[DirectedEdge]] = []
        if entries and exits:
            entry, exit_ = min(entries), max(exits)
            if exit_ > entry + 1:
                segments.append(main_path[entry + 1 : exit_])
        elif exits:
            exit_ = min(exits)
            if exit_ >= 1:
                segments.append(main_path[:exit_])
        elif entries:
            entry = max(entries)
            if entry < len(main_path) - 1:
                segments.append(main_path[entry + 1 :])

        for trunk_segment in segments:
            if not trunk_segment:
                continue
            trunk_traces: set[str] = set()
            for edge in trunk_segment:
                trunk_traces |= pruned.nodes.get(edge, set())
            trunk_only = trunk_traces - branch_traces
            if (
                len(branch_traces) >= config.divergence_min_traces
                and len(trunk_only) >= config.divergence_min_traces
            ):
                candidate = Divergence(
                    branch_edges=chain,
                    branch_trace_ids=branch_traces,
                    trunk_trace_ids=trunk_only,
                    bypassed_edges=list(trunk_segment),
                )
                if best is None or len(candidate.branch_edges) > len(best.branch_edges):
                    best = candidate

    return best


def split_by_divergence(
    traces: list[MatchedTrace],
    divergence: Divergence,
) -> tuple[list[MatchedTrace], list[MatchedTrace]]:
    """Partition a cluster's traces into (trunk users, branch users).

    Traces in neither set (e.g. partial traces that never reach the
    divergence) stay with the trunk — the larger, default variant.
    """
    branch = [t for t in traces if t.trace_id in divergence.branch_trace_ids]
    trunk = [t for t in traces if t.trace_id not in divergence.branch_trace_ids]
    return trunk, branch


def _connected_chains(
    edges: list[DirectedEdge],
    graph: SupportGraph,
) -> list[list[DirectedEdge]]:
    edge_set = set(edges)
    adjacency: dict[DirectedEdge, set[DirectedEdge]] = {e: set() for e in edges}
    for u, v in graph.arcs:
        if u in edge_set and v in edge_set:
            adjacency[u].add(v)
            adjacency[v].add(u)

    seen: set[DirectedEdge] = set()
    chains: list[list[DirectedEdge]] = []
    for edge in edges:
        if edge in seen:
            continue
        stack = [edge]
        component: list[DirectedEdge] = []
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            component.append(current)
            stack.extend(adjacency[current] - seen)
        chains.append(component)
    return chains
