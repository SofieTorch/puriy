"""Directed-edge support graph: the evidence structure for consensus.

Nodes are DirectedEdges observed in any trace of a cluster; arcs are
observed consecutive transitions. Weights count *distinct traces*, not
occurrences. Support is then localized: an edge's denominator is only
the traces that actually pass near it, so partial traces (boarding or
alighting mid-route) don't unfairly dilute edges near the termini.

Pruning on localized support is what kills the spurious cross-street
problem: a cross-street edge produced by one trace's GPS jump has
weight 1 and support ~1/N near the trunk, and dies. A genuine branch
used by half the traces survives via the support fraction.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .config import ConsensusConfig
from .types import DirectedEdge, LonLat, MatchedTrace

ME_PER_DEG_LAT = 111_320.0


def _project_m(p: LonLat, ref_lat: float) -> tuple[float, float]:
    """Equirectangular lon/lat → local meters. Fine at city scale."""
    return (
        p[0] * ME_PER_DEG_LAT * math.cos(math.radians(ref_lat)),
        p[1] * ME_PER_DEG_LAT,
    )


@dataclass
class SupportGraph:
    nodes: dict[DirectedEdge, set[str]] = field(default_factory=dict)  # edge -> supporting trace ids
    arcs: dict[tuple[DirectedEdge, DirectedEdge], set[str]] = field(default_factory=dict)
    geometries: dict[DirectedEdge, list[LonLat]] = field(default_factory=dict)
    support_frac: dict[DirectedEdge, float] = field(default_factory=dict)
    coverage: dict[DirectedEdge, int] = field(default_factory=dict)

    def node_weight(self, edge: DirectedEdge) -> int:
        return len(self.nodes.get(edge, ()))

    def arc_support(self, u: DirectedEdge, v: DirectedEdge) -> int:
        return len(self.arcs.get((u, v), ()))

    def successors(self, u: DirectedEdge) -> list[DirectedEdge]:
        return [v for (a, v) in self.arcs if a == u]


def build_support_graph(traces: list[MatchedTrace]) -> SupportGraph:
    graph = SupportGraph()
    for trace in traces:
        for edge in trace.edges:
            graph.nodes.setdefault(edge, set()).add(trace.trace_id)
            geometry = trace.edge_geometries.get(edge)
            if geometry and len(geometry) > len(graph.geometries.get(edge, ())):
                graph.geometries[edge] = geometry
        for u, v in zip(trace.edges, trace.edges[1:]):
            graph.arcs.setdefault((u, v), set()).add(trace.trace_id)
    return graph


def edge_midpoint(graph: SupportGraph, edge: DirectedEdge) -> LonLat | None:
    geometry = graph.geometries.get(edge)
    if not geometry:
        return None
    return geometry[len(geometry) // 2]


def compute_localized_support(
    graph: SupportGraph,
    traces: list[MatchedTrace],
    config: ConsensusConfig | None = None,
) -> None:
    """Fill graph.coverage and graph.support_frac in place.

    coverage(e) = number of traces whose matched polyline passes within
    `coverage_radius_m` of e's midpoint. support_frac(e) =
    node_weight(e) / max(coverage(e), 1).
    """
    config = config or ConsensusConfig()
    radius = config.coverage_radius_m
    if not graph.nodes:
        return

    ref_lat = next(iter(graph.geometries.values()), [(0.0, 0.0)])[0][1]
    cell = radius

    # One occupancy grid per trace: cell -> present.
    trace_grids: dict[str, set[tuple[int, int]]] = {}
    for trace in traces:
        cells: set[tuple[int, int]] = set()
        for p in trace.matched_polyline:
            x, y = _project_m(p, ref_lat)
            cells.add((int(x // cell), int(y // cell)))
        trace_grids[trace.trace_id] = cells

    for edge in graph.nodes:
        midpoint = edge_midpoint(graph, edge)
        if midpoint is None:
            # No geometry (shouldn't happen for matched edges): fall
            # back to global fraction so the edge isn't unfairly kept.
            graph.coverage[edge] = len(traces)
            graph.support_frac[edge] = graph.node_weight(edge) / max(len(traces), 1)
            continue
        x, y = _project_m(midpoint, ref_lat)
        cx, cy = int(x // cell), int(y // cell)
        nearby = {(cx + dx, cy + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)}
        covering = sum(1 for cells in trace_grids.values() if cells & nearby)
        graph.coverage[edge] = covering
        graph.support_frac[edge] = graph.node_weight(edge) / max(covering, 1)


def prune_graph(
    graph: SupportGraph,
    config: ConsensusConfig | None = None,
) -> tuple[SupportGraph, dict]:
    """Drop weakly-supported nodes (and their arcs).

    A node survives if node_weight >= min_support_abs OR
    support_frac >= support_frac_min — an edge seen by only 1 of 6
    traces dies, but an edge seen by the only 1 trace that covers that
    part of the route survives.
    """
    config = config or ConsensusConfig()
    pruned = SupportGraph()
    dropped: list[dict] = []

    for edge, supporters in graph.nodes.items():
        weight = len(supporters)
        frac = graph.support_frac.get(edge, 1.0)
        if weight >= config.min_support_abs or frac >= config.support_frac_min:
            pruned.nodes[edge] = set(supporters)
            if edge in graph.geometries:
                pruned.geometries[edge] = graph.geometries[edge]
            pruned.support_frac[edge] = frac
            pruned.coverage[edge] = graph.coverage.get(edge, 0)
        else:
            dropped.append({
                "edge_id": edge.edge_id,
                "forward": edge.forward,
                "weight": weight,
                "support_frac": round(frac, 3),
            })

    for (u, v), supporters in graph.arcs.items():
        if u in pruned.nodes and v in pruned.nodes:
            pruned.arcs[(u, v)] = set(supporters)

    diagnostics = {"pruned_edges": dropped, "pruned_count": len(dropped)}
    return pruned, diagnostics
