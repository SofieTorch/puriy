"""Tests for the voting API endpoints."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from geoalchemy2.shape import from_shape
from shapely.geometry import LineString
from sqlalchemy.orm import Session

from database.models.line import Line, LineStatus, LineVote
from database.models.route import (
    EdgeVote,
    Route,
    RouteEdge,
    RouteSource,
    RouteStatus,
    Trip,
    TripStatus,
    VoteChoice,
)
from database.models.trip import SessionStatus, TripSession


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

# A realistic LineString in Cochabamba, ~500m along Av. Blanco Galindo
_ROUTE_COORDS = [
    (-66.1570, -17.3935),
    (-66.1560, -17.3937),
    (-66.1550, -17.3939),
    (-66.1540, -17.3941),
    (-66.1530, -17.3943),
]

# A trip path that overlaps with the first 3 edges of the route
_TRIP_COORDS = [
    (-66.1572, -17.3934),
    (-66.1561, -17.3936),
    (-66.1551, -17.3938),
    (-66.1541, -17.3940),
]

# A trip path that does NOT overlap with the route (far away)
_DISTANT_TRIP_COORDS = [
    (-66.2000, -17.4200),
    (-66.2010, -17.4210),
]

DEVICE_ID = "test-device-abc"
OTHER_DEVICE = "other-device-xyz"


@pytest.fixture
def line_with_route(db: Session):
    """Create a line with a pending route composed of 4 edges."""
    line = Line(name="150", description="Test route line", status=LineStatus.APPROVED)
    db.add(line)
    db.flush()

    route = Route(
        line_id=line.id,
        version=1,
        source=RouteSource.IMPORTED,
        status=RouteStatus.PENDING,
    )
    db.add(route)
    db.flush()

    # Create 4 edges from consecutive pairs of route coords
    for i in range(len(_ROUTE_COORDS) - 1):
        edge_line = LineString([_ROUTE_COORDS[i], _ROUTE_COORDS[i + 1]])
        db.add(
            RouteEdge(
                route_id=route.id,
                sequence=i,
                valhalla_edge_id=1000 + i,
                forward=True,
                path=from_shape(edge_line, srid=4326),
            )
        )

    db.commit()
    db.refresh(line)
    db.refresh(route)
    return line, route


@pytest.fixture
def device_trip(db: Session, line_with_route):
    """Create a cleaned trip for DEVICE_ID that overlaps with the route."""
    line, _route = line_with_route

    session = TripSession(
        line_id=line.id,
        device_id=DEVICE_ID,
        status=SessionStatus.COMPLETED,
    )
    db.add(session)
    db.flush()

    trip = Trip(
        session_id=session.id,
        line_id=line.id,
        status=TripStatus.CLEAN,
        computed_path=from_shape(LineString(_TRIP_COORDS), srid=4326),
    )
    db.add(trip)
    db.commit()
    db.refresh(trip)
    return trip


@pytest.fixture
def distant_trip(db: Session, line_with_route):
    """Create a cleaned trip that does NOT overlap with the route."""
    line, _route = line_with_route

    session = TripSession(
        line_id=line.id,
        device_id=OTHER_DEVICE,
        status=SessionStatus.COMPLETED,
    )
    db.add(session)
    db.flush()

    trip = Trip(
        session_id=session.id,
        line_id=line.id,
        status=TripStatus.CLEAN,
        computed_path=from_shape(LineString(_DISTANT_TRIP_COORDS), srid=4326),
    )
    db.add(trip)
    db.commit()
    db.refresh(trip)
    return trip


# ---------------------------------------------------------------------------
# GET /vote/pending
# ---------------------------------------------------------------------------


class TestListPendingVotes:
    def test_returns_line_with_overlapping_trip(
        self, client: TestClient, line_with_route, device_trip
    ):
        """Device with an overlapping trip should see the line as pending."""
        line, route = line_with_route

        resp = client.get("/vote/pending", params={"device_id": DEVICE_ID, "min_trips": 1})
        assert resp.status_code == 200

        data = resp.json()
        assert len(data) >= 1
        match = next((d for d in data if d["line_id"] == str(line.id)), None)
        assert match is not None
        assert match["line_name"] == "150"
        assert match["route_id"] == str(route.id)
        assert match["pending_edge_count"] > 0
        assert match["total_edge_count"] == 4

    def test_empty_for_unknown_device(self, client: TestClient, line_with_route):
        """Device with no trips should get an empty list."""
        resp = client.get("/vote/pending", params={"device_id": "no-such-device", "min_trips": 1})
        assert resp.status_code == 200
        assert resp.json() == []

    def test_empty_after_all_edges_voted(
        self, client: TestClient, line_with_route, device_trip
    ):
        """After voting on all overlapping edges, pending list should be empty."""
        line, _ = line_with_route

        # Vote
        client.post(
            f"/vote/{line.id}",
            json={"device_id": DEVICE_ID, "vote": "approve"},
            params={"min_trips": 1},
        )

        resp = client.get("/vote/pending", params={"device_id": DEVICE_ID, "min_trips": 1})
        assert resp.status_code == 200

        data = resp.json()
        match = next((d for d in data if d["line_id"] == str(line.id)), None)
        assert match is None

    def test_no_overlap_means_not_pending(
        self, client: TestClient, line_with_route, distant_trip
    ):
        """A trip that doesn't spatially overlap should not produce pending edges."""
        resp = client.get("/vote/pending", params={"device_id": OTHER_DEVICE, "min_trips": 1})
        assert resp.status_code == 200
        assert resp.json() == []

    def test_insufficient_trips_excluded(
        self, client: TestClient, line_with_route, device_trip
    ):
        """Device with fewer trips than min_trips should get empty list."""
        # device_trip creates 1 trip, require 5
        resp = client.get(
            "/vote/pending", params={"device_id": DEVICE_ID, "min_trips": 5}
        )
        assert resp.status_code == 200
        assert resp.json() == []


