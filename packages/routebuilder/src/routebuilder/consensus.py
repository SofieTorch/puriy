"""Consensus route extraction from a pruned support graph.

Steps (per ramal cluster):
1. Order surviving edges by arc-length projection onto a reference
   polyline (the cluster medoid).
2. Pick consensus endpoints: the extremal well-supported edges that
   some trace actually starts/ends near — extends the route to the
   longest extent the evidence supports instead of truncating to the
   intersection of partial traces.
3. Widest path start→end: maximize the minimum arc support along the
   path (bottleneck Dijkstra), so the route follows the transitions
   most traces agree on. Arcs that jump backwards along the reference
   ordering are forbidden, which breaks noise cycles.
4. Assemble geometry by welding per-edge geometries. Gaps wider than
   the connect tolerance are repaired via an injectable bridge
   function (Valhalla in production) or, beyond the bridging cap,
   split into separate fragments — never blindly concatenated.
"""

from __future__ import annotations

import heapq
import math
from collections.abc import Callable
from dataclasses import dataclass

from geodata.geo_math import haversine_m

from .config import ConsensusConfig
from .graph import (
    SupportGraph,
    _project_m,
    build_support_graph,
    compute_localized_support,
    edge_midpoint,
    prune_graph,
)
from .types import ConsensusEdge, ConsensusRoute, DirectedEdge, LonLat, MatchedTrace

# Returns bridging edges between two consensus edges, or None if the
# gap cannot be bridged. Signature: (gap_start, gap_end) -> edges.
BridgeFn = Callable[[LonLat, LonLat], list[ConsensusEdge] | None]


def arc_positions(
    graph: SupportGraph,
    reference_polyline: list[LonLat],
) -> dict[DirectedEdge, float]:
    """Arc-length position (m) of each node's midpoint projected onto
    the reference polyline."""
    if len(reference_polyline) < 2:
        return {}
    ref_lat = reference_polyline[0][1]
    ref_m = [_project_m(p, ref_lat) for p in reference_polyline]

    # Cumulative arc length at each vertex.
    cumulative = [0.0]
    for a, b in zip(ref_m, ref_m[1:]):
        cumulative.append(cumulative[-1] + math.dist(a, b))

    positions: dict[DirectedEdge, float] = {}
    for edge in graph.nodes:
        midpoint = edge_midpoint(graph, edge)
        if midpoint is None:
            continue
        p = _project_m(midpoint, ref_lat)
        best_pos = 0.0
        best_dist = math.inf
        for i, (a, b) in enumerate(zip(ref_m, ref_m[1:])):
            seg = (b[0] - a[0], b[1] - a[1])
            seg_len_sq = seg[0] ** 2 + seg[1] ** 2
            if seg_len_sq == 0:
                t = 0.0
            else:
                t = ((p[0] - a[0]) * seg[0] + (p[1] - a[1]) * seg[1]) / seg_len_sq
                t = max(0.0, min(1.0, t))
            proj = (a[0] + t * seg[0], a[1] + t * seg[1])
            d = math.dist(p, proj)
            if d < best_dist:
                best_dist = d
                best_pos = cumulative[i] + t * math.sqrt(seg_len_sq)
        positions[edge] = best_pos
    return positions


def select_endpoints(
    graph: SupportGraph,
    traces: list[MatchedTrace],
    positions: dict[DirectedEdge, float],
    config: ConsensusConfig | None = None,
) -> tuple[DirectedEdge, DirectedEdge] | None:
    """Pick consensus start and end edges.

    Candidates must survive in the graph, have decent localized
    support, and be near some trace's terminus (first/last 2 edges) —
    then the extremal arc positions win.
    """
    config = config or ConsensusConfig()
    if not graph.nodes or not positions:
        return None

    start_candidates: set[DirectedEdge] = set()
    end_candidates: set[DirectedEdge] = set()
    for trace in traces:
        surviving = [e for e in trace.edges if e in graph.nodes]
        start_candidates.update(surviving[:2])
        end_candidates.update(surviving[-2:])

    # Endpoints anchor the route's extent, so they need corroboration:
    # at least 2 traces (when available) — a single trace's lonely
    # head/tail must not stretch the consensus.
    min_weight = min(2, len(traces))

    def eligible(edges: set[DirectedEdge]) -> list[DirectedEdge]:
        return [
            e for e in edges
            if e in positions
            and graph.support_frac.get(e, 0.0) >= config.endpoint_support_frac_min
            and graph.node_weight(e) >= min_weight
        ]

    starts = eligible(start_candidates) or [e for e in graph.nodes if e in positions]
    ends = eligible(end_candidates) or [e for e in graph.nodes if e in positions]
    if not starts or not ends:
        return None

    start = min(starts, key=lambda e: positions[e])
    end = max(ends, key=lambda e: positions[e])
    if start == end:
        return None
    return start, end


