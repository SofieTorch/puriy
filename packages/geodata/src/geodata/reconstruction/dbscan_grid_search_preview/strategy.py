"""Grid-search DBSCAN preview reconstruction strategy."""

from dataclasses import dataclass
import math
from statistics import mean
from typing import Any
from uuid import UUID

from shapely.geometry import LineString, MultiLineString, Point

from ...cluster import cluster_traces_preview
from ...geo_math import interpolate_route
from .. import _road_grid
from ..base import ReconstructionResult, ReconstructionTrace

EARTH_RADIUS_M = 6_371_000.0


@dataclass(frozen=True)
class _CandidateScore:
    eps_meters: float
    min_samples: int | None
    preview: Any
    overlap_ratio: float
    overlap_error_m: float
    route_support_ratio: float
    route_point_count: int


@dataclass(frozen=True)
class DBSCANGridSearchPreviewStrategy:
    """DBSCAN route reconstruction with parameter search over cleaned traces."""

    key: str = "dbscan_grid_search_preview"
    label: str = "DBSCAN grid-search consensus (preview)"

    def default_params(self) -> dict[str, Any]:
        return {
            "eps_start_meters": 5.0,
            "eps_stop_meters": 40.0,
            "eps_step_meters": 5.0,
            "min_samples_min": 1,
            "min_samples_max": 0,
            "overlap_tolerance_meters": 25.0,
            "route_support_step_meters": 10.0,
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
        eps_candidates = _build_eps_candidates(
            start=float(effective_params.get("eps_start_meters", 5.0)),
            stop=float(effective_params.get("eps_stop_meters", 40.0)),
            step=float(effective_params.get("eps_step_meters", 5.0)),
        )
        min_samples_candidates = _build_min_samples_candidates(
            trace_count=len(traces),
            min_value=int(effective_params.get("min_samples_min", 1)),
            max_value=int(effective_params.get("min_samples_max", 0)),
        )
        overlap_tolerance_meters = float(
            effective_params.get("overlap_tolerance_meters", 25.0)
        )
        route_support_step_meters = float(
            effective_params.get("route_support_step_meters", 10.0)
        )
        snap_costing = str(effective_params.get("snap_costing", "bus")).strip() or "bus"
        snap_search_radius = int(effective_params.get("snap_search_radius", 60))
        snap_gps_accuracy = int(effective_params.get("snap_gps_accuracy", 20))

        best_candidate: _CandidateScore | None = None
        attempted_candidates = 0
        failed_candidates = 0
        last_error: str | None = None

        for eps_meters in eps_candidates:
            for min_samples in min_samples_candidates:
                attempted_candidates += 1
                try:
                    preview = cluster_traces_preview(
                        line_id,
                        traces,
                        eps_meters=eps_meters,
                        min_samples=min_samples,
                    )
                    score = _score_candidate(
                        preview.route_coordinates,
                        traces,
                        overlap_tolerance_meters=overlap_tolerance_meters,
                        route_support_step_meters=route_support_step_meters,
                        eps_meters=eps_meters,
                        min_samples=preview.min_samples,
                        preview=preview,
                    )
                except Exception as exc:
                    failed_candidates += 1
                    last_error = str(exc)
                    continue

                if (
                    best_candidate is None
                    or _candidate_sort_key(score) > _candidate_sort_key(best_candidate)
                ):
                    best_candidate = score

        if best_candidate is None:
            raise ValueError(
                "Grid-search DBSCAN could not produce a valid route. "
                f"Last failure: {last_error or 'unknown error'}"
            )

        snapped_route_coordinates = _road_grid.snap_route_to_road_grid(
            best_candidate.preview.route_coordinates,
            costing=snap_costing,
            search_radius=snap_search_radius,
            gps_accuracy=snap_gps_accuracy,
        )

        diagnostics: dict[str, int | float | str] = {
            "line_id": str(line_id),
            "trace_count": best_candidate.preview.n_traces,
            "point_count": best_candidate.preview.n_points_total,
            "noise_points": best_candidate.preview.n_noise_points,
            "cluster_count": best_candidate.preview.n_clusters,
            "route_points": len(snapped_route_coordinates),
            "raw_route_points": best_candidate.route_point_count,
            "eps_meters": best_candidate.eps_meters,
            "min_samples": best_candidate.preview.min_samples,
            "ordering_method": best_candidate.preview.ordering_method,
            "attempted_candidates": attempted_candidates,
            "failed_candidates": failed_candidates,
            "overlap_ratio": best_candidate.overlap_ratio,
            "overlap_error_m": best_candidate.overlap_error_m,
            "route_support_ratio": best_candidate.route_support_ratio,
            "search_eps_count": len(eps_candidates),
            "search_min_samples_count": len(min_samples_candidates),
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
                            "trace_count": best_candidate.preview.n_traces,
                            "point_count": best_candidate.preview.n_points_total,
                            "cluster_count": best_candidate.preview.n_clusters,
                            "ordering_method": best_candidate.preview.ordering_method,
                            "attempted_candidates": attempted_candidates,
                            "failed_candidates": failed_candidates,
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


def _build_eps_candidates(*, start: float, stop: float, step: float) -> list[float]:
    if step <= 0:
        raise ValueError("eps_step_meters must be > 0")
    lo = min(start, stop)
    hi = max(start, stop)
    candidates: list[float] = []
    current = lo
    while current <= hi + 1e-9:
        candidates.append(round(current, 6))
        current += step
    return candidates or [round(lo, 6)]


def _build_min_samples_candidates(
    *,
    trace_count: int,
    min_value: int,
    max_value: int,
) -> list[int | None]:
    if trace_count <= 0:
        return [None]

    effective_min = max(1, min_value)
    if max_value <= 0:
        effective_max = min(12, trace_count)
    else:
        effective_max = max(effective_min, max_value)

    return list(range(effective_min, effective_max + 1))


def _score_candidate(
    route_coordinates: list[list[float]],
    traces: list[ReconstructionTrace],
    *,
    overlap_tolerance_meters: float,
    route_support_step_meters: float,
    eps_meters: float,
    min_samples: int,
    preview: Any,
) -> _CandidateScore:
    if len(route_coordinates) < 2:
        raise ValueError("Candidate route must contain at least 2 coordinates")

    reference_lon, reference_lat = _reference_lon_lat(route_coordinates, traces)
    route_line = LineString([
        _project_point_to_meters(lon, lat, reference_lon, reference_lat)
        for lon, lat in route_coordinates
    ])
    trace_geometries = _trace_geometries(traces, reference_lon, reference_lat)
    supported_route = _route_support_ratio(
        route_coordinates,
        trace_geometries,
        reference_lon=reference_lon,
        reference_lat=reference_lat,
        tolerance_meters=overlap_tolerance_meters,
        step_meters=route_support_step_meters,
    )

    point_distances: list[float] = []
    overlapping_points = 0
    total_points = 0
    for trace in traces:
        for point in trace.points:
            total_points += 1
            distance = route_line.distance(
                Point(
                    _project_point_to_meters(
                        point.longitude,
                        point.latitude,
                        reference_lon,
                        reference_lat,
                    )
                )
            )
            if distance <= overlap_tolerance_meters:
                overlapping_points += 1
                point_distances.append(float(distance))

    overlap_ratio = (
        overlapping_points / total_points
        if total_points > 0
        else 0.0
    )
    overlap_error_m = mean(point_distances) if point_distances else math.inf

    return _CandidateScore(
        eps_meters=eps_meters,
        min_samples=min_samples,
        preview=preview,
        overlap_ratio=overlap_ratio,
        overlap_error_m=overlap_error_m,
        route_support_ratio=supported_route,
        route_point_count=len(route_coordinates),
    )


def _candidate_sort_key(
    candidate: _CandidateScore,
) -> tuple[float, float, float, float, float]:
    return (
        candidate.route_support_ratio,
        candidate.overlap_ratio,
        -candidate.overlap_error_m,
        -candidate.preview.n_noise_points,
        -candidate.route_point_count,
    )


def _trace_geometries(
    traces: list[ReconstructionTrace],
    reference_lon: float,
    reference_lat: float,
) -> MultiLineString | LineString:
    lines = []
    for trace in traces:
        if len(trace.points) < 2:
            continue
        lines.append(
            LineString(
                [
                    _project_point_to_meters(
                        point.longitude,
                        point.latitude,
                        reference_lon,
                        reference_lat,
                    )
                    for point in trace.points
                ]
            )
        )
    if not lines:
        raise ValueError("At least one trace with 2 points is required for scoring")
    if len(lines) == 1:
        return lines[0]
    return MultiLineString([list(line.coords) for line in lines])


def _route_support_ratio(
    route_coordinates: list[list[float]],
    trace_geometries: MultiLineString | LineString,
    *,
    reference_lon: float,
    reference_lat: float,
    tolerance_meters: float,
    step_meters: float,
) -> float:
    sampled_route = interpolate_route(route_coordinates, max(1.0, step_meters))
    if len(sampled_route) < 2:
        sampled_route = route_coordinates

    supported_points = 0
    for lon, lat in sampled_route:
        point = Point(_project_point_to_meters(lon, lat, reference_lon, reference_lat))
        if trace_geometries.distance(point) <= tolerance_meters:
            supported_points += 1
    return supported_points / len(sampled_route)


def _reference_lon_lat(
    route_coordinates: list[list[float]],
    traces: list[ReconstructionTrace],
) -> tuple[float, float]:
    lons = [coord[0] for coord in route_coordinates]
    lats = [coord[1] for coord in route_coordinates]
    for trace in traces:
        for point in trace.points:
            lons.append(point.longitude)
            lats.append(point.latitude)
    return (sum(lons) / len(lons), sum(lats) / len(lats))


def _project_point_to_meters(
    lon: float,
    lat: float,
    reference_lon: float,
    reference_lat: float,
) -> tuple[float, float]:
    ref_lat_rad = math.radians(reference_lat)
    x = (
        math.radians(lon - reference_lon)
        * EARTH_RADIUS_M
        * max(1e-9, math.cos(ref_lat_rad))
    )
    y = math.radians(lat - reference_lat) * EARTH_RADIUS_M
    return (x, y)
