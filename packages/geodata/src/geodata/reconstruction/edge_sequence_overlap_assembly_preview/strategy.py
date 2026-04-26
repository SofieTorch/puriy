"""Route reconstruction by assembling overlapping matched-edge sequences."""

from collections import Counter, defaultdict
from dataclasses import dataclass
from difflib import SequenceMatcher
import json
from math import ceil
from typing import Any
from uuid import UUID

from ...match import trace_match
from ..base import MatchedEdgeRef, ReconstructionResult, ReconstructionTrace


@dataclass(frozen=True)
class _TraceObservation:
    trace_id: str
    edge_ids: list[str]


@dataclass(frozen=True)
class _MergeCandidate:
    trace_id: str
    kind: str
    merged_edge_ids: list[str]
    added_edges: int
    matched_edges: int
    score: tuple[float, int, int, int]


@dataclass(frozen=True)
class _ContainmentMatch:
    matched_fraction: float
    best_block: int


@dataclass(frozen=True)
class _AssemblyState:
    contig: list[str]
    remaining: dict[str, list[str]]
    contained_trace_count: int
    approximate_contained_trace_count: int
    merge_steps: int
    approximate_merge_steps: int


@dataclass(frozen=True)
class _AssemblyFragment:
    contig: list[str]
    trace_count: int
    contained_trace_count: int
    approximate_contained_trace_count: int
    merge_steps: int
    approximate_merge_steps: int
    beam_search_used: bool


def _collapse_consecutive(edge_ids: list[str]) -> list[str]:
    collapsed: list[str] = []
    for edge_id in edge_ids:
        if not collapsed or collapsed[-1] != edge_id:
            collapsed.append(edge_id)
    return collapsed


def _edge_key_from_ref(edge: MatchedEdgeRef) -> str:
    direction = "f" if edge.forward else "r"
    return f"{edge.valhalla_edge_id}:{direction}"


def _edge_key_from_match(edge: dict[str, Any]) -> str:
    direction = "f" if edge.get("forward", True) else "r"
    return f"{edge['id']}:{direction}"


def _edge_geometry(
    edge: dict[str, Any],
    shape_coords: list[tuple[float, float]],
) -> list[list[float]]:
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


def _support_threshold(raw_value: Any, trace_count: int, *, default_fraction: float) -> int:
    if isinstance(raw_value, (int, float)) and float(raw_value) > 0:
        return max(1, int(raw_value))
    return max(1, ceil(trace_count * default_fraction))


def _support_counters(sequences: list[list[str]]) -> tuple[Counter[str], Counter[tuple[str, str]]]:
    edge_support: Counter[str] = Counter()
    pair_support: Counter[tuple[str, str]] = Counter()
    for edge_ids in sequences:
        edge_support.update(set(edge_ids))
        pair_support.update(set(zip(edge_ids, edge_ids[1:], strict=False)))
    return edge_support, pair_support


def _remove_internal_singletons(
    edge_ids: list[str],
    edge_support: Counter[str],
    pair_support: Counter[tuple[str, str]],
    *,
    min_edge_support: int,
    min_pair_support: int,
    max_singleton_noise_support: int,
) -> list[str]:
    if len(edge_ids) < 3:
        return edge_ids

    cleaned = list(edge_ids)
    changed = True
    while changed and len(cleaned) >= 3:
        changed = False
        next_cleaned = [cleaned[0]]
        for idx in range(1, len(cleaned) - 1):
            previous_edge = next_cleaned[-1]
            current_edge = cleaned[idx]
            next_edge = cleaned[idx + 1]
            if (
                (
                    edge_support[current_edge] < min_edge_support
                    or edge_support[current_edge] <= max_singleton_noise_support
                )
                and pair_support[(previous_edge, next_edge)] >= min_pair_support
                and pair_support[(previous_edge, current_edge)] < pair_support[(previous_edge, next_edge)]
                and pair_support[(current_edge, next_edge)] < pair_support[(previous_edge, next_edge)]
            ):
                changed = True
                continue
            next_cleaned.append(current_edge)
        next_cleaned.append(cleaned[-1])
        cleaned = next_cleaned
    return cleaned


