"""Direction validation for resampled trips (pre-DBSCAN sanity check).

Detects whether all resampled trips for a line share a consistent travel
direction.  Mixed-direction batches must be split before DBSCAN clustering
or the centroid ordering step will produce a zigzag route.

Typical usage
-------------
    result = validate_trip_directions(db, line_id, interval_meters=20.0)
    if result.is_mixed:
        forward_ids = [t.resampled_trip_id for t in result.forward_trips]
        reverse_ids = [t.resampled_trip_id for t in result.reverse_trips]
"""

import math
from dataclasses import dataclass, field
from enum import Enum
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import Line, ResampledTrip, ResampledTripPoint, Trip

from .telemetry import tracer


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


class TripDirection(str, Enum):
    FORWARD = "forward"  # aligned with the dominant direction of the batch
    REVERSE = "reverse"  # opposite to dominant direction
    UNKNOWN = "unknown"  # trip too short or degenerate to classify


@dataclass
class TripDirectionResult:
    trip_id: UUID
    resampled_trip_id: UUID
    direction: TripDirection
    # Dot product with canonical forward vector (-1 to +1).
    # Values close to ±1 indicate a confident classification; near 0 is ambiguous.
    dot_score: float


@dataclass
class DirectionValidationResult:
    trips: list[TripDirectionResult] = field(default_factory=list)
    n_forward: int = 0
    n_reverse: int = 0
    n_unknown: int = 0
    # True when both FORWARD and REVERSE trips are present in the same batch.
    is_mixed: bool = False

    @property
    def forward_trips(self) -> list[TripDirectionResult]:
        return [t for t in self.trips if t.direction == TripDirection.FORWARD]

    @property
    def reverse_trips(self) -> list[TripDirectionResult]:
        return [t for t in self.trips if t.direction == TripDirection.REVERSE]


# ---------------------------------------------------------------------------
# Pure geometry helpers
# ---------------------------------------------------------------------------


def _start_end_vector(
    first: ResampledTripPoint,
    last: ResampledTripPoint,
    min_distance_m: float = 50.0,
) -> tuple[float, float] | None:
    """Return a normalised (east, north) direction vector for a trip.

    Uses only the first and last resampled points to avoid being confused by
    intermediate detours (e.g. bus stopping at a terminus loop).

    Returns None when start and end are closer than *min_distance_m* —
    the trip is too short (or a loop) to determine direction.
    """
    mean_lat = math.radians((first.latitude + last.latitude) / 2.0)
    east = (last.longitude - first.longitude) * 111_320.0 * math.cos(mean_lat)
    north = (last.latitude - first.latitude) * 111_320.0
    dist = math.sqrt(east**2 + north**2)
    if dist < min_distance_m:
        return None
    return east / dist, north / dist


def _canonical_forward(
    vectors: list[tuple[float, float]],
) -> tuple[float, float] | None:
    """Compute the dominant direction from a list of unit vectors.

    Resolves the 180° ambiguity (same road, two directions) by:
    1. Checking whether the majority of vectors agree with the first one.
    2. If not, flipping the reference so the majority becomes FORWARD.
    3. Returning the mean of all vectors aligned to that reference.

    Returns None if the input is empty or the mean degenerates to zero
    (perfectly balanced bidirectional batch with equal trip counts).
    """
    if not vectors:
        return None

    ref_e, ref_n = vectors[0]

    # Check majority polarity against the first vector.
    agree = sum(1 for e, n in vectors if e * ref_e + n * ref_n >= 0)
    if agree < len(vectors) - agree:
        # Minority agreed — flip so the majority becomes the reference.
        ref_e, ref_n = -ref_e, -ref_n

    # Align all vectors to the reference and average.
    aligned: list[tuple[float, float]] = []
    for e, n in vectors:
        if e * ref_e + n * ref_n >= 0:
            aligned.append((e, n))
        else:
            aligned.append((-e, -n))

    mean_e = sum(v[0] for v in aligned) / len(aligned)
    mean_n = sum(v[1] for v in aligned) / len(aligned)
    norm = math.sqrt(mean_e**2 + mean_n**2)
    if norm < 1e-9:
        return None
    return mean_e / norm, mean_n / norm


