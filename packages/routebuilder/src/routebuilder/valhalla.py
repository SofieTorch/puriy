"""Thin Valhalla client for consensus gap bridging.

When the widest path has a geometric gap (e.g. a short connector edge
skipped by sparse matching), we ask Valhalla to route between the gap
endpoints and recover the missing directed edges by map-matching the
returned shape. Bridged edges are marked ``inferred=True`` with
confidence 0.0 so they are visually and statistically distinct from
observed evidence.
"""

from __future__ import annotations

import logging

import httpx
from geodata.geo_math import haversine_m
from geodata.match import VALHALLA_URL, _decode_polyline6, trace_match

from .config import ConsensusConfig
from .consensus import BridgeFn
from .types import ConsensusEdge, DirectedEdge, LonLat

logger = logging.getLogger(__name__)


def route_shape(
    start: LonLat,
    end: LonLat,
    *,
    costing: str = "bus",
    timeout_s: float = 10.0,
) -> list[LonLat] | None:
    """Road-network shape between two points via Valhalla /route."""
    body = {
        "locations": [
            {"lat": start[1], "lon": start[0], "type": "break"},
            {"lat": end[1], "lon": end[0], "type": "break"},
        ],
        "costing": costing,
    }
    try:
        resp = httpx.post(f"{VALHALLA_URL}/route", json=body, timeout=timeout_s)
        resp.raise_for_status()
        data = resp.json()
        legs = data.get("trip", {}).get("legs", [])
        if not legs:
            return None
        coords: list[LonLat] = []
        for leg in legs:
            decoded = _decode_polyline6(leg["shape"])  # (lat, lon)
            coords.extend((lon, lat) for lat, lon in decoded)
        return coords
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        logger.warning("valhalla /route failed for gap bridge: %s", exc)
        return None


def make_bridge_fn(config: ConsensusConfig | None = None, *, costing: str = "bus") -> BridgeFn:
    """Build a BridgeFn that routes across gaps and recovers edges."""
    config = config or ConsensusConfig()

    def bridge(gap_start: LonLat, gap_end: LonLat) -> list[ConsensusEdge] | None:
        shape = route_shape(gap_start, gap_end, costing=costing)
        if not shape or len(shape) < 2:
            return None

        # Sanity cap: a "bridge" several times longer than the gap it
        # crosses means Valhalla routed a detour around one-ways or
        # turn restrictions — drawing road nobody traversed. Better to
        # split the route into honest fragments.
        gap_m = haversine_m(gap_start[0], gap_start[1], gap_end[0], gap_end[1])
        length_m = sum(
            haversine_m(a[0], a[1], b[0], b[1]) for a, b in zip(shape, shape[1:])
        )
        if length_m > max(3.0 * gap_m, 100.0):
            logger.info(
                "bridge rejected: routed %.0fm for a %.0fm gap", length_m, gap_m
            )
            return None

        try:
            output = trace_match(
                [{"lat": lat, "lon": lon} for lon, lat in shape],
                costing=costing,
                search_radius=20,
                gps_accuracy=5,
            )
        except httpx.HTTPError as exc:
            logger.warning("valhalla trace_attributes failed for gap bridge: %s", exc)
            return None

        edges: list[ConsensusEdge] = []
        shape_coords = output.shape_coords  # (lat, lon)
        for edge in output.edges:
            begin = edge.get("begin_shape_index")
            end_idx = edge.get("end_shape_index")
            geometry: list[LonLat] = []
            if begin is not None and end_idx is not None and end_idx >= begin:
                geometry = [(lon, lat) for lat, lon in shape_coords[begin : end_idx + 1]]
            de = DirectedEdge(int(edge["id"]), bool(edge.get("forward", True)))
            if edges and edges[-1].edge == de:
                continue
            edges.append(ConsensusEdge(edge=de, geometry=geometry, confidence=0.0, inferred=True))
        return edges or None

    return bridge