def _find_subsequence(container: list[str], needle: list[str]) -> int | None:
    if not needle:
        return 0
    max_start = len(container) - len(needle)
    for start in range(max_start + 1):
        if container[start : start + len(needle)] == needle:
            return start
    return None


def _suffix_prefix_overlap(left: list[str], right: list[str], *, min_overlap_edges: int) -> int:
    max_overlap = min(len(left), len(right))
    for overlap_len in range(max_overlap, min_overlap_edges - 1, -1):
        if left[-overlap_len:] == right[:overlap_len]:
            return overlap_len
    return 0


def _sequence_support_score(
    edge_ids: list[str],
    edge_support: Counter[str],
    pair_support: Counter[tuple[str, str]],
) -> int:
    score = sum(edge_support[edge_id] for edge_id in set(edge_ids))
    score += sum(pair_support[pair] for pair in set(zip(edge_ids, edge_ids[1:], strict=False)))
    return score


def _select_unambiguous_candidate(candidates: list[_MergeCandidate]) -> _MergeCandidate | None:
    if not candidates:
        return None

    ranked = sorted(candidates, key=lambda candidate: candidate.score, reverse=True)
    best = ranked[0]
    conflicting = [
        candidate
        for candidate in ranked[1:]
        if candidate.score == best.score and candidate.merged_edge_ids != best.merged_edge_ids
    ]
    if conflicting:
        raise ValueError("Ambiguous overlap candidates prevent a unique route assembly")
    return best


def _seed_score(
    candidate: list[str],
    others: list[list[str]],
    *,
    min_coverage: float,
    min_block_fraction: float,
    min_block_edges: int,
) -> tuple[int, int, float, int]:
    exact_contains = 0
    approximate_contains = 0
    total_coverage = 0.0
    for other in others:
        if other == candidate:
            continue
        if _find_subsequence(candidate, other) is not None:
            exact_contains += 1
        if _approximately_contains(
            candidate,
            other,
            min_coverage=min_coverage,
            min_block_fraction=min_block_fraction,
            min_block_edges=min_block_edges,
        ):
            approximate_contains += 1
        total_coverage += _containment_match(candidate, other).matched_fraction
    return (
        exact_contains,
        approximate_contains,
        total_coverage,
        len(candidate),
    )


def _containment_match(
    container: list[str],
    needle: list[str],
) -> _ContainmentMatch:
    if not container or not needle:
        return _ContainmentMatch(matched_fraction=0.0, best_block=0)
    matcher = SequenceMatcher(a=container, b=needle, autojunk=False)
    blocks = matcher.get_matching_blocks()
    total_matched = sum(block.size for block in blocks)
    best_block = max((block.size for block in blocks), default=0)
    return _ContainmentMatch(
        matched_fraction=(total_matched / len(needle)) if needle else 0.0,
        best_block=best_block,
    )


def _approximately_contains(
    container: list[str],
    needle: list[str],
    *,
    min_coverage: float,
    min_block_fraction: float,
    min_block_edges: int,
) -> bool:
    match = _containment_match(container, needle)
    required_block = min(
        len(needle),
        max(min_block_edges, int(round(len(needle) * min_block_fraction))),
    )
    return (
        match.matched_fraction >= min_coverage
        and match.best_block >= required_block
    )


