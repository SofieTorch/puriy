"""Synthetic vote generator for transit-lab.

Closes the loop between simulator-generated trips, the reconstructed route,
and EdgeVote rows. Reuses the same spatial helpers the production API uses
to define a voter's segment, then decides approve/reject by checking how
tightly that segment fits the voter's actual trip path (both raw GPS and
the cleaned/map-matched version).
"""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from database.models import (
    EdgeVote,
    RouteEdge,
    Trip,
    TripSession,
    VoteChoice,
)
from geodata.edge_overlap import (
    DEFAULT_MIN_TRIPS,
    find_overlapping_edges,
    get_active_route,
)


SIMULATOR_DEVICE_PREFIX = "simulator"


@dataclass
class VoteSimulationResult:
    error: str | None = None
    sessions_considered: int = 0
    voters_total: int = 0
    voters_eligible: int = 0
    events_created: int = 0
    approve: int = 0
    reject: int = 0
    edges_affected: int = 0
    synthetic_votes_wiped: int = 0
    voter_breakdown: list[dict] | None = None


def simulate_votes_for_line(
    db: Session,
    line_id: UUID,
    *,
    n_voters: int = 10,
    fit_threshold: float = 0.7,
    tight_tolerance_m: float = 15.0,
    voter_prefix: str = "simulator-vote",
    min_trips: int = DEFAULT_MIN_TRIPS,
    reset_synthetic: bool = False,
) -> VoteSimulationResult:
    """Simulate vote events for a line using its existing simulator-tagged trips.

    Pulls every TripSession whose ``device_id`` starts with ``simulator`` and
    has at least one cleaned trip on this line, sorts deterministically (by
    ``started_at`` then ``id``), then buckets them round-robin into ``n_voters``
    synthetic voters. For each voter:

    * Compute their segment (edges of the active route within 50m of any of
      that voter's cleaned trips) — same logic as the live API.
    * Compute a fit ratio: how many of those segment edges lie within
      ``tight_tolerance_m`` of *either* the voter's raw session path
      (``TripSession.computed_path``) or the cleaned trip
      (``Trip.computed_path``).
    * Vote ``approve`` if fit ratio >= ``fit_threshold``, else ``reject``.
    * Write one ``EdgeVote`` per segment edge (skipping any already-recorded
      ``(edge_id, device_id)`` pair) and bump ``RouteEdge.votes_for`` /
      ``votes_against`` accordingly.

    When ``reset_synthetic=True``, every existing ``EdgeVote`` whose
    ``device_id`` starts with ``voter_prefix + '-'`` is deleted *for edges in
    this route* (with counters decremented) before the new votes are generated.
    Real-user votes — anything outside that prefix — are never touched.

    Commits at the end. Returns counts and a per-voter breakdown.
    """
    if not voter_prefix or not voter_prefix.startswith(SIMULATOR_DEVICE_PREFIX):
        return VoteSimulationResult(
            error=(
                f"voter_prefix must start with '{SIMULATOR_DEVICE_PREFIX}' to keep "
                "the synthetic-voter namespace isolated from real users."
            )
        )

    route = get_active_route(db, line_id)
    if route is None:
        return VoteSimulationResult(error="No active route for this line.")

    sessions = (
        db.execute(
            select(TripSession)
            .join(Trip, Trip.session_id == TripSession.id)
            .where(
                Trip.line_id == line_id,
                Trip.computed_path.isnot(None),
                TripSession.device_id.like(f"{SIMULATOR_DEVICE_PREFIX}%"),
            )
            .order_by(TripSession.started_at, TripSession.id)
            .distinct()
        )
        .scalars()
        .all()
    )
    if not sessions:
        return VoteSimulationResult(
            error=(
                "No sessions tagged with a 'simulator…' device_id have cleaned "
                "trips on this line. Run the trip simulator + reconstruction first."
            )
        )

    synthetic_wiped = 0
    if reset_synthetic:
        synthetic_wiped = _wipe_synthetic_votes(db, route.id, voter_prefix)

    n_voters = max(1, min(n_voters, len(sessions)))
    buckets: dict[str, list[TripSession]] = {
        f"{voter_prefix}-{i:03d}": [] for i in range(n_voters)
    }
    for i, s in enumerate(sessions):
        voter_id = f"{voter_prefix}-{i % n_voters:03d}"
        buckets[voter_id].append(s)

    result = VoteSimulationResult(
        sessions_considered=len(sessions),
        voters_total=len(buckets),
        synthetic_votes_wiped=synthetic_wiped,
        voter_breakdown=[],
    )
    edges_affected: set[UUID] = set()

    for voter_id, voter_sessions in buckets.items():
        voter_trip_ids: list[UUID] = []
        for s in voter_sessions:
            for t in s.trips:
                if t.line_id == line_id and t.computed_path is not None:
                    voter_trip_ids.append(t.id)
        if len(voter_trip_ids) < min_trips:
            result.voter_breakdown.append({
                "voter": voter_id,
                "sessions": len(voter_sessions),
                "trips": len(voter_trip_ids),
                "status": f"skipped (<{min_trips} trips)",
                "vote": None,
                "fit_ratio": None,
                "edges": 0,
            })
            continue

        result.voters_eligible += 1

        segment_edges = find_overlapping_edges(db, route.id, voter_trip_ids)
        if not segment_edges:
            result.voter_breakdown.append({
                "voter": voter_id,
                "sessions": len(voter_sessions),
                "trips": len(voter_trip_ids),
                "status": "skipped (no overlapping edges)",
                "vote": None,
                "fit_ratio": None,
                "edges": 0,
            })
            continue

        edge_ids = [e.id for e in segment_edges]
        session_ids = [s.id for s in voter_sessions]
        fit_ratio = _compute_fit_ratio(
            db,
            edge_ids=edge_ids,
            trip_ids=voter_trip_ids,
            session_ids=session_ids,
            tight_tolerance_m=tight_tolerance_m,
        )
        vote = VoteChoice.APPROVE if fit_ratio >= fit_threshold else VoteChoice.REJECT

        new_votes = _apply_vote(
            db, voter_id=voter_id, edges=segment_edges, vote=vote
        )
        for e in segment_edges:
            edges_affected.add(e.id)

        if new_votes:
            result.events_created += 1
            if vote == VoteChoice.APPROVE:
                result.approve += 1
            else:
                result.reject += 1

        result.voter_breakdown.append({
            "voter": voter_id,
            "sessions": len(voter_sessions),
            "trips": len(voter_trip_ids),
            "status": "voted" if new_votes else "no-op (already voted)",
            "vote": vote.value,
            "fit_ratio": round(fit_ratio, 3),
            "edges": len(segment_edges),
            "new_rows": new_votes,
        })

    db.commit()
    result.edges_affected = len(edges_affected)
    return result


