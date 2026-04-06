"""Segment-level voting consensus reconstruction strategy."""

from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from math import ceil
from typing import Any
from uuid import UUID

from ...match import trace_match
from ..base import ReconstructionResult, ReconstructionTrace


def _collapse_consecutive_pairs(
    edge_ids: list[str],
    geometries: list[list[list[float]]],
) -> tuple[list[str], list[list[list[float]]]]:
    collapsed_ids: list[str] = []
    collapsed_geometries: list[list[list[float]]] = []
    for edge_id, geometry in zip(edge_ids, geometries, strict=False):
        if collapsed_ids and collapsed_ids[-1] == edge_id:
            continue
        collapsed_ids.append(edge_id)
        collapsed_geometries.append(geometry)
    return collapsed_ids, collapsed_geometries


def _edge_geometry(edge: dict[str, Any], shape_coords: list[tuple[float, float]]) -> list[list[float]]:
    if not shape_coords:
        return []

    start = max(0, int(edge.get("begin_shape_index", 0)))
    end = min(len(shape_coords) - 1, int(edge.get("end_shape_index", start)))
    if end < start:
        start, end = end, start

    segment = shape_coords[start : end + 1]
    if len(segment) == 1:
        segment = segment * 2
    return [[lon, lat] for lat, lon in segment]


def _trace_points_payload(trace: ReconstructionTrace) -> list[dict[str, float | int]]:
    payload: list[dict[str, float | int]] = []
    for point in trace.points:
        row: dict[str, float | int] = {
            "lat": point.latitude,
            "lon": point.longitude,
        }
        if point.timestamp is not None:
            row["time"] = int(point.timestamp.timestamp())
        payload.append(row)
    return payload


def _canonicalize_trace(
    edge_ids: list[str],
    geometries: list[list[list[float]]],
) -> tuple[list[str], list[list[list[float]]], bool]:
    if not edge_ids:
        return [], [], False

    reversed_ids = list(reversed(edge_ids))
    if tuple(reversed_ids) < tuple(edge_ids):
        return (
            reversed_ids,
            [list(reversed(geometry)) for geometry in reversed(geometries)],
            True,
        )
    return edge_ids, geometries, False


def _select_representative_geometry(geometries: list[list[list[float]]]) -> list[list[float]]:
    if not geometries:
        return []
    return max(geometries, key=lambda coords: (len(coords), coords))


def _support_threshold(raw_value: Any, matched_trace_count: int, *, default_fraction: float) -> int:
    if isinstance(raw_value, (int, float)) and float(raw_value) > 0:
        return max(1, int(raw_value))
    return max(1, ceil(matched_trace_count * default_fraction))


def _path_score(
    path: tuple[str, ...],
    node_weights: Counter[str],
    pair_weights: Counter[tuple[str, str]],
    transition_weight: float,
) -> float:
    score = sum(node_weights[node_id] for node_id in path)
    score += transition_weight * sum(
        pair_weights[(path[idx], path[idx + 1])]
        for idx in range(len(path) - 1)
    )
    return float(score)


def _consensus_path(
    node_weights: Counter[str],
    pair_weights: Counter[tuple[str, str]],
    beam_width: int,
    transition_weight: float,
) -> list[str]:
    if not node_weights:
        return []

    successors: dict[str, list[str]] = defaultdict(list)
    incoming_weight: Counter[str] = Counter()
    outgoing_weight: Counter[str] = Counter()
    for (source, target), weight in pair_weights.items():
        successors[source].append(target)
        outgoing_weight[source] += weight
        incoming_weight[target] += weight

    ranked_starts = sorted(
        node_weights,
        key=lambda node_id: (
            node_weights[node_id],
            outgoing_weight[node_id] - incoming_weight[node_id],
            outgoing_weight[node_id],
        ),
        reverse=True,
    )
    beam: list[tuple[float, tuple[str, ...]]] = [
        (
            _path_score((start,), node_weights, pair_weights, transition_weight),
            (start,),
        )
        for start in ranked_starts[: max(1, beam_width)]
    ]
    beam.sort(key=lambda item: item[0], reverse=True)

    best_score, best_path = beam[0]
    max_path_length = len(node_weights)

    while beam:
        next_beam: list[tuple[float, tuple[str, ...]]] = []
        for score, path in beam:
            extended = False
            for successor in sorted(
                successors.get(path[-1], []),
                key=lambda node_id: (pair_weights[(path[-1], node_id)], node_weights[node_id]),
                reverse=True,
            ):
                if successor in path:
                    continue
                candidate = path + (successor,)
                candidate_score = _path_score(
                    candidate,
                    node_weights,
                    pair_weights,
                    transition_weight,
                )
                next_beam.append((candidate_score, candidate))
                extended = True
            if not extended and score > best_score:
                best_score, best_path = score, path

        if not next_beam:
            break

        next_beam.sort(key=lambda item: item[0], reverse=True)
        beam = next_beam[: max(1, beam_width)]
        if beam[0][0] > best_score:
            best_score, best_path = beam[0]
        if len(best_path) >= max_path_length:
            break

    return list(best_path)