def _approximate_boundary_merge(
    contig: list[str],
    trace: list[str],
    *,
    min_match_fraction: float,
    min_match_edges: int,
) -> _MergeCandidate | None:
    if not contig or not trace:
        return None

    matcher = SequenceMatcher(a=contig, b=trace, autojunk=False)
    blocks = [block for block in matcher.get_matching_blocks() if block.size > 0]
    if not blocks:
        return None

    matched_edges = sum(block.size for block in blocks)
    matched_fraction = matched_edges / min(len(contig), len(trace))
    if matched_edges < min_match_edges or matched_fraction < min_match_fraction:
        return None

    first_block = blocks[0]
    last_block = blocks[-1]

    left_added = first_block.b if first_block.a == 0 else 0
    right_added = (
        len(trace) - (last_block.b + last_block.size)
        if last_block.a + last_block.size == len(contig)
        else 0
    )

    if left_added == 0 and right_added == 0:
        return None

    merged_edge_ids = trace[:left_added] + contig + trace[len(trace) - right_added :]
    return _MergeCandidate(
        trace_id="",
        kind="approximate",
        merged_edge_ids=merged_edge_ids,
        added_edges=left_added + right_added,
        matched_edges=matched_edges,
        score=(
            matched_fraction,
            matched_edges,
            left_added + right_added,
            len(merged_edge_ids),
        ),
    )


def _drop_resolved_traces(
    contig: list[str],
    remaining: dict[str, list[str]],
    *,
    min_coverage: float,
    min_block_fraction: float,
    min_block_edges: int,
) -> tuple[dict[str, list[str]], int, int]:
    next_remaining = dict(remaining)

    contained_trace_ids = [
        trace_id
        for trace_id, edge_ids in next_remaining.items()
        if _find_subsequence(contig, edge_ids) is not None
    ]
    for trace_id in contained_trace_ids:
        next_remaining.pop(trace_id, None)

    approximate_contained_trace_ids = [
        trace_id
        for trace_id, edge_ids in next_remaining.items()
        if _approximately_contains(
            contig,
            edge_ids,
            min_coverage=min_coverage,
            min_block_fraction=min_block_fraction,
            min_block_edges=min_block_edges,
        )
    ]
    for trace_id in approximate_contained_trace_ids:
        next_remaining.pop(trace_id, None)

    return (
        next_remaining,
        len(contained_trace_ids),
        len(approximate_contained_trace_ids),
    )


def _build_merge_candidates(
    contig: list[str],
    remaining: dict[str, list[str]],
    *,
    edge_support: Counter[str],
    pair_support: Counter[tuple[str, str]],
    min_overlap_edges: int,
    approx_merge_match_fraction: float,
    approx_merge_min_edges: int,
) -> list[_MergeCandidate]:
    merge_candidates: list[_MergeCandidate] = []
    for trace_id, edge_ids in remaining.items():
        prepend_overlap = _suffix_prefix_overlap(
            edge_ids,
            contig,
            min_overlap_edges=min_overlap_edges,
        )
        if prepend_overlap:
            merge_candidates.append(
                _MergeCandidate(
                    trace_id=trace_id,
                    kind="exact",
                    merged_edge_ids=edge_ids[:-prepend_overlap] + contig,
                    added_edges=len(edge_ids) - prepend_overlap,
                    matched_edges=prepend_overlap,
                    score=(
                        1.0,
                        prepend_overlap,
                        len(edge_ids) - prepend_overlap,
                        _sequence_support_score(edge_ids, edge_support, pair_support),
                    ),
                )
            )
        append_overlap = _suffix_prefix_overlap(
            contig,
            edge_ids,
            min_overlap_edges=min_overlap_edges,
        )
        if append_overlap:
            merge_candidates.append(
                _MergeCandidate(
                    trace_id=trace_id,
                    kind="exact",
                    merged_edge_ids=contig + edge_ids[append_overlap:],
                    added_edges=len(edge_ids) - append_overlap,
                    matched_edges=append_overlap,
                    score=(
                        1.0,
                        append_overlap,
                        len(edge_ids) - append_overlap,
                        _sequence_support_score(edge_ids, edge_support, pair_support),
                    ),
                )
            )
        approximate_candidate = _approximate_boundary_merge(
            contig,
            edge_ids,
            min_match_fraction=approx_merge_match_fraction,
            min_match_edges=approx_merge_min_edges,
        )
        if approximate_candidate is not None:
            approximate_match_fraction = approximate_candidate.score[0]
            merge_candidates.append(
                _MergeCandidate(
                    trace_id=trace_id,
                    kind="approximate",
                    merged_edge_ids=approximate_candidate.merged_edge_ids,
                    added_edges=approximate_candidate.added_edges,
                    matched_edges=approximate_candidate.matched_edges,
                    score=(
                        approximate_match_fraction,
                        approximate_candidate.matched_edges,
                        approximate_candidate.added_edges,
                        _sequence_support_score(edge_ids, edge_support, pair_support),
                    ),
                )
            )
    return merge_candidates


