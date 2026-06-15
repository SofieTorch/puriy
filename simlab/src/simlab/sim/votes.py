"""Vote simulation, mirroring the production rules.

Eligibility replicates the server (routes/voting.py): a device may
vote on a line only with >= eligibility_min_trips cleaned trips within
the eligibility window, and only on edges overlapping its own trips
(within overlap_tolerance_m). Resolution replicates the pipeline
steps (resolve_edge_votes / resolve_routes) in memory.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

import shapely
from routebuilder.graph import _project_m
from routebuilder.types import ConsensusRoute, MatchedTrace
from shapely.geometry import LineString

from ..scenario import ScenarioConfig
from .personas import SimTrip


@dataclass
class VoteEvent:
    device_id: str
    edge_id: int
    forward: bool
    approve: bool


@dataclass
class EdgeTally:
    edge_id: int
    forward: bool
    inferred: bool
    votes_for: int = 0
    votes_against: int = 0
    status: str = "PENDING"

    @property
    def total(self) -> int:
        return self.votes_for + self.votes_against


@dataclass
class VotingOutcome:
    votes: list[VoteEvent]
    tallies: dict[tuple[int, bool], EdgeTally]
    eligible_devices: list[str]
    ineligible_devices: list[str]
    route_status: dict[str, str] = field(default_factory=dict)


def simulate_votes(
    routes: list[ConsensusRoute],
    trips: list[SimTrip],
    matched_by_trip: dict[str, MatchedTrace],
    truth_polyline: list[tuple[float, float]] | list[list[tuple[float, float]]],
    config: ScenarioConfig,
    rng: random.Random,
) -> VotingOutcome:
    vm = config.votes
    if not trips:
        return VotingOutcome([], {}, [], [])

    # Accept one polyline or several (main + ramal variants): an edge
    # is "true" when it lies near any rideable ground-truth route.
    if truth_polyline and isinstance(truth_polyline[0], list):
        truth_polylines = [p for p in truth_polyline if len(p) >= 2]
    else:
        truth_polylines = [truth_polyline] if len(truth_polyline) >= 2 else []

    # Eligibility is structural: a voter is a device that aggregates
    # >= eligibility_min_trips cleaned (matched) traces — built that way by
    # form_voters. No time window to reason about.
    trips_by_device: dict[str, list[SimTrip]] = {}
    for trip in trips:
        if trip.trip_id in matched_by_trip:
            trips_by_device.setdefault(trip.device_id, []).append(trip)

    eligible: dict[str, list[SimTrip]] = {}
    ineligible: list[str] = []
    for device, device_trips in trips_by_device.items():
        if len(device_trips) >= vm.eligibility_min_trips:
            eligible[device] = device_trips
        else:
            ineligible.append(device)

    ref_lat = truth_polylines[0][0][1] if truth_polylines else -17.39
    truth_lines = [
        LineString([_project_m(p, ref_lat) for p in polyline])
        for polyline in truth_polylines
    ]

    tallies: dict[tuple[int, bool], EdgeTally] = {}
    edge_index: list[tuple] = []  # (route, ConsensusEdge, midpoint_m)
    for route in routes:
        for ce in route.edges:
            tallies[(ce.edge.edge_id, ce.edge.forward)] = EdgeTally(
                edge_id=ce.edge.edge_id,
                forward=ce.edge.forward,
                inferred=ce.inferred,
            )
            if ce.geometry:
                midpoint = _project_m(ce.geometry[len(ce.geometry) // 2], ref_lat)
                edge_index.append((route, ce, midpoint))

    midpoints = shapely.points([m for (_, _, m) in edge_index]) if edge_index else None
    if midpoints is not None and truth_lines:
        on_truth_flags = [False] * len(edge_index)
        for line in truth_lines:
            distances = shapely.distance(line, midpoints)
            for i, d in enumerate(distances):
                if d <= vm.overlap_tolerance_m:
                    on_truth_flags[i] = True
    else:
        on_truth_flags = [False] * len(edge_index)

    votes: list[VoteEvent] = []

    # Every eligible voter votes (turnout is measured, not an input): the only
    # way an eligible device casts nothing is if none of its traces overlap a
    # reconstructed edge.
    for device, recent in eligible.items():
        # Edges overlapping this device's own trips (vectorized:
        # distance from each device line to all edge midpoints).
        device_lines = [
            LineString([_project_m(p, ref_lat) for p in matched_by_trip[t.trip_id].matched_polyline])
            for t in recent
            if len(matched_by_trip[t.trip_id].matched_polyline) >= 2
        ]
        if not device_lines or midpoints is None:
            continue

        overlaps = [False] * len(edge_index)
        for line in device_lines:
            distances = shapely.distance(line, midpoints)
            for i, d in enumerate(distances):
                if d <= vm.overlap_tolerance_m:
                    overlaps[i] = True

        for i, (route, ce, _) in enumerate(edge_index):
            if not overlaps[i]:
                continue
            # Voter judgement: does this edge belong to the route they
            # know? Modelled from the true geometry.
            on_truth = bool(on_truth_flags[i])
            p_approve = vm.approve_prob_true_edge if on_truth else vm.approve_prob_spurious_edge
            approve = rng.random() < p_approve
            tally = tallies[(ce.edge.edge_id, ce.edge.forward)]
            if approve:
                tally.votes_for += 1
            else:
                tally.votes_against += 1
            votes.append(VoteEvent(device, ce.edge.edge_id, ce.edge.forward, approve))

    outcome = VotingOutcome(
        votes=votes,
        tallies=tallies,
        eligible_devices=sorted(eligible),
        ineligible_devices=sorted(ineligible),
    )
    resolve(routes, outcome, config)
    return outcome


def resolve(
    routes: list[ConsensusRoute],
    outcome: VotingOutcome,
    config: ScenarioConfig,
) -> None:
    """Pipeline-equivalent resolution: edges then routes."""
    vm = config.votes
    for tally in outcome.tallies.values():
        if tally.total >= vm.edge_min_votes:
            ratio = tally.votes_for / tally.total
            if ratio >= vm.edge_approval_threshold:
                tally.status = "CONFIRMED"

    for route in routes:
        edge_keys = [(ce.edge.edge_id, ce.edge.forward) for ce in route.edges]
        confirmed = sum(
            1 for k in edge_keys if outcome.tallies.get(k, EdgeTally(0, True, False)).status == "CONFIRMED"
        )
        ratio = confirmed / len(edge_keys) if edge_keys else 0.0
        outcome.route_status[route_key(route)] = (
            "CONFIRMED" if ratio >= vm.route_approval_threshold else "PENDING"
        )


def route_key(route: ConsensusRoute) -> str:
    """Unique key per route: the same ramal label exists once per
    direction group (a line's outbound and return runs)."""
    return f"{route.ramal_label}/d{route.direction_group}"