# ---------------------------------------------------------------------------
# GET /vote/{line_id}/segment
# ---------------------------------------------------------------------------


class TestGetVoteableSegment:
    def test_returns_overlapping_edges(
        self, client: TestClient, line_with_route, device_trip
    ):
        """Should return edges that overlap with the device's trip."""
        line, route = line_with_route

        resp = client.get(
            f"/vote/{line.id}/segment", params={"device_id": DEVICE_ID, "min_trips": 1}
        )
        assert resp.status_code == 200

        data = resp.json()
        assert data["route_id"] == str(route.id)
        assert data["line_name"] == "150"
        assert len(data["edges"]) > 0
        assert data["segment_geojson"] is not None
        assert data["segment_geojson"]["geometry"]["type"] == "MultiLineString"

        # Each edge should have expected fields
        edge = data["edges"][0]
        assert "id" in edge
        assert "sequence" in edge
        assert "confidence" in edge
        assert "path" in edge

    def test_404_no_trips(self, client: TestClient, line_with_route):
        """Should 404 when device has no trips for this line."""
        line, _ = line_with_route

        resp = client.get(
            f"/vote/{line.id}/segment", params={"device_id": "no-trips-device", "min_trips": 1}
        )
        assert resp.status_code == 404

    def test_404_no_line(self, client: TestClient):
        """Should 404 for non-existent line."""
        resp = client.get(
            f"/vote/{uuid4()}/segment", params={"device_id": DEVICE_ID, "min_trips": 1}
        )
        assert resp.status_code == 404

    def test_403_insufficient_trips(
        self, client: TestClient, line_with_route, device_trip
    ):
        """Should 403 when device hasn't traveled enough."""
        line, _ = line_with_route
        resp = client.get(
            f"/vote/{line.id}/segment",
            params={"device_id": DEVICE_ID, "min_trips": 5},
        )
        assert resp.status_code == 403
        assert "Not enough trips" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# POST /vote/{line_id}
# ---------------------------------------------------------------------------