def _future_mergeable_count(
    contig: list[str],
    remaining: dict[str, list[str]],
    *,
    min_coverage: float,
    min_block_fraction: float,
    min_block_edges: int,
    min_overlap_edges: int,
    approx_merge_match_fraction: float,
    approx_merge_min_edges: int,
) -> int:
    mergeable = 0
    for edge_ids in remaining.values():
        if _find_subsequence(contig, edge_ids) is not None:
            mergeable += 1
            continue
        if _approximately_contains(
            contig,
            edge_ids,
            min_coverage=min_coverage,
            min_block_fraction=min_block_fraction,
            min_block_edges=min_block_edges,
        ):
            mergeable += 1
            continue
        if _suffix_prefix_overlap(contig, edge_ids, min_overlap_edges=min_overlap_edges):
            mergeable += 1
            continue
        if _suffix_prefix_overlap(edge_ids, contig, min_overlap_edges=min_overlap_edges):
            mergeable += 1
            continue
        if _approximate_boundary_merge(
            contig,
            edge_ids,
            min_match_fraction=approx_merge_match_fraction,
            min_match_edges=approx_merge_min_edges,
        ):
            mergeable += 1
    return mergeable


def _beam_search_assembly(
    initial_state: _AssemblyState,
    *,
    total_trace_count: int,
    min_coverage: float,
    min_block_fraction: float,
    min_block_edges: int,
    min_overlap_edges: int,
    approx_merge_match_fraction: float,
    approx_merge_min_edges: int,
    beam_width: int = 6,
    candidate_width: int = 6,
) -> _AssemblyState | None:
    frontier: list[_AssemblyState] = [initial_state]
    best_completed: _AssemblyState | None = None

    for _ in range(total_trace_count):
        next_frontier: list[tuple[tuple[int, int, int, int, int], _AssemblyState]] = []
        for state in frontier:
            pruned_remaining, contained_count, approximate_contained_count = _drop_resolved_traces(
                state.contig,
                state.remaining,
                min_coverage=min_coverage,
                min_block_fraction=min_block_fraction,
                min_block_edges=min_block_edges,
            )
            pruned_state = _AssemblyState(
                contig=state.contig,
                remaining=pruned_remaining,
                contained_trace_count=state.contained_trace_count + contained_count,
                approximate_contained_trace_count=(
                    state.approximate_contained_trace_count + approximate_contained_count
                ),
                merge_steps=state.merge_steps,
                approximate_merge_steps=state.approximate_merge_steps,
            )
            if not pruned_state.remaining:
                return pruned_state

            edge_support, pair_support = _support_counters(
                [pruned_state.contig, *pruned_state.remaining.values()]
            )
            candidates = sorted(
                _build_merge_candidates(
                    pruned_state.contig,
                    pruned_state.remaining,
                    edge_support=edge_support,
                    pair_support=pair_support,
                    min_overlap_edges=min_overlap_edges,
                    approx_merge_match_fraction=approx_merge_match_fraction,
                    approx_merge_min_edges=approx_merge_min_edges,
                ),
                key=lambda candidate: candidate.score,
                reverse=True,
            )[:candidate_width]

            for candidate in candidates:
                next_remaining = dict(pruned_state.remaining)
                next_remaining.pop(candidate.trace_id, None)
                next_state = _AssemblyState(
                    contig=candidate.merged_edge_ids,
                    remaining=next_remaining,
                    contained_trace_count=pruned_state.contained_trace_count,
                    approximate_contained_trace_count=pruned_state.approximate_contained_trace_count,
                    merge_steps=pruned_state.merge_steps + 1,
                    approximate_merge_steps=(
                        pruned_state.approximate_merge_steps
                        + (1 if candidate.kind == "approximate" else 0)
                    ),
                )
                reachable = _future_mergeable_count(
                    next_state.contig,
                    next_state.remaining,
                    min_coverage=min_coverage,
                    min_block_fraction=min_block_fraction,
                    min_block_edges=min_block_edges,
                    min_overlap_edges=min_overlap_edges,
                    approx_merge_match_fraction=approx_merge_match_fraction,
                    approx_merge_min_edges=approx_merge_min_edges,
                )
                resolved = total_trace_count - len(next_state.remaining)
                heuristic = (
                    resolved,
                    reachable,
                    len(next_state.contig),
                    next_state.contained_trace_count + next_state.approximate_contained_trace_count,
                    -next_state.merge_steps,
                )
                next_frontier.append((heuristic, next_state))

        if not next_frontier:
            return best_completed

        deduped: dict[tuple[tuple[str, ...], tuple[str, ...]], tuple[tuple[int, int, int, int, int], _AssemblyState]] = {}
        for heuristic, state in next_frontier:
            signature = (tuple(state.contig), tuple(sorted(state.remaining)))
            current = deduped.get(signature)
            if current is None or heuristic > current[0]:
                deduped[signature] = (heuristic, state)

        frontier = [
            state
            for _, state in sorted(
                deduped.values(),
                key=lambda item: item[0],
                reverse=True,
            )[:beam_width]
        ]

    return best_completed


