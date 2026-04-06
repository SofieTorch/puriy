"""DBSCAN preview reconstruction strategy."""

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from ...cluster import cluster_traces_preview
from .. import _road_grid
from ..base import ReconstructionResult, ReconstructionTrace


@dataclass(frozen=True)
class DBSCANConsensusPreviewStrategy:
    """Notebook-local DBSCAN consensus reconstruction."""

    key: str = "dbscan_consensus_preview"
    label: str = "DBSCAN consensus (preview)"

    def default_params(self) -> dict[str, Any]:
        return {
            "eps_meters": 5.0,
            "min_samples": 2,
            "snap_costing": "bus",
            "snap_search_radius": 60,
            "snap_gps_accuracy": 20,
        }

    def reconstruct(
        self,
        line_id: UUID,
        traces: list[ReconstructionTrace],
        params: dict[str, Any] | None = None,
    ) -> ReconstructionResult:
        effective_params = self.default_params() | (params or {})
        eps_meters = float(effective_params.get("eps_meters", 30.0))
        raw_min_samples = int(effective_params.get("min_samples", 0))
        min_samples = raw_min_samples if raw_min_samples > 0 else None
        snap_costing = str(effective_params.get("snap_costing", "bus")).strip() or "bus"
        snap_search_radius = int(effective_params.get("snap_search_radius", 60))
        snap_gps_accuracy = int(effective_params.get("snap_gps_accuracy", 20))

        preview = cluster_traces_preview(
            line_id,
            traces,
            eps_meters=eps_meters,
            min_samples=min_samples,
        )
        snapped_route_coordinates = _road_grid.snap_route_to_road_grid(
            preview.route_coordinates,
            costing=snap_costing,
            search_radius=snap_search_radius,
            gps_accuracy=snap_gps_accuracy,
        )

        diagnostics: dict[str, int | float | str] = {
            "line_id": str(line_id),
            "trace_count": preview.n_traces,
            "point_count": preview.n_points_total,
            "noise_points": preview.n_noise_points,
            "cluster_count": preview.n_clusters,
            "route_points": len(snapped_route_coordinates),
            "raw_route_points": len(preview.route_coordinates),
            "eps_meters": eps_meters,
            "min_samples": preview.min_samples,
            "ordering_method": preview.ordering_method,
            "snap_costing": snap_costing,
            "snap_search_radius": snap_search_radius,
            "snap_gps_accuracy": snap_gps_accuracy,
        }
        return ReconstructionResult(
            strategy_name=self.label,
            geojson={
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {
                            "strategy": self.label,
                            "line_id": str(line_id),
                            "trace_count": preview.n_traces,
                            "point_count": preview.n_points_total,
                            "cluster_count": preview.n_clusters,
                            "ordering_method": preview.ordering_method,
                            "snap_costing": snap_costing,
                            "snap_search_radius": snap_search_radius,
                            "snap_gps_accuracy": snap_gps_accuracy,
                        },
                        "geometry": {
                            "type": "LineString",
                            "coordinates": snapped_route_coordinates,
                        },
                    }
                ],
            },
            diagnostics=diagnostics,
        )