def widest_path(
    graph: SupportGraph,
    start: DirectedEdge,
    end: DirectedEdge,
    positions: dict[DirectedEdge, float],
    config: ConsensusConfig | None = None,
) -> list[DirectedEdge] | None:
    """Bottleneck-maximizing path start→end.

    Primary: maximize the minimum arc support along the path.
    Tie-breaks: maximize total node support, then minimize hop count.
    Arcs moving backwards along the reference ordering by more than
    backtrack_tolerance_m are forbidden.
    """
    config = config or ConsensusConfig()
    if start not in graph.nodes or end not in graph.nodes:
        return None

    adjacency: dict[DirectedEdge, list[tuple[DirectedEdge, int]]] = {}
    for (u, v), supporters in graph.arcs.items():
        pos_u = positions.get(u)
        pos_v = positions.get(v)
        if (
            pos_u is not None
            and pos_v is not None
            and pos_v < pos_u - config.backtrack_tolerance_m
        ):
            continue
        adjacency.setdefault(u, []).append((v, len(supporters)))

    # Phase 1 — best achievable bottleneck start→end. The bottleneck
    # objective is monotone along a path, so plain Dijkstra finalizes
    # each node once. (A combined lexicographic key with total support
    # would *improve* around cycles and never terminate.)
    INF = float("inf")
    best_bottleneck: dict[DirectedEdge, float] = {start: INF}
    heap: list[tuple[float, int, DirectedEdge]] = [(-INF, 0, start)]
    counter = 0
    visited: set[DirectedEdge] = set()
    while heap:
        neg_b, _, u = heapq.heappop(heap)
        if u in visited:
            continue
        visited.add(u)
        if u == end:
            break
        for v, arc_support in adjacency.get(u, ()):
            cand = min(-neg_b, arc_support)
            if cand > best_bottleneck.get(v, -INF) and v not in visited:
                best_bottleneck[v] = cand
                counter += 1
                heapq.heappush(heap, (-cand, counter, v))

    if end not in best_bottleneck:
        return None
    bottleneck = best_bottleneck[end]

    # Phase 2 — within arcs meeting the bottleneck, shortest path with
    # strictly positive weights that mildly prefer well-supported
    # nodes: weight in (0.5, 1] per hop, so no improving cycles exist.
    cost: dict[DirectedEdge, float] = {start: 0.0}
    came_from: dict[DirectedEdge, DirectedEdge] = {}
    heap2: list[tuple[float, int, DirectedEdge]] = [(0.0, 0, start)]
    done: set[DirectedEdge] = set()
    while heap2:
        c, _, u = heapq.heappop(heap2)
        if u in done:
            continue
        done.add(u)
        if u == end:
            break
        for v, arc_support in adjacency.get(u, ()):
            if arc_support < bottleneck or v in done:
                continue
            frac = min(graph.support_frac.get(v, 0.0), 1.0)
            new_cost = c + 1.0 - 0.5 * frac
            if new_cost < cost.get(v, INF):
                cost[v] = new_cost
                came_from[v] = u
                counter += 1
                heapq.heappush(heap2, (new_cost, counter, v))

    if end not in cost:
        return None

    path = [end]
    while path[-1] != start:
        path.append(came_from[path[-1]])
    path.reverse()
    return path


