"""Synthetic fixtures: corridors of fake Valhalla edges with geometry.

The corridor is a straight west→east street at Cochabamba's latitude.
Each edge is ~100m long. Cross-street and branch edges can be grafted
on for consensus tests. No Valhalla needed.
"""

from __future__ import annotations

from routebuilder.types import DirectedEdge, LonLat, MatchedTrace

ORIGIN_LON = -66.157
ORIGIN_LAT = -17.3935
# ~100m steps at this latitude.
LON_STEP = 0.00094
LAT_STEP = 0.0009


def corridor_point(i: int, offset_north: int = 0) -> LonLat:
    """Node i of the corridor, optionally shifted N blocks north."""
    return (ORIGIN_LON + i * LON_STEP, ORIGIN_LAT + offset_north * LAT_STEP)


def edge_geometry(edge_id: int, *, offset_north: int = 0) -> list[LonLat]:
    """Geometry of corridor edge `edge_id`: node (id-1) → node id."""
    return [corridor_point(edge_id - 1, offset_north), corridor_point(edge_id, offset_north)]


def make_trace(
    trace_id: str,
    edge_ids: list[int],
    *,
    forward: bool = True,
    geometries: dict[int, list[LonLat]] | None = None,
    quality: float = 1.0,
    device_id: str | None = None,
) -> MatchedTrace:
    """Build a MatchedTrace from corridor edge ids.

    With forward=False the run is reversed: edge order flipped, each
    DirectedEdge gets forward=False, and geometries are reversed —
    modelling a return trip on the same two-way street.

    `geometries` overrides the default straight-corridor geometry per
    edge id (e.g. for branch edges living off-corridor).
    """
    ids = list(edge_ids) if forward else list(reversed(edge_ids))
    edges: list[DirectedEdge] = []
    geoms: dict[DirectedEdge, list[LonLat]] = {}
    polyline: list[LonLat] = []

    for eid in ids:
        de = DirectedEdge(eid, forward)
        geometry = list((geometries or {}).get(eid) or edge_geometry(eid))
        if not forward:
            geometry = list(reversed(geometry))
        edges.append(de)
        geoms[de] = geometry
        if polyline and polyline[-1] == geometry[0]:
            polyline.extend(geometry[1:])
        else:
            polyline.extend(geometry)

    return MatchedTrace(
        trace_id=trace_id,
        edges=edges,
        edge_geometries=geoms,
        matched_polyline=polyline,
        match_quality=quality,
        device_id=device_id,
    )