class TestSubmitVote:
    def test_approve_creates_edge_votes(
        self, client: TestClient, db: Session, line_with_route, device_trip
    ):
        """Approving should create EdgeVote records and increment votes_for."""
        line, route = line_with_route

        resp = client.post(
            f"/vote/{line.id}",
            json={"device_id": DEVICE_ID, "vote": "approve"},
            params={"min_trips": 1},
        )
        assert resp.status_code == 201

        data = resp.json()
        assert data["vote"] == "approve"
        assert data["edges_voted"] > 0

        # Verify EdgeVote records exist
        votes = db.query(EdgeVote).filter(EdgeVote.device_id == DEVICE_ID).all()
        assert len(votes) == data["edges_voted"]
        assert all(v.vote == VoteChoice.APPROVE for v in votes)

        # Verify vote counts on edges
        edges = (
            db.query(RouteEdge)
            .filter(RouteEdge.route_id == route.id)
            .order_by(RouteEdge.sequence)
            .all()
        )
        voted_edges = [e for e in edges if e.votes_for > 0]
        assert len(voted_edges) == data["edges_voted"]

    def test_reject_increments_votes_against(
        self, client: TestClient, db: Session, line_with_route, device_trip
    ):
        """Rejecting should increment votes_against on overlapping edges."""
        line, route = line_with_route

        resp = client.post(
            f"/vote/{line.id}",
            json={"device_id": DEVICE_ID, "vote": "reject"},
            params={"min_trips": 1},
        )
        assert resp.status_code == 201
        assert resp.json()["vote"] == "reject"

        edges = (
            db.query(RouteEdge)
            .filter(RouteEdge.route_id == route.id)
            .order_by(RouteEdge.sequence)
            .all()
        )
        rejected_edges = [e for e in edges if e.votes_against > 0]
        assert len(rejected_edges) > 0

    def test_duplicate_vote_same_choice_is_idempotent(
        self, client: TestClient, db: Session, line_with_route, device_trip
    ):
        """Voting twice with the same choice should not double-count."""
        line, route = line_with_route

        # Vote approve twice
        resp1 = client.post(
            f"/vote/{line.id}",
            json={"device_id": DEVICE_ID, "vote": "approve"},
            params={"min_trips": 1},
        )
        resp2 = client.post(
            f"/vote/{line.id}",
            json={"device_id": DEVICE_ID, "vote": "approve"},
            params={"min_trips": 1},
        )
        assert resp1.status_code == 201
        assert resp2.status_code == 201

        # votes_for should be 1, not 2
        edges = (
            db.query(RouteEdge)
            .filter(RouteEdge.route_id == route.id)
            .order_by(RouteEdge.sequence)
            .all()
        )
        for e in edges:
            assert e.votes_for <= 1

    def test_change_vote_updates_counters(
        self, client: TestClient, db: Session, line_with_route, device_trip
    ):
        """Changing vote from approve to reject should adjust both counters."""
        line, route = line_with_route

        # First approve
        client.post(
            f"/vote/{line.id}",
            json={"device_id": DEVICE_ID, "vote": "approve"},
            params={"min_trips": 1},
        )

        # Then reject
        client.post(
            f"/vote/{line.id}",
            json={"device_id": DEVICE_ID, "vote": "reject"},
            params={"min_trips": 1},
        )

        edges = (
            db.query(RouteEdge)
            .filter(RouteEdge.route_id == route.id)
            .order_by(RouteEdge.sequence)
            .all()
        )
        voted_edges = [e for e in edges if e.votes_for > 0 or e.votes_against > 0]
        for e in voted_edges:
            assert e.votes_for == 0
            assert e.votes_against == 1

    def test_404_no_trips_for_device(self, client: TestClient, line_with_route):
        """Should 404 when device has no trips."""
        line, _ = line_with_route

        resp = client.post(
            f"/vote/{line.id}",
            json={"device_id": "ghost-device", "vote": "approve"},
            params={"min_trips": 1},
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Vote migration
# ---------------------------------------------------------------------------


class TestVoteMigration:
    def test_votes_carry_forward_to_new_route(self, db: Session):
        """When a route is superseded, votes should migrate to matching edges."""
        from geodata.migrate_votes import migrate_votes_to_new_route

        line = Line(name="Migration Test", status=LineStatus.APPROVED)
        db.add(line)
        db.flush()

        # Old route with 2 edges
        old_route = Route(
            line_id=line.id, version=1, source=RouteSource.IMPORTED,
            status=RouteStatus.SUPERSEDED,
        )
        db.add(old_route)
        db.flush()

        edge_line_a = LineString([(-66.15, -17.39), (-66.14, -17.39)])
        edge_line_b = LineString([(-66.14, -17.39), (-66.13, -17.39)])

        old_edge_a = RouteEdge(
            route_id=old_route.id, sequence=0, valhalla_edge_id=2001,
            forward=True, path=from_shape(edge_line_a, srid=4326),
            votes_for=5, votes_against=1,
        )
        old_edge_b = RouteEdge(
            route_id=old_route.id, sequence=1, valhalla_edge_id=2002,
            forward=True, path=from_shape(edge_line_b, srid=4326),
            votes_for=3, votes_against=0,
        )
        db.add_all([old_edge_a, old_edge_b])
        db.flush()

        # Add votes on old edges
        db.add(EdgeVote(edge_id=old_edge_a.id, device_id="dev1", vote=VoteChoice.APPROVE))
        db.add(EdgeVote(edge_id=old_edge_a.id, device_id="dev2", vote=VoteChoice.APPROVE))
        db.add(EdgeVote(edge_id=old_edge_b.id, device_id="dev1", vote=VoteChoice.APPROVE))
        db.flush()

        # New route with same valhalla edges
        new_route = Route(
            line_id=line.id, version=2, source=RouteSource.IMPORTED,
            status=RouteStatus.PENDING,
        )
        db.add(new_route)
        db.flush()

        new_edge_a = RouteEdge(
            route_id=new_route.id, sequence=0, valhalla_edge_id=2001,
            forward=True, path=from_shape(edge_line_a, srid=4326),
        )
        new_edge_b = RouteEdge(
            route_id=new_route.id, sequence=1, valhalla_edge_id=2002,
            forward=True, path=from_shape(edge_line_b, srid=4326),
        )
        db.add_all([new_edge_a, new_edge_b])
        db.flush()

        # Migrate
        migrated = migrate_votes_to_new_route(db, old_route.id, new_route.id)
        db.flush()

        assert migrated == 3  # 2 votes on edge_a + 1 on edge_b

        # New edges should have the vote counts
        db.refresh(new_edge_a)
        db.refresh(new_edge_b)
        assert new_edge_a.votes_for == 5
        assert new_edge_a.votes_against == 1
        assert new_edge_b.votes_for == 3
        assert new_edge_b.votes_against == 0

        # EdgeVote records should point to new edges
        votes_on_new_a = (
            db.query(EdgeVote).filter(EdgeVote.edge_id == new_edge_a.id).all()
        )
        assert len(votes_on_new_a) == 2
        votes_on_old_a = (
            db.query(EdgeVote).filter(EdgeVote.edge_id == old_edge_a.id).all()
        )
        assert len(votes_on_old_a) == 0


# ---------------------------------------------------------------------------
# Line familiarity voting
# ---------------------------------------------------------------------------

# Route for a DIFFERENT line, near the same coords as _ROUTE_COORDS
_NEARBY_LINE_COORDS = [
    (-66.1565, -17.3930),
    (-66.1555, -17.3932),
    (-66.1545, -17.3934),
]


@pytest.fixture
def nearby_line_with_route(db: Session):
    """Create a second line with a route near _ROUTE_COORDS."""
    line = Line(name="A", description="Nearby line A", status=LineStatus.APPROVED)
    db.add(line)
    db.flush()

    route = Route(
        line_id=line.id, version=1, source=RouteSource.IMPORTED,
        status=RouteStatus.PENDING,
    )
    db.add(route)
    db.flush()

    for i in range(len(_NEARBY_LINE_COORDS) - 1):
        edge_line = LineString([_NEARBY_LINE_COORDS[i], _NEARBY_LINE_COORDS[i + 1]])
        db.add(
            RouteEdge(
                route_id=route.id, sequence=i, valhalla_edge_id=3000 + i,
                forward=True, path=from_shape(edge_line, srid=4326),
            )
        )

    db.commit()
    db.refresh(line)
    return line


class TestListNearbyLines:
    def test_returns_nearby_line(
        self, client: TestClient, line_with_route, device_trip, nearby_line_with_route
    ):
        """Should return a nearby line the device doesn't already ride."""
        nearby = nearby_line_with_route

        resp = client.get(
            "/vote/lines/nearby", params={"device_id": DEVICE_ID}
        )
        assert resp.status_code == 200

        data = resp.json()
        match = next((d for d in data if d["line_id"] == str(nearby.id)), None)
        assert match is not None
        assert match["line_name"] == "A"

    def test_excludes_ridden_line(
        self, client: TestClient, line_with_route, device_trip
    ):
        """Should NOT return the line the device already has trips on."""
        line, _ = line_with_route

        resp = client.get(
            "/vote/lines/nearby", params={"device_id": DEVICE_ID}
        )
        assert resp.status_code == 200

        data = resp.json()
        match = next((d for d in data if d["line_id"] == str(line.id)), None)
        assert match is None

    def test_excludes_already_voted_line(
        self, client: TestClient, db: Session,
        line_with_route, device_trip, nearby_line_with_route
    ):
        """After voting on a nearby line, it should disappear."""
        nearby = nearby_line_with_route

        # Vote on the nearby line
        client.post(
            f"/vote/lines/{nearby.id}",
            json={"device_id": DEVICE_ID, "vote": "approve"},
        )

        resp = client.get(
            "/vote/lines/nearby", params={"device_id": DEVICE_ID}
        )
        data = resp.json()
        match = next((d for d in data if d["line_id"] == str(nearby.id)), None)
        assert match is None

    def test_empty_for_unknown_device(self, client: TestClient):
        """Unknown device should get empty list."""
        resp = client.get(
            "/vote/lines/nearby", params={"device_id": "unknown"}
        )
        assert resp.status_code == 200
        assert resp.json() == []


class TestSubmitLineVote:
    def test_approve_line(
        self, client: TestClient, db: Session, nearby_line_with_route
    ):
        """Should create a LineVote record."""
        line = nearby_line_with_route

        resp = client.post(
            f"/vote/lines/{line.id}",
            json={"device_id": DEVICE_ID, "vote": "approve"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["line_id"] == str(line.id)
        assert data["vote"] == "approve"

        vote = (
            db.query(LineVote)
            .filter(LineVote.line_id == line.id, LineVote.device_id == DEVICE_ID)
            .one()
        )
        assert vote.vote == VoteChoice.APPROVE

    def test_change_line_vote(
        self, client: TestClient, db: Session, nearby_line_with_route
    ):
        """Changing vote should update, not duplicate."""
        line = nearby_line_with_route

        client.post(
            f"/vote/lines/{line.id}",
            json={"device_id": DEVICE_ID, "vote": "approve"},
        )
        client.post(
            f"/vote/lines/{line.id}",
            json={"device_id": DEVICE_ID, "vote": "reject"},
        )

        votes = (
            db.query(LineVote)
            .filter(LineVote.line_id == line.id, LineVote.device_id == DEVICE_ID)
            .all()
        )
        assert len(votes) == 1
        assert votes[0].vote == VoteChoice.REJECT

    def test_404_unknown_line(self, client: TestClient):
        """Should 404 for non-existent line."""
        resp = client.post(
            f"/vote/lines/{uuid4()}",
            json={"device_id": DEVICE_ID, "vote": "approve"},
        )
        assert resp.status_code == 404