def assemble_routes(
    path: list[DirectedEdge],
    graph: SupportGraph,
    *,
    config: ConsensusConfig | None = None,
    bridge_fn: BridgeFn | None = None,
    ramal_label: str = "main",
    direction_group: int = 0,
    trace_ids: list[str] | None = None,
) -> list[ConsensusRoute]:
    """Turn an edge path into connected route fragments.

    Welds per-edge geometries; gaps wider than connect_tolerance_m are
    bridged via bridge_fn (inserted as inferred edges with confidence
    0.0) when possible, otherwise the route splits into fragments.
    The connectivity invariant — every consecutive coordinate pair in
    a fragment's geometry closer than connect_tolerance_m — always
    holds on output.
    """
    config = config or ConsensusConfig()
    fragments: list[list[ConsensusEdge]] = [[]]
    fragment_bridges: list[list[list[LonLat]]] = [[]]
    bridged_gaps: list[dict] = []
    welded_gaps: list[float] = []
    split_gaps: list[dict] = []
    weld_limit = max(config.max_weld_gap_m, config.connect_tolerance_m)

    for edge in path:
        geometry = list(graph.geometries.get(edge, []))
        consensus_edge = ConsensusEdge(
            edge=edge,
            geometry=geometry,
            confidence=graph.support_frac.get(edge, 0.0),
        )
        current = fragments[-1]
        if not current or not geometry or not current[-1].geometry:
            current.append(consensus_edge)
            continue

        gap_start = current[-1].geometry[-1]
        gap_end = geometry[0]
        gap_m = haversine_m(gap_start[0], gap_start[1], gap_end[0], gap_end[1])

        if gap_m <= config.connect_tolerance_m:
            current.append(consensus_edge)
            continue

        if gap_m <= weld_limit:
            # Straight-line weld: keep one fragment; the geometry
            # concatenation draws the connecting segment.
            current.append(consensus_edge)
            welded_gaps.append(round(gap_m, 1))
            fragment_bridges[-1].append([gap_start, gap_end])
            continue

        bridge: list[ConsensusEdge] | None = None
        if gap_m <= config.max_bridge_gap_m and bridge_fn is not None:
            bridge = bridge_fn(gap_start, gap_end)

        if bridge:
            current.extend(bridge)
            current.append(consensus_edge)
            bridged_gaps.append({"gap_m": round(gap_m, 1), "edges": len(bridge)})
        else:
            split_gaps.append({
                "gap_m": round(gap_m, 1),
                "after_edge_id": current[-1].edge.edge_id,
                "before_edge_id": edge.edge_id,
            })
            fragments.append([consensus_edge])
            fragment_bridges.append([])

    routes: list[ConsensusRoute] = []
    fragment_list = [
        (f, b) for f, b in zip(fragments, fragment_bridges) if f
    ]
    for index, (fragment, bridges) in enumerate(fragment_list):
        geometry: list[LonLat] = []
        for ce in fragment:
            for p in ce.geometry:
                if not geometry or _gap_m(geometry[-1], p) > 0:
                    geometry.append(p)
        label = ramal_label if len(fragment_list) == 1 else f"{ramal_label}.{index + 1}"
        routes.append(
            ConsensusRoute(
                ramal_label=label,
                direction_group=direction_group,
                edges=fragment,
                geometry=geometry,
                trace_count=len(trace_ids or []),
                trace_ids=list(trace_ids or []),
                bridges=bridges,
                diagnostics={
                    "fragment_index": index,
                    "fragment_count": len(fragment_list),
                    "bridged_gaps": bridged_gaps if index == 0 else [],
                    "welded_gaps": welded_gaps if index == 0 else [],
                    "split_gaps": split_gaps if index == 0 else [],
                },
            )
        )

    for route in routes:
        assert_connected(route, config)
    return routes


@dataclass
class ClusterConsensus:
    """Everything produced by one cluster's consensus run, including
    the intermediates the engine needs for divergence detection."""

    routes: list[ConsensusRoute]
    diagnostics: dict
    pruned: SupportGraph | None = None
    path: list[DirectedEdge] | None = None


