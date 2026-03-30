"""Step 2: Centerline construction via Fréchet distance.

For each homogeneous segment, compute a road centerline by:

1. Computing a pairwise Fréchet distance matrix between all trajectories.
2. Normalising into a dissimilarity score S_FD (Eq. 1 in the paper).
3. Removing outlier trajectories (z-score > 1.96 on the dissimilarity).
4. Selecting the most dissimilar pairs (outermost trajectories) with
   dissimilarity threshold S'.
5. For each selected pair, computing lateral midpoints at regular Dx
   intervals along the segment.
6. Averaging the midpoints to get an initial centerline.
7. Smoothing the centerline iteratively (CL_Smoother, Fig. 6).

References
----------
- Fréchet distance: Eiter & Mannila, 1994
- Dissimilarity score: Arman & Tampère Eq. 1
- CL_Smoother: Arman & Tampère §4.2, Pseudo Code 1
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ...geo_math import haversine_m
from ...telemetry import tracer
from .segment import Segment, Trajectory


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class CenterlineResult:
    """Output of centerline construction for a single segment."""

    points: np.ndarray  # shape (M, 2) — (lat, lon) centerline waypoints
    n_trajectories_used: int
    n_outliers_removed: int
    n_pairs_selected: int


# ---------------------------------------------------------------------------
# Fréchet distance
# ---------------------------------------------------------------------------


def frechet_distance(P: np.ndarray, Q: np.ndarray) -> float:
    """Compute the discrete Fréchet distance between two trajectories.

    Uses an iterative (bottom-up DP) approach — O(n*m) time and memory,
    no recursion limit issues.

    Parameters
    ----------
    P, Q:
        Arrays of shape (n, 2) and (m, 2) with (lat, lon) coordinates.

    Returns
    -------
    Discrete Fréchet distance in metres.
    """
    n, m = len(P), len(Q)

    # Pre-compute all pairwise distances using vectorised haversine
    _R = 6_371_000.0
    P_rad = np.radians(P)
    Q_rad = np.radians(Q)
    # Shape (n, 1, 2) vs (1, m, 2)
    dlat = P_rad[:, None, 0] - Q_rad[None, :, 0]
    dlon = P_rad[:, None, 1] - Q_rad[None, :, 1]
    a = (
        np.sin(dlat / 2) ** 2
        + np.cos(P_rad[:, None, 0]) * np.cos(Q_rad[None, :, 0]) * np.sin(dlon / 2) ** 2
    )
    dist = 2 * _R * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))

    # Bottom-up DP
    ca = np.empty((n, m))
    ca[0, 0] = dist[0, 0]
    for i in range(1, n):
        ca[i, 0] = max(ca[i - 1, 0], dist[i, 0])
    for j in range(1, m):
        ca[0, j] = max(ca[0, j - 1], dist[0, j])
    for i in range(1, n):
        for j in range(1, m):
            ca[i, j] = max(
                min(ca[i - 1, j], ca[i - 1, j - 1], ca[i, j - 1]),
                dist[i, j],
            )
    return float(ca[n - 1, m - 1])


# ---------------------------------------------------------------------------
# Dissimilarity matrix
# ---------------------------------------------------------------------------


def compute_dissimilarity_matrix(
    trajectories: list[Trajectory],
) -> np.ndarray:
    """Pairwise normalised Fréchet dissimilarity (Eq. 1).

    Returns an (n, n) matrix where entry (i, j) is:

        S_FD(i,j) = (D_ij - min(D)) / (max(D) - min(D))

    with D_ij = frechet_distance(traj_i, traj_j).
    """
    n = len(trajectories)
    D = np.zeros((n, n))

    for i in range(n):
        for j in range(i + 1, n):
            d = frechet_distance(trajectories[i].points, trajectories[j].points)
            D[i, j] = d
            D[j, i] = d

    d_min = D[D > 0].min() if np.any(D > 0) else 0.0
    d_max = D.max()
    denom = d_max - d_min
    if denom < 1e-9:
        return np.zeros((n, n))

    S = (D - d_min) / denom
    np.fill_diagonal(S, 0.0)
    return S


# ---------------------------------------------------------------------------
# Outlier removal
# ---------------------------------------------------------------------------


def remove_outlier_trajectories(
    trajectories: list[Trajectory],
    S: np.ndarray,
    *,
    z_threshold: float = 1.96,
) -> tuple[list[Trajectory], list[int]]:
    """Remove trajectories whose mean dissimilarity is a z-score outlier.

    The paper removes trajectories with z-score > 1.96 on their row
    mean in the dissimilarity matrix (roughly 4.56% of trajectories).

    Returns
    -------
    (kept_trajectories, removed_indices)
    """
    row_means = S.mean(axis=1)
    mu = row_means.mean()
    sigma = row_means.std()
    if sigma < 1e-9:
        return list(trajectories), []

    z_scores = (row_means - mu) / sigma
    kept = []
    removed = []
    for i, z in enumerate(z_scores):
        if abs(z) > z_threshold:
            removed.append(i)
        else:
            kept.append(trajectories[i])

    return kept, removed


# ---------------------------------------------------------------------------
# Pair selection & midpoint centerline
# ---------------------------------------------------------------------------


def select_dissimilar_pairs(
    trajectories: list[Trajectory],
    S: np.ndarray,
    *,
    s_prime: float = 0.60,
) -> list[tuple[int, int]]:
    """Select pairs of trajectories with high dissimilarity (>= s_prime).

    These are the outermost trajectory pairs — they mark the lateral
    extremes of the road.  The centerline is approximated as the
    midpoint between each such pair.

    Each trajectory can only appear in one pair (the one with the
    highest dissimilarity).
    """
    n = len(trajectories)
    candidates = []
    for i in range(n):
        for j in range(i + 1, n):
            if S[i, j] >= s_prime:
                candidates.append((i, j, S[i, j]))

    # Sort by dissimilarity descending, greedily assign
    candidates.sort(key=lambda x: x[2], reverse=True)
    used: set[int] = set()
    pairs = []
    for i, j, _ in candidates:
        if i not in used and j not in used:
            pairs.append((i, j))
            used.add(i)
            used.add(j)

    return pairs


def compute_midpoint_centerline(
    pairs: list[tuple[int, int]],
    trajectories: list[Trajectory],
    *,
    dx_meters: float = 10.0,
) -> np.ndarray:
    """Compute the initial centerline from midpoints of selected pairs.

    For each pair of trajectories, sample them at longitudinal intervals
    of ``dx_meters``, compute the lateral midpoint at each sample, then
    average across all pairs.

    Parameters
    ----------
    pairs:
        Index pairs from ``select_dissimilar_pairs``.
    trajectories:
        Trajectory objects (after outlier removal).
    dx_meters:
        Longitudinal sampling interval (paper default: 10 m).

    Returns
    -------
    Array of shape (M, 2) — (lat, lon) centerline waypoints.
    """
    if not pairs:
        # Fallback: use the centroid of all trajectories
        all_pts = np.vstack([t.points for t in trajectories])
        return all_pts.mean(axis=0, keepdims=True)

    # TODO: implement proper longitudinal sampling + lateral midpoint
    # computation as described in the paper (§4.2, Fig. 5).
    #
    # For now, a simplified version: for each pair, compute pointwise
    # midpoints after resampling both trajectories to the same number
    # of points.
    midpoint_sets: list[np.ndarray] = []
    for i, j in pairs:
        P = trajectories[i].points
        Q = trajectories[j].points
        # Resample to the same number of points (simple approach)
        n_samples = max(len(P), len(Q))
        P_resampled = _resample_to_n(P, n_samples)
        Q_resampled = _resample_to_n(Q, n_samples)
        midpoints = (P_resampled + Q_resampled) / 2.0
        midpoint_sets.append(midpoints)

    # Average across all pairs
    max_len = max(len(m) for m in midpoint_sets)
    # Resample all midpoint sets to the same length, then average
    resampled = np.stack(
        [_resample_to_n(m, max_len) for m in midpoint_sets]
    )
    return resampled.mean(axis=0)


def _resample_to_n(points: np.ndarray, n: int) -> np.ndarray:
    """Linearly resample a trajectory to exactly n points."""
    if len(points) == n:
        return points
    old_t = np.linspace(0, 1, len(points))
    new_t = np.linspace(0, 1, n)
    lat = np.interp(new_t, old_t, points[:, 0])
    lon = np.interp(new_t, old_t, points[:, 1])
    return np.column_stack([lat, lon])


# ---------------------------------------------------------------------------
# Centerline smoother (Pseudo Code 1 from the paper)
# ---------------------------------------------------------------------------


def smooth_centerline(
    points: np.ndarray,
    *,
    small_threshold: float = 1e-4,
) -> np.ndarray:
    """Smooth the centerline using the CL_Smoother algorithm (Fig. 6).

    Iteratively adjusts points where the heading sign changes relative
    to their neighbours (i.e. sharp kinks), averaging the heading with
    adjacent points until convergence.

    Parameters
    ----------
    points:
        Array of shape (M, 2) — (lat, lon) centerline points.
    small_threshold:
        Convergence threshold (maximum angular correction in radians).

    Returns
    -------
    Smoothed array of shape (M, 2).
    """
    result = points.copy()
    n = len(result)
    if n < 3:
        return result

    epsilon = float("inf")
    while epsilon >= small_threshold:
        epsilon = 0.0
        for w in range(1, n - 1):
            # Compute headings to previous and next points
            theta_w = np.arctan2(
                result[w + 1, 1] - result[w, 1],
                result[w + 1, 0] - result[w, 0],
            )
            theta_prev = np.arctan2(
                result[w, 1] - result[w - 1, 1],
                result[w, 0] - result[w - 1, 0],
            )

            sign_w = np.sign(np.pi - theta_w)  # heading sign
            sign_prev = np.sign(np.pi - theta_prev)

            # Check if heading sign differs from both neighbours
            if w + 1 < n:
                theta_next = np.arctan2(
                    result[min(w + 2, n - 1), 1] - result[w + 1, 1],
                    result[min(w + 2, n - 1), 0] - result[w + 1, 0],
                )
                sign_next = np.sign(np.pi - theta_next)
            else:
                sign_next = sign_w

            if sign_w != sign_prev and sign_w != sign_next:
                # Average heading with neighbours
                theta_new = (theta_prev + theta_w) / 2.0
                correction = abs(theta_new - theta_w)
                epsilon = max(epsilon, correction)
                # Adjust point position slightly toward the smoothed heading
                dist_prev = haversine_m(
                    result[w - 1, 0], result[w - 1, 1],
                    result[w, 0], result[w, 1],
                )
                result[w, 0] = result[w - 1, 0] + dist_prev * np.cos(theta_new)
                result[w, 1] = result[w - 1, 1] + dist_prev * np.sin(theta_new)

    return result


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def build_centerline(
    segment: Segment,
    *,
    z_threshold: float = 1.96,
    s_prime: float = 0.60,
    dx_meters: float = 10.0,
) -> CenterlineResult:
    """Run Step 2: build the centerline for one segment.

    Parameters
    ----------
    segment:
        A Segment from Step 1 (network segmentation).
    z_threshold:
        Z-score threshold for outlier trajectory removal.
    s_prime:
        Minimum normalised dissimilarity for pair selection.
    dx_meters:
        Longitudinal sampling interval for midpoint computation.

    Returns
    -------
    CenterlineResult
    """
    with tracer.start_as_current_span("arman_tampere.build_centerline"):
        trajectories = segment.trajectories
        n_total = len(trajectories)

        # Dissimilarity matrix
        S = compute_dissimilarity_matrix(trajectories)

        # Remove outliers
        kept, removed_idx = remove_outlier_trajectories(
            trajectories, S, z_threshold=z_threshold
        )

        if len(kept) < 2:
            # Not enough trajectories after outlier removal — use all
            kept = list(trajectories)
            removed_idx = []
            S_kept = S
        else:
            # Recompute dissimilarity for kept trajectories
            S_kept = compute_dissimilarity_matrix(kept)

        # Select outermost pairs
        pairs = select_dissimilar_pairs(kept, S_kept, s_prime=s_prime)

        # Compute midpoint centerline
        raw_centerline = compute_midpoint_centerline(
            pairs, kept, dx_meters=dx_meters
        )

        # Smooth
        centerline = smooth_centerline(raw_centerline)

        return CenterlineResult(
            points=centerline,
            n_trajectories_used=len(kept),
            n_outliers_removed=len(removed_idx),
            n_pairs_selected=len(pairs),
        )
