"""Pluggable consensus strategies.

routebuilder's native algorithm is the directed-edge **support graph**
(graph.py + consensus.py). For comparison — and because it sometimes
assembles a connected route where the support graph fragments at
terminus loops — the legacy geodata **edge-overlap** strategy is
exposed here as an alternative, wrapped so it returns the same
``ConsensusRoute`` shape.

Both take one ramal cluster's matched traces and return a list of
``ConsensusRoute``. The engine swaps between them per the ``strategy``
argument; direction splitting, ramal clustering and validation stay
shared around them.
"""

from __future__ import annotations

import uuid

from .config import ConsensusConfig
from .types import ConsensusEdge, ConsensusRoute, DirectedEdge, MatchedTrace

STRATEGIES = ("support_graph", "edge_overlap")


def reconstruct_edge_overlap(
    traces: list[MatchedTrace],
    *,
    config: ConsensusConfig | None = None,
    ramal_label: str = "main",
    direction_group: int = 0,
) -> tuple[list[ConsensusRoute], dict]:
    """Run geodata's edge-sequence-overlap assembly on a cluster.

    The legacy strategy returns a GeoJSON polyline; we re-match it once
    through Valhalla to recover a clean directed-edge sequence, so the
    output is a full ConsensusRoute (geometry + edges) compatible with
    voting and persistence.
    """
    from geodata.reconstruction import (
        EdgeSequenceOverlapAssemblyPreviewStrategy,
        MatchedEdgeRef,
        ReconstructionPoint,
        ReconstructionTrace,
    )

    config = config or ConsensusConfig()
    diagnostics: dict = {"strategy": "edge_overlap", "trace_count": len(traces)}
    if not traces:
        return [], diagnostics

    rec_traces = [
        ReconstructionTrace(
            trace_id=t.trace_id,
            points=[
                ReconstructionPoint(longitude=lon, latitude=lat, point_index=i)
                for i, (lon, lat) in enumerate(t.matched_polyline)
            ],
            matched_edges=[
                MatchedEdgeRef(valhalla_edge_id=e.edge_id, forward=e.forward, sequence=i)
                for i, e in enumerate(t.edges)
            ],
        )
        for t in traces
        if len(t.matched_polyline) >= 2
    ]
    if not rec_traces:
        diagnostics["failure"] = "no_usable_traces"
        return [], diagnostics

    strategy = EdgeSequenceOverlapAssemblyPreviewStrategy()
    try:
        # recover_geometry=True lets the legacy strategy turn its
        # consensus edge sequence into a road-following polyline (it
        # can't otherwise). We then re-match that polyline below to
        # recover a clean directed-edge sequence for voting.
        result = strategy.reconstruct(uuid.uuid4(), rec_traces, params={
            "recover_geometry": True,
        })
    except (ValueError, RuntimeError) as exc:
        diagnostics["failure"] = f"strategy_error: {exc}"
        return [], diagnostics

    from geodata.evaluate import extract_linestring_coordinates

    lines = extract_linestring_coordinates(result.geojson)
    diagnostics.update({
        "fragments": len(lines),
        "legacy_diagnostics": {
            k: result.diagnostics.get(k)
            for k in ("usable_trace_count", "fragment_count", "consensus_edge_count")
            if k in result.diagnostics
        },
    })

    routes: list[ConsensusRoute] = []
    fragment_count = len(lines)
    for index, line in enumerate(lines):
        geometry = [(c[0], c[1]) for c in line if len(c) >= 2]
        if len(geometry) < 2:
            continue
        edges = _recover_edges(geometry, config)
        label = ramal_label if fragment_count == 1 else f"{ramal_label}.{index + 1}"
        routes.append(ConsensusRoute(
            ramal_label=label,
            direction_group=direction_group,
            edges=edges,
            geometry=geometry,
            trace_count=len(traces),
            trace_ids=[t.trace_id for t in traces],
            diagnostics={"strategy": "edge_overlap", "fragment_index": index,
                         "fragment_count": fragment_count},
        ))
    return routes, diagnostics


def _recover_edges(geometry: list, config: ConsensusConfig) -> list[ConsensusEdge]:
    """Re-match the assembled polyline to a directed-edge sequence."""
    from geodata.match import trace_match

    try:
        output = trace_match(
            [{"lat": lat, "lon": lon} for lon, lat in geometry],
            costing="bus", search_radius=20, gps_accuracy=8,
        )
    except Exception:  # noqa: BLE001 - matching is best-effort here
        return []

    shape = output.shape_coords  # (lat, lon)
    edges: list[ConsensusEdge] = []
    for e in output.edges:
        de = DirectedEdge(int(e["id"]), bool(e.get("forward", True)))
        if edges and edges[-1].edge == de:
            continue
        begin, end = e.get("begin_shape_index"), e.get("end_shape_index")
        geom = (
            [(lon, lat) for lat, lon in shape[begin : end + 1]]
            if begin is not None and end is not None and end >= begin
            else []
        )
        edges.append(ConsensusEdge(edge=de, geometry=geom, confidence=1.0))
    return edges