# ---------------------------------------------------------------------------
# DB-backed validation
# ---------------------------------------------------------------------------


def validate_trip_directions(
    db: Session,
    line_id: UUID,
    interval_meters: float,
    *,
    min_match_score: float | None = None,
    min_distance_m: float = 50.0,
    reverse_threshold: float = -0.1,
) -> DirectionValidationResult:
    """Classify every resampled trip for a line as FORWARD, REVERSE, or UNKNOWN.

    Parameters
    ----------
    db:
        SQLAlchemy session.
    line_id:
        Line whose resampled trips to validate.
    interval_meters:
        Resampling interval to target (must match an existing ResampledTrip batch).
    min_match_score:
        If provided, only trips resampled with this exact match-score filter are
        included — mirrors the dropdown selection in the notebook.
    min_distance_m:
        Trips whose start-to-end crow-fly distance is below this threshold are
        classified as UNKNOWN (too short to determine direction reliably).
    reverse_threshold:
        Dot-product cutoff below which a trip is labelled REVERSE (default -0.1,
        giving a ≈6° deadband around perpendicular to avoid false reversals on
        very short L-shaped partial trips).

    Returns
    -------
    DirectionValidationResult
        Per-trip classification plus aggregate counts and ``is_mixed`` flag.
    """
    with tracer.start_as_current_span(
        "validate_trip_directions",
        attributes={
            "line_id": str(line_id),
            "interval_meters": interval_meters,
        },
    ) as span:
        line = db.get(Line, line_id)
        if not line:
            raise ValueError(f"Line {line_id} not found")

        # Load all ResampledTrips for this (line, interval, score) combination.
        score_filter = (
            ResampledTrip.match_score.is_(None)
            if min_match_score is None
            else ResampledTrip.match_score == min_match_score
        )
        resampled_trips = db.execute(
            select(ResampledTrip)
            .join(Trip, ResampledTrip.trip_id == Trip.id)
            .where(
                Trip.line_id == line_id,
                ResampledTrip.interval_meters == interval_meters,
                score_filter,
            )
        ).scalars().all()

        span.set_attribute("trips.total", len(resampled_trips))

        if not resampled_trips:
            return DirectionValidationResult()

        # Load first and last points for each resampled trip.
        trip_endpoints: list[tuple[ResampledTrip, ResampledTripPoint, ResampledTripPoint]] = []
        for rt in resampled_trips:
            pts = db.execute(
                select(ResampledTripPoint)
                .where(ResampledTripPoint.resampled_trip_id == rt.id)
                .order_by(ResampledTripPoint.point_index)
            ).scalars().all()
            if len(pts) >= 2:
                trip_endpoints.append((rt, pts[0], pts[-1]))

        # Compute direction vectors for classifiable trips.
        vectors: list[tuple[float, float] | None] = [
            _start_end_vector(first, last, min_distance_m)
            for _, first, last in trip_endpoints
        ]
        valid_vectors = [v for v in vectors if v is not None]

        canonical = _canonical_forward(valid_vectors)

        result = DirectionValidationResult()

        for (rt, first, last), vec in zip(trip_endpoints, vectors):
            if vec is None or canonical is None:
                result.trips.append(
                    TripDirectionResult(
                        trip_id=rt.trip_id,
                        resampled_trip_id=rt.id,
                        direction=TripDirection.UNKNOWN,
                        dot_score=0.0,
                    )
                )
                result.n_unknown += 1
                continue

            dot = vec[0] * canonical[0] + vec[1] * canonical[1]
            if dot >= reverse_threshold:
                direction = TripDirection.FORWARD
                result.n_forward += 1
            else:
                direction = TripDirection.REVERSE
                result.n_reverse += 1

            result.trips.append(
                TripDirectionResult(
                    trip_id=rt.trip_id,
                    resampled_trip_id=rt.id,
                    direction=direction,
                    dot_score=round(dot, 4),
                )
            )

        result.is_mixed = result.n_forward > 0 and result.n_reverse > 0

        span.set_attributes({
            "trips.forward": result.n_forward,
            "trips.reverse": result.n_reverse,
            "trips.unknown": result.n_unknown,
            "trips.is_mixed": result.is_mixed,
        })

        return result