def _compute_fit_ratio(
    db: Session,
    *,
    edge_ids: list[UUID],
    trip_ids: list[UUID],
    session_ids: list[UUID],
    tight_tolerance_m: float,
) -> float:
    """Fraction of `edge_ids` within `tight_tolerance_m` of either trip or session path."""
    if not edge_ids:
        return 0.0

    matched: set[UUID] = set()

    if trip_ids:
        rows = db.execute(
            select(RouteEdge.id)
            .distinct()
            .join(
                Trip,
                func.ST_DWithin(
                    func.ST_Transform(RouteEdge.path, 3857),
                    func.ST_Transform(Trip.computed_path, 3857),
                    tight_tolerance_m,
                ),
            )
            .where(RouteEdge.id.in_(edge_ids), Trip.id.in_(trip_ids))
        ).scalars().all()
        matched.update(rows)

    if session_ids and len(matched) < len(edge_ids):
        rows = db.execute(
            select(RouteEdge.id)
            .distinct()
            .join(
                TripSession,
                func.ST_DWithin(
                    func.ST_Transform(RouteEdge.path, 3857),
                    func.ST_Transform(TripSession.computed_path, 3857),
                    tight_tolerance_m,
                ),
            )
            .where(
                RouteEdge.id.in_(edge_ids),
                TripSession.id.in_(session_ids),
                TripSession.computed_path.isnot(None),
            )
        ).scalars().all()
        matched.update(rows)

    return len(matched) / len(edge_ids)


def _apply_vote(
    db: Session,
    *,
    voter_id: str,
    edges: list[RouteEdge],
    vote: VoteChoice,
) -> int:
    """Insert EdgeVote rows for this voter. Returns count of newly inserted rows.

    Existing ``(edge, voter)`` pairs are left untouched — the simulator's
    ``reset_synthetic`` mode is responsible for any wiping that needs to
    happen first.
    """
    existing_edge_ids = set(
        db.execute(
            select(EdgeVote.edge_id).where(
                EdgeVote.device_id == voter_id,
                EdgeVote.edge_id.in_([e.id for e in edges]),
            )
        ).scalars().all()
    )

    new_count = 0
    for edge in edges:
        if edge.id in existing_edge_ids:
            continue
        db.add(EdgeVote(edge_id=edge.id, device_id=voter_id, vote=vote))
        if vote == VoteChoice.APPROVE:
            edge.votes_for += 1
        else:
            edge.votes_against += 1
        new_count += 1

    return new_count


def _wipe_synthetic_votes(db: Session, route_id: UUID, voter_prefix: str) -> int:
    """Delete every EdgeVote in this route's edges whose device_id starts with the
    synthetic prefix. Decrements RouteEdge counters in lockstep so the per-edge
    totals stay consistent. Returns the number of rows deleted.

    Real-user votes (anything outside the prefix) are never touched.
    """
    pattern = f"{voter_prefix}-%"
    rows = db.execute(
        select(EdgeVote, RouteEdge)
        .join(RouteEdge, RouteEdge.id == EdgeVote.edge_id)
        .where(
            RouteEdge.route_id == route_id,
            EdgeVote.device_id.like(pattern),
        )
    ).all()

    for vote_row, edge in rows:
        if vote_row.vote == VoteChoice.APPROVE:
            edge.votes_for = max(0, edge.votes_for - 1)
        else:
            edge.votes_against = max(0, edge.votes_against - 1)
        db.delete(vote_row)

    db.flush()
    return len(rows)
