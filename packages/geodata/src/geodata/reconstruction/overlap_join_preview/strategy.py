"""Greedy overlap-join preview reconstruction strategy."""

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from ...geo_math import haversine_m
from ..base import ReconstructionPoint, ReconstructionResult, ReconstructionTrace


def _coords_from_points(points: list[ReconstructionPoint]) -> list[list[float]]:
    return [[point.longitude, point.latitude] for point in points]


def _mean_overlap_distance_m(
    left: list[list[float]],
    right: list[list[float]],
    overlap_len: int,
) -> float:
    if overlap_len <= 0:
        return 0.0
    distances = [
        haversine_m(left[-overlap_len + idx][0], left[-overlap_len + idx][1], right[idx][0], right[idx][1])
        for idx in range(overlap_len)
    ]
    return sum(distances) / len(distances)


def _best_suffix_prefix_overlap(
    left: list[list[float]],
    right: list[list[float]],
    *,
    tolerance_meters: float,
    min_overlap_points: int,
) -> tuple[int, float]:
    max_overlap = min(len(left), len(right))
    best_len = 0
    best_mean_distance = float("inf")
    for overlap_len in range(max_overlap, min_overlap_points - 1, -1):
        valid = True
        distance_sum = 0.0
        for idx in range(overlap_len):
            lon1, lat1 = left[-overlap_len + idx]
            lon2, lat2 = right[idx]
            distance = haversine_m(lon1, lat1, lon2, lat2)
            if distance > tolerance_meters:
                valid = False
                break
            distance_sum += distance
        if valid:
            best_len = overlap_len
            best_mean_distance = distance_sum / overlap_len
            break
    return best_len, best_mean_distance


def _merge_with_overlap(
    left: list[list[float]],
    right: list[list[float]],
    overlap_len: int,
) -> list[list[float]]:
    if overlap_len >= len(right):
        return left[:]
    return left + right[overlap_len:]


def _endpoint_gap_m(left: list[list[float]], right: list[list[float]]) -> float:
    lon1, lat1 = left[-1]
    lon2, lat2 = right[0]
    return haversine_m(lon1, lat1, lon2, lat2)


@dataclass(frozen=True)
class _CandidateMerge:
    trace_index: int
    prepend: bool
    reversed_trace: bool
    overlap_len: int
    mean_distance_m: float
    endpoint_gap_m: float
    merged_coordinates: list[list[float]]


def _choose_best_merge(
    route_coordinates: list[list[float]],
    remaining_traces: list[list[list[float]]],
    *,
    tolerance_meters: float,
    min_overlap_points: int,
) -> _CandidateMerge:
    best_candidate: _CandidateMerge | None = None
    for trace_index, trace_coordinates in enumerate(remaining_traces):
        for reversed_trace, candidate_coordinates in (
            (False, trace_coordinates),
            (True, list(reversed(trace_coordinates))),
        ):
            overlap_len, mean_distance_m = _best_suffix_prefix_overlap(
                route_coordinates,
                candidate_coordinates,
                tolerance_meters=tolerance_meters,
                min_overlap_points=min_overlap_points,
            )
            append_candidate = _CandidateMerge(
                trace_index=trace_index,
                prepend=False,
                reversed_trace=reversed_trace,
                overlap_len=overlap_len,
                mean_distance_m=mean_distance_m,
                endpoint_gap_m=_endpoint_gap_m(route_coordinates, candidate_coordinates),
                merged_coordinates=_merge_with_overlap(
                    route_coordinates,
                    candidate_coordinates,
                    overlap_len,
                ),
            )

            overlap_len, mean_distance_m = _best_suffix_prefix_overlap(
                candidate_coordinates,
                route_coordinates,
                tolerance_meters=tolerance_meters,
                min_overlap_points=min_overlap_points,
            )
            prepend_candidate = _CandidateMerge(
                trace_index=trace_index,
                prepend=True,
                reversed_trace=reversed_trace,
                overlap_len=overlap_len,
                mean_distance_m=mean_distance_m,
                endpoint_gap_m=_endpoint_gap_m(candidate_coordinates, route_coordinates),
                merged_coordinates=_merge_with_overlap(
                    candidate_coordinates,
                    route_coordinates,
                    overlap_len,
                ),
            )

            for candidate in (append_candidate, prepend_candidate):
                if best_candidate is None:
                    best_candidate = candidate
                    continue
                candidate_key = (
                    candidate.overlap_len,
                    -candidate.mean_distance_m,
                    -candidate.endpoint_gap_m,
                    len(candidate.merged_coordinates),
                )
                best_key = (
                    best_candidate.overlap_len,
                    -best_candidate.mean_distance_m,
                    -best_candidate.endpoint_gap_m,
                    len(best_candidate.merged_coordinates),
                )
                if candidate_key > best_key:
                    best_candidate = candidate

    if best_candidate is None:
        raise ValueError("At least one trace is required for reconstruction")
    return best_candidate