def _assemble_fragments(
    observations: list[_TraceObservation],
    *,
    min_overlap_edges: int,
    approx_containment_coverage: float,
    approx_block_fraction: float,
    approx_block_min_edges: int,
    approx_merge_match_fraction: float,
    approx_merge_min_edges: int,
) -> list[_AssemblyFragment]:
    """Assemble observations into one or more contiguous fragments.

    Runs greedy overlap assembly (with beam-search fallback) repeatedly until
    all observations are consumed.  Each round produces one fragment.
    """
    fragments: list[_AssemblyFragment] = []
    unassembled = list(observations)

    while unassembled:
        seed = max(
            unassembled,
            key=lambda obs: _seed_score(
                obs.edge_ids,
                [o.edge_ids for o in unassembled],
                min_coverage=approx_containment_coverage,
                min_block_fraction=approx_block_fraction,
                min_block_edges=approx_block_min_edges,
            ),
        )
        contig = list(seed.edge_ids)
        remaining: dict[str, list[str]] = {
            obs.trace_id: list(obs.edge_ids)
            for obs in unassembled
            if obs.trace_id != seed.trace_id
        }
        initial_state = _AssemblyState(
            contig=list(contig),
            remaining=dict(remaining),
            contained_trace_count=0,
            approximate_contained_trace_count=0,
            merge_steps=0,
            approximate_merge_steps=0,
        )

        edge_support, pair_support = _support_counters(
            [contig, *remaining.values()]
        )
        contained_trace_count = 0
        approximate_contained_trace_count = 0
        merge_steps = 0
        approximate_merge_steps = 0
        beam_search_used = False
        greedy_failed = False

        while remaining:
            remaining, dropped_contained, dropped_approximate = _drop_resolved_traces(
                contig,
                remaining,
                min_coverage=approx_containment_coverage,
                min_block_fraction=approx_block_fraction,
                min_block_edges=approx_block_min_edges,
            )
            contained_trace_count += dropped_contained
            approximate_contained_trace_count += dropped_approximate
            if not remaining:
                break

            merge_candidates = _build_merge_candidates(
                contig,
                remaining,
                edge_support=edge_support,
                pair_support=pair_support,
                min_overlap_edges=min_overlap_edges,
                approx_merge_match_fraction=approx_merge_match_fraction,
                approx_merge_min_edges=approx_merge_min_edges,
            )
            best_merge = _select_unambiguous_candidate(merge_candidates)
            if best_merge is None:
                greedy_failed = True
                break

            contig = best_merge.merged_edge_ids
            remaining.pop(best_merge.trace_id, None)
            merge_steps += 1
            if best_merge.kind == "approximate":
                approximate_merge_steps += 1

            edge_support, pair_support = _support_counters(
                [contig, *remaining.values()]
            )

        if greedy_failed:
            beam_state = _beam_search_assembly(
                initial_state,
                total_trace_count=len(unassembled),
                min_coverage=approx_containment_coverage,
                min_block_fraction=approx_block_fraction,
                min_block_edges=approx_block_min_edges,
                min_overlap_edges=min_overlap_edges,
                approx_merge_match_fraction=approx_merge_match_fraction,
                approx_merge_min_edges=approx_merge_min_edges,
            )
            if beam_state is not None and not beam_state.remaining:
                beam_search_used = True
                contig = beam_state.contig
                remaining = {}
                contained_trace_count = beam_state.contained_trace_count
                approximate_contained_trace_count = beam_state.approximate_contained_trace_count
                merge_steps = beam_state.merge_steps
                approximate_merge_steps = beam_state.approximate_merge_steps

        consumed_count = len(unassembled) - len(remaining)
        fragments.append(
            _AssemblyFragment(
                contig=contig,
                trace_count=consumed_count,
                contained_trace_count=contained_trace_count,
                approximate_contained_trace_count=approximate_contained_trace_count,
                merge_steps=merge_steps,
                approximate_merge_steps=approximate_merge_steps,
                beam_search_used=beam_search_used,
            )
        )
        unassembled = [
            obs for obs in unassembled if obs.trace_id in remaining
        ]

    return fragments


