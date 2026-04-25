"""Route-file preview reconstruction strategy."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

from ...geojson import parse_route_from_geojson
from ..base import ReconstructionResult, ReconstructionTrace


@dataclass(frozen=True)
class RouteFilePreviewStrategy:
    """Stub strategy that returns a route from a GeoJSON route file."""

    key: str = "route_file_preview"
    label: str = "Route file preview"

    def default_params(self) -> dict[str, Any]:
        return {"route_file": ""}

    def reconstruct(
        self,
        line_id: UUID,
        traces: list[ReconstructionTrace],
        params: dict[str, Any] | None = None,
    ) -> ReconstructionResult:
        effective_params = self.default_params() | (params or {})
        route_file = str(effective_params.get("route_file", "")).strip()
        if not route_file:
            raise ValueError("Select a route GeoJSON file for preview")

        route_path = Path(route_file).expanduser()
        if not route_path.is_file():
            raise ValueError(f"Route file not found: {route_path}")

        route_coords = parse_route_from_geojson(route_path.read_text(encoding="utf-8"))
        if len(route_coords) < 2:
            raise ValueError("Route file must contain at least 2 coordinates")

        geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {
                        "strategy": self.label,
                        "line_id": str(line_id),
                        "route_file": str(route_path),
                        "trace_count": len(traces),
                    },
                    "geometry": {
                        "type": "LineString",
                        "coordinates": route_coords,
                    },
                }
            ],
        }
        diagnostics: dict[str, int | float | str] = {
            "line_id": str(line_id),
            "trace_count": len(traces),
            "route_points": len(route_coords),
            "route_file": route_path.name,
        }
        return ReconstructionResult(
            strategy_name=self.label,
            geojson=geojson,
            diagnostics=diagnostics,
        )
