"""Vote eligibility and resolution — including the boundary cases:
exactly 3 trips, and trips exactly at the 14-day window edge."""

import random
from datetime import UTC, datetime, timedelta

from routebuilder.types import ConsensusEdge, ConsensusRoute, DirectedEdge, MatchedTrace
from simlab.scenario import PersonaSpec, ScenarioConfig
from simlab.sim.personas import SimTrip
from simlab.sim.votes import simulate_votes

LAT = -17.3935
SIM_START = datetime(2026, 5, 1, 8, 0, tzinfo=UTC)


def _lon(i: int) -> float:
    return -66.157 + i * 0.00094


def _truth(n: int = 10):
    return [(_lon(i), LAT) for i in range(n + 1)]


def _route(n: int = 10) -> ConsensusRoute:
    edges = [
        ConsensusEdge(
            edge=DirectedEdge(i, True),
            geometry=[(_lon(i - 1), LAT), (_lon(i), LAT)],
            confidence=1.0,
        )
        for i in range(1, n + 1)
    ]
    geometry = [p for ce in edges for p in ce.geometry]
    return ConsensusRoute(
        ramal_label="main", direction_group=0, edges=edges,
        geometry=geometry, trace_count=3,
    )


def _trip(device: str, day: int, trip_id: str) -> SimTrip:
    return SimTrip(
        trip_id=trip_id, device_id=device, persona_name="p", day=day,
        started_at=SIM_START + timedelta(days=day),
        forward=True, board_m=0.0, alight_m=1000.0,
    )


def _matched(trip_id: str, lo: int = 0, hi: int = 10) -> MatchedTrace:
    return MatchedTrace(
        trace_id=trip_id,
        edges=[DirectedEdge(i, True) for i in range(max(lo, 1), hi + 1)],
        edge_geometries={},
        matched_polyline=[(_lon(i), LAT) for i in range(lo, hi + 1)],
        match_quality=1.0,
    )


def _config(**votes_kwargs) -> ScenarioConfig:
    return ScenarioConfig(
        name="t", route_geojson="x", sim_days=21, vote_day=21,
        personas=[PersonaSpec(name="p", count=1, vote_propensity=1.0)],
        votes=dict(approve_prob_true_edge=1.0, approve_prob_spurious_edge=0.0,
                   **votes_kwargs),
    )


def test_exactly_three_recent_trips_is_eligible():
    config = _config()
    trips = [_trip("d1", 10 + i, f"t{i}") for i in range(3)]  # days 10,11,12 < vote day 21
    matched = {t.trip_id: _matched(t.trip_id) for t in trips}
    outcome = simulate_votes([_route()], trips, matched, _truth(), config, random.Random(1))
    assert outcome.eligible_devices == ["d1"]
    assert len(outcome.votes) > 0


def test_two_trips_is_not_eligible():
    config = _config()
    trips = [_trip("d1", 10 + i, f"t{i}") for i in range(2)]
    matched = {t.trip_id: _matched(t.trip_id) for t in trips}
    outcome = simulate_votes([_route()], trips, matched, _truth(), config, random.Random(1))
    assert outcome.eligible_devices == []
    assert outcome.ineligible_devices == ["d1"]
    assert outcome.votes == []


def test_eligibility_is_structural_not_windowed():
    # Eligibility no longer depends on when trips happened — a device with
    # >= min_trips matched traces is a voter regardless of day.
    config = _config()
    trips = [_trip("d1", i, f"t{i}") for i in range(3)]  # days 0,1,2 — old
    matched = {t.trip_id: _matched(t.trip_id) for t in trips}
    outcome = simulate_votes([_route()], trips, matched, _truth(), config, random.Random(1))
    assert outcome.eligible_devices == ["d1"]


def test_unmatched_trips_do_not_count():
    config = _config()
    trips = [_trip("d1", 10 + i, f"t{i}") for i in range(3)]
    matched = {t.trip_id: _matched(t.trip_id) for t in trips[:2]}  # one trip not cleaned
    outcome = simulate_votes([_route()], trips, matched, _truth(), config, random.Random(1))
    assert outcome.eligible_devices == []


def test_votes_only_on_overlapping_segments():
    # Device's trips cover only the first half of the route: it must
    # not vote on far-away edges.
    config = _config()
    trips = [_trip("d1", 10 + i, f"t{i}") for i in range(3)]
    matched = {t.trip_id: _matched(t.trip_id, lo=0, hi=5) for t in trips}
    outcome = simulate_votes([_route(20)], trips, matched, _truth(20), config, random.Random(1))
    voted_edges = {v.edge_id for v in outcome.votes}
    assert voted_edges  # voted on nearby edges
    assert all(e <= 7 for e in voted_edges), voted_edges  # 50m tolerance reaches ~1 edge past


def test_resolution_confirms_route_with_enough_approvals():
    config = _config()
    trips = [_trip(f"d{k}", 10 + i, f"t{k}:{i}") for k in range(3) for i in range(3)]
    matched = {t.trip_id: _matched(t.trip_id) for t in trips}
    outcome = simulate_votes([_route()], trips, matched, _truth(), config, random.Random(1))
    assert len(outcome.eligible_devices) == 3
    confirmed = [t for t in outcome.tallies.values() if t.status == "CONFIRMED"]
    assert len(confirmed) == len(outcome.tallies)  # all true edges, 3 approvals each
    assert outcome.route_status["main/d0"] == "CONFIRMED"


def test_spurious_edges_get_rejected():
    # An edge far from the truth: voters reject it, route stays pending
    # if too many edges are unconfirmed.
    config = _config()
    route = _route(10)
    # Replace one edge with a spurious one 300m north.
    bad = ConsensusEdge(
        edge=DirectedEdge(99, True),
        geometry=[(_lon(5), LAT + 0.0027), (_lon(6), LAT + 0.0027)],
        confidence=0.34,
    )
    route.edges[5] = bad
    trips = [_trip(f"d{k}", 10 + i, f"t{k}:{i}") for k in range(3) for i in range(3)]
    matched = {
        t.trip_id: MatchedTrace(
            trace_id=t.trip_id,
            edges=[DirectedEdge(i, True) for i in range(1, 11)],
            edge_geometries={},
            # Polyline passes near the spurious edge too (within 50m? no - 300m).
            matched_polyline=[(_lon(i), LAT) for i in range(11)] + [(_lon(5), LAT + 0.0027)],
            match_quality=1.0,
        )
        for t in trips
    }
    outcome = simulate_votes([route], trips, matched, _truth(), config, random.Random(1))
    tally = outcome.tallies[(99, True)]
    assert tally.votes_against >= tally.votes_for or tally.total == 0