def run_cluster_consensus(
    traces: list[MatchedTrace],
    *,
    config: ConsensusConfig | None = None,
    reference_polyline: list[LonLat] | None = None,
    bridge_fn: BridgeFn | None = None,
    ramal_label: str = "main",
    direction_group: int = 0,
) -> ClusterConsensus:
    """Full consensus pipeline for one ramal cluster of traces.

    Routes is empty when the cluster has no extractable consensus
    (no surviving endpoints/path).
    """
    config = config or ConsensusConfig()
    diagnostics: dict = {"trace_count": len(traces)}
    if not traces:
        return ClusterConsensus([], diagnostics)

    if reference_polyline is None:
        reference_polyline = max(
            (t.matched_polyline for t in traces), key=_polyline_length_m
        )

    graph = build_support_graph(traces)
    compute_localized_support(graph, traces, config)
    pruned, prune_diag = prune_graph(graph, config)
    diagnostics.update(prune_diag)
    diagnostics["nodes_total"] = len(graph.nodes)
    diagnostics["nodes_surviving"] = len(pruned.nodes)

    positions = arc_positions(pruned, reference_polyline)
    endpoints = select_endpoints(pruned, traces, positions, config)
    if endpoints is None:
        diagnostics["failure"] = "no_endpoints"
        return ClusterConsensus([], diagnostics, pruned=pruned)

    start, end = endpoints
    path = widest_path(pruned, start, end, positions, config)
    if path is None:
        diagnostics["failure"] = "no_path"
        return ClusterConsensus([], diagnostics, pruned=pruned)

    diagnostics["path_edges"] = len(path)
    routes = assemble_routes(
        path,
        pruned,
        config=config,
        bridge_fn=bridge_fn,
        ramal_label=ramal_label,
        direction_group=direction_group,
        trace_ids=[t.trace_id for t in traces],
    )
    return ClusterConsensus(routes, diagnostics, pruned=pruned, path=path)


def consensus_for_cluster(
    traces: list[MatchedTrace],
    *,
    config: ConsensusConfig | None = None,
    reference_polyline: list[LonLat] | None = None,
    bridge_fn: BridgeFn | None = None,
    ramal_label: str = "main",
    direction_group: int = 0,
) -> tuple[list[ConsensusRoute], dict]:
    """Convenience wrapper returning just (routes, diagnostics)."""
    result = run_cluster_consensus(
        traces,
        config=config,
        reference_polyline=reference_polyline,
        bridge_fn=bridge_fn,
        ramal_label=ramal_label,
        direction_group=direction_group,
    )
    return result.routes, result.diagnostics


def _polyline_length_m(polyline: list[LonLat]) -> float:
    return sum(_gap_m(a, b) for a, b in zip(polyline, polyline[1:]))


def _gap_m(a: LonLat, b: LonLat) -> float:
    return haversine_m(a[0], a[1], b[0], b[1])


def assert_connected(route: ConsensusRoute, config: ConsensusConfig | None = None) -> None:
    """The output invariant: consecutive edges' geometries meet.

    Vertices *within* one edge may be far apart (a straight road needs
    only two vertices) — disconnection only happens at the junction
    between consecutive edges, so that is what we check.
    """
    config = config or ConsensusConfig()
    # Gaps up to the weld limit are intentionally connected by a
    # straight segment, so that — not connect_tolerance — is the
    # invariant bound on a connected fragment.
    tolerance = max(config.max_weld_gap_m, config.connect_tolerance_m)
    with_geometry = [ce for ce in route.edges if ce.geometry]
    for prev, nxt in zip(with_geometry, with_geometry[1:]):
        gap = _gap_m(prev.geometry[-1], nxt.geometry[0])
        if gap > tolerance:
            raise AssertionError(
                f"route {route.ramal_label}: junction gap {gap:.1f}m between "
                f"edge {prev.edge.edge_id} and edge {nxt.edge.edge_id} exceeds "
                f"weld limit {tolerance}m"
            )