def _component_nodes(
    node_weights: Counter[str],
    pair_weights: Counter[tuple[str, str]],
) -> list[set[str]]:
    adjacency: dict[str, set[str]] = {node_id: set() for node_id in node_weights}
    for source, target in pair_weights:
        adjacency.setdefault(source, set()).add(target)
        adjacency.setdefault(target, set()).add(source)

    components: list[set[str]] = []
    seen: set[str] = set()
    for node_id in adjacency:
        if node_id in seen:
            continue
        component: set[str] = set()
        queue = deque([node_id])
        seen.add(node_id)
        while queue:
            current = queue.popleft()
            component.add(current)
            for neighbor in adjacency.get(current, set()):
                if neighbor in seen:
                    continue
                seen.add(neighbor)
                queue.append(neighbor)
        components.append(component)
    return components


def _stitch_geometries(edge_ids: list[str], geometry_by_edge_id: dict[str, list[list[float]]]) -> list[list[float]]:
    stitched: list[list[float]] = []
    for edge_id in edge_ids:
        geometry = geometry_by_edge_id.get(edge_id, [])
        if not geometry:
            continue
        if not stitched:
            stitched.extend(geometry)
            continue
        if stitched[-1] == geometry[0]:
            stitched.extend(geometry[1:])
        else:
            stitched.extend(geometry)
    return stitched