def _feature_collection(route_coordinates: list[list[float]]) -> dict[str, Any]:
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {},
                "geometry": {
                    "type": "LineString",
                    "coordinates": route_coordinates,
                },
            }
        ],
    }


@dataclass(frozen=True)
class OverlapJoinPreviewStrategy:
    """Reconstruct a route by greedily merging traces with pairwise overlaps."""

    key: str = "overlap_join_preview"
    label: str = "Pairwise overlap join (preview)"

    def default_params(self) -> dict[str, Any]:
        return {
            "overlap_tolerance_meters": 25.0,
            "min_overlap_points": 1,
        }

    def reconstruct(
        self,
        line_id: UUID,
        traces: list[ReconstructionTrace],
        params: dict[str, Any] | None = None,
    ) -> ReconstructionResult:
        if not traces:
            raise ValueError("At least one trace is required for reconstruction")

        effective_params = self.default_params() | (params or {})
        tolerance_meters = float(effective_params.get("overlap_tolerance_meters", 25.0))
        min_overlap_points = max(1, int(effective_params.get("min_overlap_points", 1)))

        trace_coordinates = [_coords_from_points(trace.points) for trace in traces if trace.points]
        if not trace_coordinates:
            raise ValueError("At least one non-empty trace is required for reconstruction")

        route_coordinates = max(trace_coordinates, key=len)
        remaining_traces = [coords for coords in trace_coordinates if coords is not route_coordinates]

        merges_with_overlap = 0
        merges_without_overlap = 0
        reversed_trace_count = 0
        total_overlap_points = 0

        while remaining_traces:
            candidate = _choose_best_merge(
                route_coordinates,
                remaining_traces,
                tolerance_meters=tolerance_meters,
                min_overlap_points=min_overlap_points,
            )
            if candidate.reversed_trace:
                reversed_trace_count += 1
            if candidate.overlap_len > 0:
                merges_with_overlap += 1
                total_overlap_points += candidate.overlap_len
            else:
                merges_without_overlap += 1
            route_coordinates = candidate.merged_coordinates
            remaining_traces.pop(candidate.trace_index)

        diagnostics: dict[str, int | float | str] = {
            "line_id": str(line_id),
            "trace_count": len(trace_coordinates),
            "route_points": len(route_coordinates),
            "overlap_tolerance_meters": tolerance_meters,
            "min_overlap_points": min_overlap_points,
            "merges_with_overlap": merges_with_overlap,
            "merges_without_overlap": merges_without_overlap,
            "reversed_trace_count": reversed_trace_count,
            "total_overlap_points": total_overlap_points,
            "consensus_method": "greedy_pairwise_overlap_join",
        }
        return ReconstructionResult(
            strategy_name=self.label,
            geojson=_feature_collection(route_coordinates),
            diagnostics=diagnostics,
        )
