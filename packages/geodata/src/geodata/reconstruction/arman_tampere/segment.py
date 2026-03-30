"""Step 1: Network segmentation — bundle trajectories and identify nodes.

This module implements the first step of the Arman & Tampère pipeline:
identify trajectory bundles, detect merge/diverge nodes, and split the
network into homogeneous segments.

A *bundle* is a set of trajectories that follow the same path through
the network.  The original paper uses QuickBundles (QB) clustering,
which was designed for diffusion MRI streamlines but works well on
2-D trajectory data when the third dimension is set to zero.

Nodes are points where bundles merge or diverge.  Upstream of a diverge
the incidence rate (trajectories entering per distance unit) is stable
at Q; it drops to zero at the diverge point.  Symmetrically for merges.

References
----------
- QuickBundles: Garyfallidis et al., 2012 (originally for 3-D MRI)
- Fréchet distance for incidence detection: Arman & Tampère §4.1
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

import numpy as np
from sqlalchemy.orm import Session

from ...telemetry import tracer


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class Trajectory:
    """A cleaned trajectory as a sequence of (lat, lon) points."""

    trip_id: UUID
    points: np.ndarray  # shape (N, 2) — each row is (lat, lon)


@dataclass
class Node:
    """A merge or diverge point in the trajectory network."""

    lat: float
    lon: float
    node_type: str  # "merge" | "diverge"


@dataclass
class Segment:
    """A homogeneous, unidirectional road segment between two nodes."""

    start_node: Node | None  # None = network boundary
    end_node: Node | None
    trajectories: list[Trajectory]


@dataclass
class SegmentationResult:
    """Output of the network segmentation step."""

    segments: list[Segment]
    nodes: list[Node]
    n_trajectories: int
    n_bundles: int


# ---------------------------------------------------------------------------
# Bundle detection
# ---------------------------------------------------------------------------


def _bundle_trajectories(
    trajectories: list[Trajectory],
    *,
    distance_threshold: float = 50.0,
) -> list[list[int]]:
    """Group trajectories into bundles based on shape similarity.

    Uses a simplified QuickBundles-like approach: iteratively assign
    each trajectory to the nearest existing bundle centroid (measured by
    discrete Fréchet distance), or create a new bundle if the distance
    exceeds ``distance_threshold`` (in metres).

    Parameters
    ----------
    trajectories:
        Cleaned trajectory objects.
    distance_threshold:
        Maximum Fréchet distance (metres) for a trajectory to join an
        existing bundle.

    Returns
    -------
    List of bundles, where each bundle is a list of trajectory indices.
    """
    # TODO: implement QuickBundles clustering
    # For now, return all trajectories in a single bundle
    return [list(range(len(trajectories)))]


# ---------------------------------------------------------------------------
# Node detection
# ---------------------------------------------------------------------------


def _detect_nodes(
    trajectories: list[Trajectory],
    bundles: list[list[int]],
    *,
    f_q: float = 0.035,
    f_q_prime: float = 0.027,
) -> list[Node]:
    """Identify merge/diverge nodes from incidence rate changes.

    At a diverge, the incidence count Q drops from a stable value to
    zero.  The point at fraction ``f_q`` of Q is taken as the diverge
    location.  Symmetrically for merges with ``f_q_prime``.

    Parameters
    ----------
    trajectories:
        All trajectories in the network.
    bundles:
        Bundle assignments from ``_bundle_trajectories``.
    f_q:
        Fraction of the stable diverge incidence count used to locate
        the diverge point (paper default: 0.035).
    f_q_prime:
        Fraction for merge detection (paper default: 0.027).

    Returns
    -------
    List of detected Node objects.
    """
    # TODO: implement incidence-based node detection
    return []


# ---------------------------------------------------------------------------
# Segmentation
# ---------------------------------------------------------------------------


def _cut_segments(
    trajectories: list[Trajectory],
    nodes: list[Node],
) -> list[Segment]:
    """Split trajectories at the detected nodes into segments.

    Each segment is a contiguous stretch of trajectories between two
    consecutive nodes (or between a node and a network boundary).

    Returns
    -------
    List of Segment objects.
    """
    # TODO: implement trajectory cutting at nodes
    # For now, return a single segment containing all trajectories
    return [
        Segment(
            start_node=None,
            end_node=None,
            trajectories=trajectories,
        )
    ]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def segment_network(
    db: Session,
    line_id: UUID,
    *,
    min_match_score: float | None = None,
    trip_ids: list[UUID] | None = None,
    distance_threshold: float = 50.0,
    f_q: float = 0.035,
    f_q_prime: float = 0.027,
) -> SegmentationResult:
    """Run Step 1: segment the trajectory network for a line.

    Loads cleaned trips from the database, bundles them, detects
    merge/diverge nodes, and splits into homogeneous segments.

    Parameters
    ----------
    db:
        SQLAlchemy session.
    line_id:
        Transit line to process.
    min_match_score:
        Only include trips with ``match_score >= min_match_score``.
    trip_ids:
        Explicit allowlist of Trip IDs (overrides min_match_score).
    distance_threshold:
        QuickBundles distance threshold in metres.
    f_q, f_q_prime:
        Incidence fractions for node detection.

    Returns
    -------
    SegmentationResult
    """
    from geoalchemy2.shape import to_shape
    from sqlalchemy import select

    from database.models import Trip

    with tracer.start_as_current_span(
        "arman_tampere.segment_network",
        attributes={"line_id": str(line_id)},
    ):
        # Load trips (reuse the same loading logic as DBSCAN)
        q = select(Trip).where(
            Trip.line_id == line_id,
            Trip.computed_path.is_not(None),
        )
        if trip_ids is not None:
            q = select(Trip).where(Trip.id.in_(trip_ids))
        elif min_match_score is not None:
            q = q.where(Trip.match_score >= min_match_score)

        trips = db.execute(q).scalars().all()
        if not trips:
            raise ValueError(f"No clean trips found for line {line_id}")

        # Convert to Trajectory objects
        trajectories: list[Trajectory] = []
        for trip in trips:
            geom = to_shape(trip.computed_path)
            coords = np.array(
                [(c[1], c[0]) for c in geom.coords]  # (lat, lon)
            )
            trajectories.append(Trajectory(trip_id=trip.id, points=coords))

        # Bundle → detect nodes → cut segments
        bundles = _bundle_trajectories(
            trajectories, distance_threshold=distance_threshold
        )
        nodes = _detect_nodes(
            trajectories, bundles, f_q=f_q, f_q_prime=f_q_prime
        )
        segments = _cut_segments(trajectories, nodes)

        return SegmentationResult(
            segments=segments,
            nodes=nodes,
            n_trajectories=len(trajectories),
            n_bundles=len(bundles),
        )