@dataclass(frozen=True)
class SegmentVoteConsensusPreviewStrategy:
    """Consensus route from segment-level support votes over matched traces."""

    key: str = "segment_vote_consensus_preview"
    label: str = "Segment-vote consensus (preview)"

    def default_params(self) -> dict[str, Any]:
        return {
            "costing": "bus",
            "search_radius": 60,
            "gps_accuracy": 20,
            "beam_width": 8,
            "transition_weight": 2.0,
            "min_edge_support": 0,
            "min_pair_support": 0,
            "edge_support_fraction": 0.34,
            "pair_support_fraction": 0.34,
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
        costing = str(effective_params.get("costing", "bus")).strip() or "bus"
        search_radius = int(effective_params.get("search_radius", 60))
        gps_accuracy = int(effective_params.get("gps_accuracy", 20))
        beam_width = max(1, int(effective_params.get("beam_width", 8)))
        transition_weight = float(effective_params.get("transition_weight", 2.0))

        node_support: Counter[str] = Counter()
        pair_support: Counter[tuple[str, str]] = Counter()
        geometry_samples: dict[str, list[list[list[float]]]] = defaultdict(list)
        matched_trace_count = 0
        reversed_trace_count = 0

        for trace in traces:
            if len(trace.points) < 2:
                continue

            result = trace_match(
                _trace_points_payload(trace),
                trace_id=trace.trace_id,
                costing=costing,
                search_radius=search_radius,
                gps_accuracy=gps_accuracy,
            )

            raw_edge_ids = [str(edge["id"]) for edge in result.edges]
            raw_geometries = [_edge_geometry(edge, result.shape_coords) for edge in result.edges]
            edge_ids, edge_geometries = _collapse_consecutive_pairs(raw_edge_ids, raw_geometries)
            edge_ids, edge_geometries, reversed_trace = _canonicalize_trace(edge_ids, edge_geometries)
            if not edge_ids:
                continue

            matched_trace_count += 1
            if reversed_trace:
                reversed_trace_count += 1

            node_support.update(set(edge_ids))
            pair_support.update(set(zip(edge_ids, edge_ids[1:], strict=False)))
            for edge_id, geometry in zip(edge_ids, edge_geometries, strict=False):
                if len(geometry) >= 2:
                    geometry_samples[edge_id].append(geometry)

        if not node_support:
            raise ValueError("Valhalla did not return any matched edges for these traces")

        min_edge_support = _support_threshold(
            effective_params.get("min_edge_support", 0),
            matched_trace_count,
            default_fraction=float(effective_params.get("edge_support_fraction", 0.34)),
        )
        min_pair_support = _support_threshold(
            effective_params.get("min_pair_support", 0),
            matched_trace_count,
            default_fraction=float(effective_params.get("pair_support_fraction", 0.34)),
        )

        filtered_nodes = Counter(
            {edge_id: weight for edge_id, weight in node_support.items() if weight >= min_edge_support}
        )
        filtered_pairs = Counter(
            {
                (source, target): weight
                for (source, target), weight in pair_support.items()
                if weight >= min_pair_support
                and source in filtered_nodes
                and target in filtered_nodes
            }
        )
        if not filtered_nodes:
            raise ValueError("No matched edges survived the support threshold")

        geometry_by_edge_id = {
            edge_id: _select_representative_geometry(samples)
            for edge_id, samples in geometry_samples.items()
            if edge_id in filtered_nodes
        }

        components = _component_nodes(filtered_nodes, filtered_pairs)
        component_features: list[dict[str, Any]] = []
        component_route_count = 0
        total_route_points = 0

        for component_index, component in enumerate(
            sorted(components, key=lambda nodes: sum(filtered_nodes[node] for node in nodes), reverse=True)
        ):
            component_nodes = Counter({node: filtered_nodes[node] for node in component})
            component_pairs = Counter(
                {
                    pair: weight
                    for pair, weight in filtered_pairs.items()
                    if pair[0] in component and pair[1] in component
                }
            )
            consensus_edge_ids = _consensus_path(
                component_nodes,
                component_pairs,
                beam_width=beam_width,
                transition_weight=transition_weight,
            )
            if not consensus_edge_ids:
                consensus_edge_ids = [max(component_nodes, key=component_nodes.get)]

            route_coordinates = _stitch_geometries(consensus_edge_ids, geometry_by_edge_id)
            if len(route_coordinates) < 2:
                continue

            component_route_count += 1
            total_route_points += len(route_coordinates)
            component_features.append(
                {
                    "type": "Feature",
                    "properties": {
                        "strategy": self.label,
                        "line_id": str(line_id),
                        "trace_count": len(traces),
                        "matched_trace_count": matched_trace_count,
                        "component_index": component_index,
                        "component_support": sum(component_nodes.values()),
                        "consensus_edge_count": len(consensus_edge_ids),
                    },
                    "geometry": {
                        "type": "LineString",
                        "coordinates": route_coordinates,
                    },
                }
            )

        if not component_features:
            raise ValueError("Consensus support graph could not be converted into a route")

        geojson = {
            "type": "FeatureCollection",
            "features": component_features,
        }
        diagnostics: dict[str, int | float | str] = {
            "line_id": str(line_id),
            "trace_count": len(traces),
            "matched_trace_count": matched_trace_count,
            "reversed_trace_count": reversed_trace_count,
            "raw_edge_count": len(node_support),
            "raw_pair_count": len(pair_support),
            "supported_edge_count": len(filtered_nodes),
            "supported_pair_count": len(filtered_pairs),
            "component_count": component_route_count,
            "route_points": total_route_points,
            "costing": costing,
            "search_radius": search_radius,
            "gps_accuracy": gps_accuracy,
            "beam_width": beam_width,
            "transition_weight": transition_weight,
            "min_edge_support": min_edge_support,
            "min_pair_support": min_pair_support,
            "consensus_method": "segment_vote_local_support",
        }
        return ReconstructionResult(
            strategy_name=self.label,
            geojson=geojson,
            diagnostics=diagnostics,
        )