def _select_representative_geometry(geometries: list[list[list[float]]]) -> list[list[float]]:
    if not geometries:
        return []
    return max(geometries, key=lambda coords: (len(coords), coords))


def _stitch_geometries(
    edge_ids: list[str],
    geometry_by_edge_id: dict[str, list[list[float]]],
) -> list[list[float]]:
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
class EdgeSequenceOverlapAssemblyPreviewStrategy:
    """Assemble a single route from overlapping directed edge-id traces."""

    key: str = "edge_sequence_overlap_assembly_preview"
    label: str = "Edge-sequence overlap assembly (preview)"

    def default_params(self) -> dict[str, Any]:
        return {
            "costing": "bus",
            "search_radius": 60,
            "gps_accuracy": 20,
            "min_overlap_edges": 1,
            "min_edge_support": 0,
            "min_pair_support": 0,
            "edge_support_fraction": 0.34,
            "pair_support_fraction": 0.34,
            "max_singleton_noise_support": 1,
            "recover_geometry": True,
            "approx_containment_coverage": 0.85,
            "approx_block_fraction": 0.4,
            "approx_block_min_edges": 4,
            "approx_merge_match_fraction": 0.4,
            "approx_merge_min_edges": 2,
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
        min_overlap_edges = max(1, int(effective_params.get("min_overlap_edges", 1)))
        max_singleton_noise_support = max(
            1,
            int(effective_params.get("max_singleton_noise_support", 1)),
        )
        recover_geometry = bool(effective_params.get("recover_geometry", True))
        approx_containment_coverage = float(
            effective_params.get("approx_containment_coverage", 0.85)
        )
        approx_block_fraction = float(effective_params.get("approx_block_fraction", 0.4))
        approx_block_min_edges = max(1, int(effective_params.get("approx_block_min_edges", 4)))
        approx_merge_match_fraction = float(
            effective_params.get("approx_merge_match_fraction", 0.4)
        )
        approx_merge_min_edges = max(
            1,
            int(effective_params.get("approx_merge_min_edges", 2)),
        )

        observations: list[_TraceObservation] = []
        geometry_samples: dict[str, list[list[list[float]]]] = defaultdict(list)
        persisted_trace_count = 0
        fallback_trace_match_count = 0

        for trace in traces:
            if len(trace.points) < 2:
                continue

            match_result = None
            if trace.matched_edges:
                persisted_trace_count += 1
                sorted_edges = sorted(trace.matched_edges, key=lambda edge: edge.sequence)
                raw_edge_ids = [_edge_key_from_ref(edge) for edge in sorted_edges]
            else:
                match_result = trace_match(
                    _trace_points_payload(trace),
                    trace_id=trace.trace_id,
                    costing=costing,
                    search_radius=search_radius,
                    gps_accuracy=gps_accuracy,
                )
                fallback_trace_match_count += 1
                raw_edge_ids = [_edge_key_from_match(edge) for edge in match_result.edges]

            edge_ids = _collapse_consecutive(raw_edge_ids)
            if not edge_ids:
                continue
            observations.append(_TraceObservation(trace_id=trace.trace_id, edge_ids=edge_ids))

            if recover_geometry and match_result is None:
                match_result = trace_match(
                    _trace_points_payload(trace),
                    trace_id=trace.trace_id,
                    costing=costing,
                    search_radius=search_radius,
                    gps_accuracy=gps_accuracy,
                )

            if match_result is not None:
                for edge in match_result.edges:
                    edge_id = _edge_key_from_match(edge)
                    geometry = _edge_geometry(edge, match_result.shape_coords)
                    if len(geometry) >= 2:
                        geometry_samples[edge_id].append(geometry)

        if not observations:
            raise ValueError("No matched-edge traces are available for reconstruction")

        min_edge_support = _support_threshold(
            effective_params.get("min_edge_support", 0),
            len(observations),
            default_fraction=float(effective_params.get("edge_support_fraction", 0.34)),
        )
        min_pair_support = _support_threshold(
            effective_params.get("min_pair_support", 0),
            len(observations),
            default_fraction=float(effective_params.get("pair_support_fraction", 0.34)),
        )

        edge_support, pair_support = _support_counters([obs.edge_ids for obs in observations])
        cleaned_observations = [
            _TraceObservation(
                trace_id=obs.trace_id,
                edge_ids=_remove_internal_singletons(
                    obs.edge_ids,
                    edge_support,
                    pair_support,
                    min_edge_support=min_edge_support,
                    min_pair_support=min_pair_support,
                    max_singleton_noise_support=max_singleton_noise_support,
                ),
            )
            for obs in observations
        ]
        cleaned_observations = [obs for obs in cleaned_observations if obs.edge_ids]

        retained_observations: list[_TraceObservation] = []
        dropped_isolated_trace_count = 0
        for idx, observation in enumerate(cleaned_observations):
            connected = False
            for other_idx, other in enumerate(cleaned_observations):
                if idx == other_idx:
                    continue
                if _find_subsequence(observation.edge_ids, other.edge_ids) is not None:
                    connected = True
                    break
                if _find_subsequence(other.edge_ids, observation.edge_ids) is not None:
                    connected = True
                    break
                if _approximately_contains(
                    observation.edge_ids,
                    other.edge_ids,
                    min_coverage=approx_containment_coverage,
                    min_block_fraction=approx_block_fraction,
                    min_block_edges=approx_block_min_edges,
                ):
                    connected = True
                    break
                if _approximately_contains(
                    other.edge_ids,
                    observation.edge_ids,
                    min_coverage=approx_containment_coverage,
                    min_block_fraction=approx_block_fraction,
                    min_block_edges=approx_block_min_edges,
                ):
                    connected = True
                    break
                if _suffix_prefix_overlap(
                    observation.edge_ids,
                    other.edge_ids,
                    min_overlap_edges=min_overlap_edges,
                ):
                    connected = True
                    break
                if _suffix_prefix_overlap(
                    other.edge_ids,
                    observation.edge_ids,
                    min_overlap_edges=min_overlap_edges,
                ):
                    connected = True
                    break
            if connected or len(cleaned_observations) <= 2:
                retained_observations.append(observation)
            else:
                dropped_isolated_trace_count += 1

        if not retained_observations:
            raise ValueError("All traces were isolated; need more overlapping trips")

        fragments = _assemble_fragments(
            retained_observations,
            min_overlap_edges=min_overlap_edges,
            approx_containment_coverage=approx_containment_coverage,
            approx_block_fraction=approx_block_fraction,
            approx_block_min_edges=approx_block_min_edges,
            approx_merge_match_fraction=approx_merge_match_fraction,
            approx_merge_min_edges=approx_merge_min_edges,
        )

        geometry_by_edge_id = {
            edge_id: _select_representative_geometry(samples)
            for edge_id, samples in geometry_samples.items()
        }
        features: list[dict[str, Any]] = []
        total_route_points = 0
        for fragment_index, fragment in enumerate(fragments):
            route_coordinates = _stitch_geometries(fragment.contig, geometry_by_edge_id)
            if len(route_coordinates) < 2:
                continue
            total_route_points += len(route_coordinates)
            consensus_edge_ids = [
                int(edge_id.split(":", 1)[0]) for edge_id in fragment.contig
            ]
            features.append(
                {
                    "type": "Feature",
                    "properties": {
                        "strategy": self.label,
                        "line_id": str(line_id),
                        "fragment_index": fragment_index,
                        "fragment_count": len(fragments),
                        "trace_count": len(traces),
                        "usable_trace_count": len(retained_observations),
                        "fragment_trace_count": fragment.trace_count,
                        "consensus_edge_ids": consensus_edge_ids,
                        "consensus_directed_edge_ids": fragment.contig,
                    },
                    "geometry": {
                        "type": "LineString",
                        "coordinates": route_coordinates,
                    },
                }
            )

        if not features:
            raise ValueError("Consensus edge sequences could not be converted into lines")

        geojson = {
            "type": "FeatureCollection",
            "features": features,
        }
        diagnostics: dict[str, int | float | str] = {
            "line_id": str(line_id),
            "trace_count": len(traces),
            "usable_trace_count": len(retained_observations),
            "persisted_trace_count": persisted_trace_count,
            "fallback_trace_match_count": fallback_trace_match_count,
            "dropped_isolated_trace_count": dropped_isolated_trace_count,
            "fragment_count": len(fragments),
            "contained_trace_count": sum(f.contained_trace_count for f in fragments),
            "approximate_contained_trace_count": sum(
                f.approximate_contained_trace_count for f in fragments
            ),
            "merge_steps": sum(f.merge_steps for f in fragments),
            "approximate_merge_steps": sum(f.approximate_merge_steps for f in fragments),
            "beam_search_used": int(any(f.beam_search_used for f in fragments)),
            "min_overlap_edges": min_overlap_edges,
            "min_edge_support": min_edge_support,
            "min_pair_support": min_pair_support,
            "approx_containment_coverage": approx_containment_coverage,
            "approx_block_fraction": approx_block_fraction,
            "approx_block_min_edges": approx_block_min_edges,
            "approx_merge_match_fraction": approx_merge_match_fraction,
            "approx_merge_min_edges": approx_merge_min_edges,
            "consensus_edge_count": sum(len(f.contig) for f in fragments),
            "route_points": total_route_points,
            "consensus_edge_ids_json": json.dumps(
                [int(e.split(":", 1)[0]) for e in fragments[0].contig]
            ),
            "consensus_method": "edge_sequence_overlap_assembly",
        }
        return ReconstructionResult(
            strategy_name=self.label,
            geojson=geojson,
            diagnostics=diagnostics,
        )
