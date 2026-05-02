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

from geoalchemy2 import WKBElement
from shapely import wkb

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
DEFAULT_VOTER_PREFIX = "simulator-vote"


def _group_into_sections(edges: list[RouteEdge]) -> list[list[RouteEdge]]:
    """Group contiguous edges (by sequence) into sections."""
    if not edges:
        return []
    sections: list[list[RouteEdge]] = []
    current: list[RouteEdge] = []
    for edge in edges:
        if current and edge.sequence != current[-1].sequence + 1:
            sections.append(current)
            current = []
        current.append(edge)
    if current:
        sections.append(current)
    return sections


def _load_simulator_sessions(db: Session, line_id: UUID) -> list[TripSession]:
    """Pull every simulator-tagged TripSession with cleaned trips on this line,
    sorted deterministically by (started_at, id) so bucketing is stable.
    """
    return (
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


def _bucket_sessions(
    sessions: list[TripSession], n_voters: int, voter_prefix: str
) -> dict[str, list[TripSession]]:
    """Round-robin bucket sessions into N synthetic voters."""
    n = max(1, min(n_voters, len(sessions)))
    buckets: dict[str, list[TripSession]] = {
        f"{voter_prefix}-{i:03d}": [] for i in range(n)
    }
    for i, s in enumerate(sessions):
        buckets[f"{voter_prefix}-{i % n:03d}"].append(s)
    return buckets


def _detect_synthetic_voter_count(db: Session, route_id: UUID, voter_prefix: str) -> int:
    """Infer the N used at simulation time from existing EdgeVote device_ids
    matching the synthetic prefix. Returns max bucket index + 1, or 0.
    """
    rows = (
        db.execute(
            select(EdgeVote.device_id)
            .distinct()
            .join(RouteEdge, RouteEdge.id == EdgeVote.edge_id)
            .where(
                RouteEdge.route_id == route_id,
                EdgeVote.device_id.like(f"{voter_prefix}-%"),
            )
        )
        .scalars()
        .all()
    )
    indices: list[int] = []
    for did in rows:
        try:
            indices.append(int(did.rsplit("-", 1)[-1]))
        except ValueError:
            continue
    return (max(indices) + 1) if indices else 0


def _coords(geom) -> list[list[float]]:
    """Extract [[lon, lat], ...] from a PostGIS geometry."""
    if geom is None:
        return []
    if isinstance(geom, WKBElement):
        return [list(c) for c in wkb.loads(bytes(geom.data)).coords]
    try:
        return [list(c) for c in geom.coords]
    except Exception:
        return []


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

    sessions = _load_simulator_sessions(db, line_id)
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

    buckets = _bucket_sessions(sessions, n_voters, voter_prefix)

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
                "sections": [],
            })
            continue

        # Vote per section independently
        sections = _group_into_sections(segment_edges)
        session_ids = [s.id for s in voter_sessions]
        total_new_votes = 0
        section_results = []

        for sec_idx, sec_edges in enumerate(sections):
            sec_edge_ids = [e.id for e in sec_edges]
            sec_fit = _compute_fit_ratio(
                db,
                edge_ids=sec_edge_ids,
                trip_ids=voter_trip_ids,
                session_ids=session_ids,
                tight_tolerance_m=tight_tolerance_m,
            )
            sec_vote = VoteChoice.APPROVE if sec_fit >= fit_threshold else VoteChoice.REJECT
            sec_new = _apply_vote(db, voter_id=voter_id, edges=sec_edges, vote=sec_vote)
            total_new_votes += sec_new

            for e in sec_edges:
                edges_affected.add(e.id)

            if sec_new:
                if sec_vote == VoteChoice.APPROVE:
                    result.approve += 1
                else:
                    result.reject += 1

            section_results.append({
                "section_index": sec_idx,
                "edges": len(sec_edges),
                "fit_ratio": round(sec_fit, 3),
                "vote": sec_vote.value,
                "new_rows": sec_new,
            })

        if total_new_votes:
            result.events_created += 1

        result.voter_breakdown.append({
            "voter": voter_id,
            "sessions": len(voter_sessions),
            "trips": len(voter_trip_ids),
            "status": "voted" if total_new_votes else "no-op (already voted)",
            "vote": "per-section",
            "fit_ratio": None,
            "edges": len(segment_edges),
            "new_rows": total_new_votes,
            "sections": section_results,
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


def _build_section_view(edges: list[dict]) -> dict:
    """Build a section summary from a group of contiguous voted edges."""
    # Stitch geometry
    stitched: list[list[float]] = []
    for ve in edges:
        if not stitched:
            stitched.extend(ve["path"])
        elif stitched[-1] == ve["path"][0]:
            stitched.extend(ve["path"][1:])
        else:
            stitched.extend(ve["path"])

    votes = [ve["vote"] for ve in edges]
    # Section vote = majority of edge votes (all same in practice since we vote per section)
    approve_count = sum(1 for v in votes if v == "approve")
    section_vote = "approve" if approve_count > len(votes) / 2 else "reject"

    return {
        "edges": edges,
        "edge_count": len(edges),
        "geometry": stitched,
        "vote": section_vote,
        "sequences": [ve["sequence"] for ve in edges],
    }


def load_synthetic_voter_views(
    db: Session,
    line_id: UUID,
    route_id: UUID,
    *,
    voter_prefix: str = DEFAULT_VOTER_PREFIX,
) -> list[dict]:
    """Per-voter rendering payload for synthetic vote minimaps.

    Re-derives each voter's session bucket by detecting N from the existing
    EdgeVote device_ids (max bucket index + 1) and replaying the same
    deterministic round-robin bucketing the simulator used. For each voter,
    returns the geometry needed to render a minimap:

      * raw_paths: TripSession.computed_path coords per session (raw GPS)
      * cleaned_paths: Trip.computed_path coords per cleaned trip
      * voted_edges: list of {path, vote, sequence, edge_id} for every edge
        this voter cast a vote on (vote ∈ "approve" / "reject")
      * bounds: dict with lat/lon min-max for view-state framing, or None

    Skips voters with no recorded votes. Returns [] when no synthetic votes
    exist for the route.
    """
    n = _detect_synthetic_voter_count(db, route_id, voter_prefix)
    if n == 0:
        return []

    sessions = _load_simulator_sessions(db, line_id)
    buckets = _bucket_sessions(sessions, n, voter_prefix)

    # Pull every synthetic vote (with its edge) for this route in one shot,
    # then group by voter id.
    rows = db.execute(
        select(EdgeVote, RouteEdge)
        .join(RouteEdge, RouteEdge.id == EdgeVote.edge_id)
        .where(
            RouteEdge.route_id == route_id,
            EdgeVote.device_id.like(f"{voter_prefix}-%"),
        )
        .order_by(RouteEdge.sequence)
    ).all()
    votes_by_voter: dict[str, list[tuple]] = {}
    for vote_row, edge in rows:
        votes_by_voter.setdefault(vote_row.device_id, []).append((vote_row, edge))

    views: list[dict] = []
    for voter_id in sorted(buckets.keys()):
        voter_votes = votes_by_voter.get(voter_id, [])
        if not voter_votes:
            continue

        bucket_sessions = buckets.get(voter_id, [])
        raw_paths = [
            _coords(s.computed_path)
            for s in bucket_sessions
            if s.computed_path is not None
        ]
        raw_paths = [p for p in raw_paths if len(p) >= 2]

        cleaned_paths: list[list[list[float]]] = []
        for s in bucket_sessions:
            for t in s.trips:
                if t.line_id == line_id and t.computed_path is not None:
                    coords = _coords(t.computed_path)
                    if len(coords) >= 2:
                        cleaned_paths.append(coords)

        voted_edges: list[dict] = []
        for vote_row, edge in voter_votes:
            coords = _coords(edge.path)
            if len(coords) < 2:
                continue
            voted_edges.append({
                "path": coords,
                "vote": vote_row.vote.value,
                "sequence": edge.sequence,
                "edge_id": str(edge.id),
            })

        # Group voted edges into contiguous sections for carousel display
        voted_sections: list[dict] = []
        if voted_edges:
            sorted_ve = sorted(voted_edges, key=lambda x: x["sequence"])
            current_sec: list[dict] = [sorted_ve[0]]
            for ve in sorted_ve[1:]:
                if ve["sequence"] == current_sec[-1]["sequence"] + 1:
                    current_sec.append(ve)
                else:
                    voted_sections.append(_build_section_view(current_sec))
                    current_sec = [ve]
            voted_sections.append(_build_section_view(current_sec))

        all_lons: list[float] = []
        all_lats: list[float] = []
        for path in raw_paths + cleaned_paths:
            all_lons.extend(c[0] for c in path)
            all_lats.extend(c[1] for c in path)
        for ve in voted_edges:
            all_lons.extend(c[0] for c in ve["path"])
            all_lats.extend(c[1] for c in ve["path"])

        if all_lons and all_lats:
            bounds = {
                "lat_min": min(all_lats),
                "lat_max": max(all_lats),
                "lon_min": min(all_lons),
                "lon_max": max(all_lons),
                "lat_center": (min(all_lats) + max(all_lats)) / 2,
                "lon_center": (min(all_lons) + max(all_lons)) / 2,
            }
        else:
            bounds = None

        approve = sum(1 for ve in voted_edges if ve["vote"] == "approve")
        reject = sum(1 for ve in voted_edges if ve["vote"] == "reject")

        views.append({
            "voter_id": voter_id,
            "session_count": len(bucket_sessions),
            "trip_count": sum(1 for s in bucket_sessions for t in s.trips
                              if t.line_id == line_id and t.computed_path is not None),
            "raw_paths": raw_paths,
            "cleaned_paths": cleaned_paths,
            "voted_edges": voted_edges,
            "voted_sections": voted_sections,
            "approve": approve,
            "reject": reject,
            "bounds": bounds,
        })

    return views


def load_real_voter_views(
    db: Session,
    line_id: UUID,
    route_id: UUID,
    *,
    voter_prefix: str = DEFAULT_VOTER_PREFIX,
) -> list[dict]:
    """Per-voter rendering payload for real-user vote minimaps.

    A real voter is any device that has cast at least one EdgeVote on this
    route and whose ``device_id`` does NOT start with ``voter_prefix + '-'``
    (so synthetic voters are filtered out). For each device we gather:

      * raw_paths: TripSession.computed_path coords for every session that
        device recorded on this line
      * cleaned_paths: Trip.computed_path coords for every cleaned trip
      * voted_edges: cumulative {path, vote, sequence, edge_id} for edges
        this device has voted on for this route. (Real users may have
        submitted multiple POSTs over time; this view shows the union.)
      * bounds: dict with lat/lon min-max for view-state framing, or None
    """
    voter_ids = (
        db.execute(
            select(EdgeVote.device_id)
            .distinct()
            .join(RouteEdge, RouteEdge.id == EdgeVote.edge_id)
            .where(
                RouteEdge.route_id == route_id,
                EdgeVote.device_id.notlike(f"{voter_prefix}-%"),
            )
            .order_by(EdgeVote.device_id)
        )
        .scalars()
        .all()
    )
    if not voter_ids:
        return []

    # Pre-fetch every relevant vote+edge in one query.
    rows = db.execute(
        select(EdgeVote, RouteEdge)
        .join(RouteEdge, RouteEdge.id == EdgeVote.edge_id)
        .where(
            RouteEdge.route_id == route_id,
            EdgeVote.device_id.in_(voter_ids),
        )
        .order_by(RouteEdge.sequence)
    ).all()
    votes_by_voter: dict[str, list[tuple]] = {}
    for vote_row, edge in rows:
        votes_by_voter.setdefault(vote_row.device_id, []).append((vote_row, edge))

    # Pre-fetch every relevant TripSession (with cleaned trips) for the line.
    sessions_by_voter: dict[str, list[TripSession]] = {}
    sessions = (
        db.execute(
            select(TripSession)
            .join(Trip, Trip.session_id == TripSession.id)
            .where(
                Trip.line_id == line_id,
                Trip.computed_path.isnot(None),
                TripSession.device_id.in_(voter_ids),
            )
            .order_by(TripSession.started_at, TripSession.id)
            .distinct()
        )
        .scalars()
        .all()
    )
    for s in sessions:
        sessions_by_voter.setdefault(s.device_id, []).append(s)

    views: list[dict] = []
    for voter_id in voter_ids:
        voter_votes = votes_by_voter.get(voter_id, [])
        if not voter_votes:
            continue
        voter_sessions = sessions_by_voter.get(voter_id, [])

        raw_paths = [
            _coords(s.computed_path)
            for s in voter_sessions
            if s.computed_path is not None
        ]
        raw_paths = [p for p in raw_paths if len(p) >= 2]

        cleaned_paths: list[list[list[float]]] = []
        for s in voter_sessions:
            for t in s.trips:
                if t.line_id == line_id and t.computed_path is not None:
                    coords = _coords(t.computed_path)
                    if len(coords) >= 2:
                        cleaned_paths.append(coords)

        voted_edges: list[dict] = []
        for vote_row, edge in voter_votes:
            coords = _coords(edge.path)
            if len(coords) < 2:
                continue
            voted_edges.append({
                "path": coords,
                "vote": vote_row.vote.value,
                "sequence": edge.sequence,
                "edge_id": str(edge.id),
            })

        # Group voted edges into contiguous sections
        voted_sections: list[dict] = []
        if voted_edges:
            sorted_ve = sorted(voted_edges, key=lambda x: x["sequence"])
            current_sec: list[dict] = [sorted_ve[0]]
            for ve in sorted_ve[1:]:
                if ve["sequence"] == current_sec[-1]["sequence"] + 1:
                    current_sec.append(ve)
                else:
                    voted_sections.append(_build_section_view(current_sec))
                    current_sec = [ve]
            voted_sections.append(_build_section_view(current_sec))

        all_lons: list[float] = []
        all_lats: list[float] = []
        for path in raw_paths + cleaned_paths:
            all_lons.extend(c[0] for c in path)
            all_lats.extend(c[1] for c in path)
        for ve in voted_edges:
            all_lons.extend(c[0] for c in ve["path"])
            all_lats.extend(c[1] for c in ve["path"])

        if all_lons and all_lats:
            bounds = {
                "lat_min": min(all_lats),
                "lat_max": max(all_lats),
                "lon_min": min(all_lons),
                "lon_max": max(all_lons),
                "lat_center": (min(all_lats) + max(all_lats)) / 2,
                "lon_center": (min(all_lons) + max(all_lons)) / 2,
            }
        else:
            bounds = None

        approve = sum(1 for ve in voted_edges if ve["vote"] == "approve")
        reject = sum(1 for ve in voted_edges if ve["vote"] == "reject")

        # Truncate display id so the title doesn't blow out the tile width.
        display_id = voter_id if len(voter_id) <= 16 else voter_id[:8] + "…" + voter_id[-4:]

        views.append({
            "voter_id": display_id,
            "full_voter_id": voter_id,
            "session_count": len(voter_sessions),
            "trip_count": sum(1 for s in voter_sessions for t in s.trips
                              if t.line_id == line_id and t.computed_path is not None),
            "raw_paths": raw_paths,
            "cleaned_paths": cleaned_paths,
            "voted_edges": voted_edges,
            "voted_sections": voted_sections,
            "approve": approve,
            "reject": reject,
            "bounds": bounds,
        })

    return views


def zoom_for_extent(lat_extent_deg: float, lon_extent_deg: float) -> int:
    """Heuristic zoom level (~deck.gl) for a bounding box in degrees."""
    extent = max(lat_extent_deg, lon_extent_deg, 1e-6)
    if extent < 0.002:
        return 16
    if extent < 0.005:
        return 15
    if extent < 0.01:
        return 14
    if extent < 0.02:
        return 13
    if extent < 0.05:
        return 12
    if extent < 0.1:
        return 11
    return 10
