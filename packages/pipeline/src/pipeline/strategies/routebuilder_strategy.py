"""Routebuilder reconstruction as a self-clustering pipeline strategy.

Wraps the routebuilder engine (top-down divergence discovery + corridor spine +
overlapping membership — the same engine simlab uses) behind geodata's
``ReconstructionStrategy`` interface, adapting DB-loaded traces ↔ routebuilder
types. It lives in ``pipeline`` (not geodata's registry) because routebuilder
depends on geodata, so geodata cannot import it.

Unlike the per-cluster legacy strategies, this one discovers ramales itself
(``clusters_internally = True``): ``reconstruct_routes`` hands it ALL of a line's
traces and accepts one GeoJSON feature per ramal it emits. Per-edge geometry
comes from ``TripMatchedEdge.geometry`` (persisted at clean time), so no Valhalla
call happens here.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from geodata.reconstruction.base import (
    ReconstructionResult,
    ReconstructionTrace,
)
from routebuilder.cleaning import matched_trace_from_valhalla
from routebuilder.config import CleaningConfig, ReconstructionConfig
from routebuilder.engine import reconstruct_from_matched
from routebuilder.types import MatchedTrace


def _to_matched_trace(
    trace: ReconstructionTrace, cleaning: CleaningConfig
) -> MatchedTrace | None:
    """DB ``ReconstructionTrace`` → routebuilder ``MatchedTrace``.

    Uses the persisted raw Valhalla attributes (``Trip.match_attributes``) and
    routebuilder's *own* matcher, so the result — including per-edge corner
    refinement — is identical to what simlab produces, with no Valhalla call.
    Returns None if the trace predates the attribute (legacy) or is empty.
    """
    attrs = trace.match_attributes
    if not attrs:
        return None
    edges = attrs.get("edges")
    shape_coords = attrs.get("shape_coords")
    if not edges or not shape_coords or len(shape_coords) < 2:
        return None
    # shape_coords stored as [[lat, lon], ...]; matcher wants (lat, lon).
    shape = [(float(lat), float(lon)) for lat, lon in shape_coords]
    trace_mt = matched_trace_from_valhalla(
        trace.trace_id,
        edges=edges,
        shape_coords=shape,
        matched_points=attrs.get("matched_points"),
        max_edge_detour_m=cleaning.max_edge_detour_m,
        edge_corner_dev_m=cleaning.edge_corner_dev_m,
    )
    return trace_mt if trace_mt.edges else None


def _routes_to_featurecollection(routes) -> dict:
    """routebuilder ``ConsensusRoute``s → a GeoJSON FeatureCollection, one
    LineString feature per ramal (label in properties)."""
    features = []
    for route in routes:
        coords = [[lon, lat] for lon, lat in route.geometry]
        if len(coords) < 2:
            continue
        features.append({
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": coords},
            "properties": {
                "ramal_label": route.ramal_label,
                "direction_group": route.direction_group,
                "trace_count": route.trace_count,
            },
        })
    return {"type": "FeatureCollection", "features": features}


class RoutebuilderDivergenceStrategy:
    """Top-down divergence reconstruction over a whole line's traces."""

    key = "routebuilder_divergence"
    label = "Routebuilder (top-down divergence)"
    clusters_internally = True

    def default_params(self) -> dict[str, Any]:
        return {"discovery": "divergence", "infer_direction": False}

    def reconstruct(
        self,
        line_id: UUID,
        traces: list[ReconstructionTrace],
        params: dict[str, Any] | None = None,
    ) -> ReconstructionResult:
        params = {**self.default_params(), **(params or {})}
        config = ReconstructionConfig()
        config.ramales.discovery = str(params.get("discovery", "divergence"))

        matched = [
            m for m in (_to_matched_trace(t, config.cleaning) for t in traces)
            if m is not None
        ]

        output = reconstruct_from_matched(
            matched,
            config=config,
            existing_ramales=params.get("existing_ramales") or None,
            infer_direction=bool(params.get("infer_direction", False)),
        )
        return ReconstructionResult(
            strategy_name=self.key,
            geojson=_routes_to_featurecollection(output.routes),
            diagnostics={
                "traces_in": len(traces),
                "traces_matched": len(matched),
                "ramales": len(output.routes),
                "discovery": config.ramales.discovery,
            },
        )
