"""Step 3: Combine segment centerlines into a full route estimation.

This module orchestrates the full Arman & Tampère pipeline:
1. Segment the network (Step 1).
2. Build the centerline for each segment (Step 2).
3. Concatenate segment centerlines into a single route.
4. Persist as RouteEstimation + RouteSegments.

The lane identification step from the original paper (Step 3: GMM) is
omitted here, as the goal is transit route reconstruction, not
lane-level mapping.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

import numpy as np
from geoalchemy2.shape import from_shape
from shapely.geometry import LineString
from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import (
    EstimationStatus,
    Line,
    RouteEstimation,
    RouteSegment,
)

from ...telemetry import tracer
from .centerline import CenterlineResult, build_centerline
from .segment import SegmentationResult, segment_network


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class ArmanTampereResult:
    """Full result of the Arman & Tampère reconstruction pipeline."""

    estimation: RouteEstimation
    segmentation: SegmentationResult
    centerlines: list[CenterlineResult]
    n_route_segments: int


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def reconstruct_route(
    db: Session,
    line_id: UUID,
    *,
    min_match_score: float | None = None,
    trip_ids: list[UUID] | None = None,
    # Step 1 params
    distance_threshold: float = 50.0,
    f_q: float = 0.035,
    f_q_prime: float = 0.027,
    # Step 2 params
    z_threshold: float = 1.96,
    s_prime: float = 0.60,
    dx_meters: float = 10.0,
) -> ArmanTampereResult:
    """Run the full Arman & Tampère reconstruction pipeline.

    Parameters
    ----------
    db:
        SQLAlchemy session.
    line_id:
        Transit line to reconstruct.
    min_match_score:
        Only include trips with match_score >= this value.
    trip_ids:
        Explicit allowlist of Trip IDs.
    distance_threshold:
        QuickBundles distance threshold (metres) for Step 1.
    f_q, f_q_prime:
        Incidence fractions for node detection in Step 1.
    z_threshold:
        Z-score for outlier removal in Step 2.
    s_prime:
        Minimum dissimilarity for pair selection in Step 2.
    dx_meters:
        Longitudinal sampling interval in Step 2.

    Returns
    -------
    ArmanTampereResult
    """
    with tracer.start_as_current_span(
        "arman_tampere.reconstruct_route",
        attributes={"line_id": str(line_id)},
    ):
        line = db.get(Line, line_id)
        if not line:
            raise ValueError(f"Line {line_id} not found")

        # ---- Step 1: Segment the network ----
        segmentation = segment_network(
            db,
            line_id,
            min_match_score=min_match_score,
            trip_ids=trip_ids,
            distance_threshold=distance_threshold,
            f_q=f_q,
            f_q_prime=f_q_prime,
        )

        # ---- Step 2: Build centerline for each segment ----
        centerlines: list[CenterlineResult] = []
        all_waypoints: list[tuple[float, float]] = []

        for segment in segmentation.segments:
            cl = build_centerline(
                segment,
                z_threshold=z_threshold,
                s_prime=s_prime,
                dx_meters=dx_meters,
            )
            centerlines.append(cl)

            for lat, lon in cl.points:
                all_waypoints.append((float(lat), float(lon)))

        if len(all_waypoints) < 2:
            raise ValueError(
                f"Not enough centerline waypoints for line {line_id}"
            )

        # ---- Step 3: Persist as RouteEstimation ----
        previous = db.execute(
            select(RouteEstimation).where(
                RouteEstimation.line_id == line_id,
                RouteEstimation.status != EstimationStatus.SUPERSEDED,
            )
        ).scalars().all()

        next_version = 1
        for prev in previous:
            if prev.version >= next_version:
                next_version = prev.version + 1
            prev.status = EstimationStatus.SUPERSEDED
            db.add(prev)

        estimation = RouteEstimation(
            line_id=line_id,
            version=next_version,
            status=EstimationStatus.PENDING,
            trip_count=segmentation.n_trajectories,
        )
        db.add(estimation)
        db.flush()

        n_route_segments = 0
        for seq, (wp_a, wp_b) in enumerate(
            zip(all_waypoints[:-1], all_waypoints[1:])
        ):
            path = from_shape(
                LineString([
                    (wp_a[1], wp_a[0]),  # (lon, lat)
                    (wp_b[1], wp_b[0]),
                ]),
                srid=4326,
            )
            db.add(
                RouteSegment(
                    estimation_id=estimation.id,
                    sequence=seq,
                    path=path,
                    confidence=1.0,
                )
            )
            n_route_segments += 1

        db.commit()

        return ArmanTampereResult(
            estimation=estimation,
            segmentation=segmentation,
            centerlines=centerlines,
            n_route_segments=n_route_segments,
        )
