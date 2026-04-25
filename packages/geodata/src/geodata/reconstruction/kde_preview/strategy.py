"""KDE density-ridge preview reconstruction strategy.

Inspired by Davies et al. (2006) as evaluated in Biagioni & Eriksson (2012).
Pools all pre-snapped trace points into a 2D density grid, smooths with a
Gaussian kernel, thresholds to isolate the transit corridor, extracts the
density ridge as a centerline, and optionally re-snaps to the road grid.
"""

import math
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import numpy as np
from scipy.ndimage import gaussian_filter, label

from .. import _road_grid
from ..base import ReconstructionResult, ReconstructionTrace

EARTH_RADIUS_M = 6_371_000.0

# Cap for MST ordering — keeps O(n^2) distance matrix tractable.
_MAX_RIDGE_POINTS = 1200


@dataclass(frozen=True)
class KDEDensityRidgePreviewStrategy:
    """Reconstruct a route by extracting the density ridge from a KDE of
    pre-snapped trace points (Davies-style approach)."""

    key: str = "kde_density_ridge_preview"
    label: str = "KDE density ridge (preview)"

    def default_params(self) -> dict[str, Any]:
        return {
            "cell_size_meters": 5.0,
            "bandwidth_meters": 15.0,
            "density_threshold": 0.15,
            "snap_costing": "bus",
            "snap_search_radius": 60,
            "snap_gps_accuracy": 20,
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
        cell_size = max(1.0, float(effective_params.get("cell_size_meters", 5.0)))
        bandwidth = max(1.0, float(effective_params.get("bandwidth_meters", 15.0)))
        threshold_frac = max(0.0, float(effective_params.get("density_threshold", 0.15)))
        snap_costing = str(effective_params.get("snap_costing", "bus")).strip() or "bus"
        snap_search_radius = int(effective_params.get("snap_search_radius", 60))
        snap_gps_accuracy = int(effective_params.get("snap_gps_accuracy", 20))

        # -- 1. Pool all trace points ------------------------------------------
        all_lons: list[float] = []
        all_lats: list[float] = []
        for trace in traces:
            for point in trace.points:
                all_lons.append(point.longitude)
                all_lats.append(point.latitude)

        n_points = len(all_lons)
        if n_points < 2:
            raise ValueError("At least 2 points are required for KDE reconstruction")

        # -- 2. Project to local metres ----------------------------------------
        ref_lon = sum(all_lons) / n_points
        ref_lat = sum(all_lats) / n_points
        xs, ys = _project_arrays(all_lons, all_lats, ref_lon, ref_lat)

        # -- 3. Build 2D histogram on a bounded grid --------------------------
        x_min, x_max = float(np.min(xs)), float(np.max(xs))
        y_min, y_max = float(np.min(ys)), float(np.max(ys))
        # Pad by 3x bandwidth so the Gaussian tails don't clip
        pad = 3 * bandwidth
        x_min -= pad
        x_max += pad
        y_min -= pad
        y_max += pad

        n_cols = max(1, int(math.ceil((x_max - x_min) / cell_size)))
        n_rows = max(1, int(math.ceil((y_max - y_min) / cell_size)))

        if n_rows * n_cols > 20_000_000:
            raise ValueError(
                f"Grid too large ({n_rows}x{n_cols}). "
                "Increase cell_size_meters or use fewer traces."
            )

        col_indices = np.clip(((xs - x_min) / cell_size).astype(int), 0, n_cols - 1)
        row_indices = np.clip(((ys - y_min) / cell_size).astype(int), 0, n_rows - 1)

        grid = np.zeros((n_rows, n_cols), dtype=np.float64)
        np.add.at(grid, (row_indices, col_indices), 1)

        # -- 4. Gaussian smooth ------------------------------------------------
        sigma = bandwidth / cell_size
        density = gaussian_filter(grid, sigma=sigma)
        max_density = float(np.max(density))
        if max_density <= 0:
            raise ValueError("Density grid is empty after smoothing")

        # -- 5. Threshold ------------------------------------------------------
        threshold = threshold_frac * max_density
        binary_mask = density >= threshold

        # -- 6. Largest connected component ------------------------------------
        labelled, n_components = label(binary_mask)
        if n_components == 0:
            raise ValueError(
                "No cells survived the density threshold. Try lowering "
                "density_threshold or increasing bandwidth_meters."
            )

        component_sizes = np.bincount(labelled.ravel())
        component_sizes[0] = 0  # ignore background
        largest_label = int(np.argmax(component_sizes))
        component_mask = labelled == largest_label

        # -- 7. Extract ridge points -------------------------------------------
        ridge_rows, ridge_cols, ridge_method = _extract_ridge(
            density, component_mask, cell_size
        )

        if len(ridge_rows) < 2:
            raise ValueError("Ridge extraction produced fewer than 2 points")

        # Convert grid indices back to metres
        ridge_xs = x_min + (ridge_cols + 0.5) * cell_size
        ridge_ys = y_min + (ridge_rows + 0.5) * cell_size

        # -- 8. Subsample if too many points -----------------------------------
        if len(ridge_xs) > _MAX_RIDGE_POINTS:
            ridge_xs, ridge_ys = _spatial_subsample(
                ridge_xs, ridge_ys, _MAX_RIDGE_POINTS, cell_size
            )

        # -- 9. Order via MST diameter -----------------------------------------
        ordered_xs, ordered_ys = _order_by_mst_diameter(ridge_xs, ridge_ys)

        # -- 10. Convert back to lon/lat ---------------------------------------
        route_coordinates = _unproject_to_lonlat(
            ordered_xs, ordered_ys, ref_lon, ref_lat
        )

        if len(route_coordinates) < 2:
            raise ValueError("Route reconstruction produced fewer than 2 coordinates")

        raw_route_points = len(route_coordinates)

        # -- 11. Snap to road grid ---------------------------------------------
        snapped_route_coordinates = _road_grid.snap_route_to_road_grid(
            route_coordinates,
            costing=snap_costing,
            search_radius=snap_search_radius,
            gps_accuracy=snap_gps_accuracy,
        )

        diagnostics: dict[str, int | float | str] = {
            "line_id": str(line_id),
            "trace_count": len(traces),
            "point_count": n_points,
            "grid_rows": n_rows,
            "grid_cols": n_cols,
            "max_density": round(max_density, 2),
            "density_threshold": round(threshold, 2),
            "threshold_fraction": threshold_frac,
            "cells_above_threshold": int(np.sum(binary_mask)),
            "largest_component_cells": int(np.sum(component_mask)),
            "connected_components": n_components,
            "ridge_points": len(ridge_xs),
            "ridge_method": ridge_method,
            "raw_route_points": raw_route_points,
            "route_points": len(snapped_route_coordinates),
            "cell_size_meters": cell_size,
            "bandwidth_meters": bandwidth,
            "snap_costing": snap_costing,
            "snap_search_radius": snap_search_radius,
            "snap_gps_accuracy": snap_gps_accuracy,
        }
        return ReconstructionResult(
            strategy_name=self.label,
            geojson={
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {
                            "strategy": self.label,
                            "line_id": str(line_id),
                            "trace_count": len(traces),
                            "point_count": n_points,
                            "ridge_method": ridge_method,
                            "snap_costing": snap_costing,
                        },
                        "geometry": {
                            "type": "LineString",
                            "coordinates": snapped_route_coordinates,
                        },
                    }
                ],
            },
            diagnostics=diagnostics,
        )


# ---------------------------------------------------------------------------
# Ridge extraction
# ---------------------------------------------------------------------------


def _extract_ridge(
    density: np.ndarray,
    component_mask: np.ndarray,
    cell_size: float,
) -> tuple[np.ndarray, np.ndarray, str]:
    """Extract the density ridge from the largest component.

    Combines both row-wise and column-wise slicing: for each occupied row,
    computes the density-weighted centroid column, and vice-versa.  The union
    of both point sets is deduplicated on a coarse grid so that straight
    segments and turns are both captured without double-counting.
    """
    row_r, row_c = _slice_ridge_along_rows(density, component_mask)
    col_r, col_c = _slice_ridge_along_cols(density, component_mask)

    # Merge and deduplicate on a coarse grid (1 cell tolerance)
    all_r = np.concatenate([row_r, col_r])
    all_c = np.concatenate([row_c, col_c])
    seen: set[tuple[int, int]] = set()
    unique_r: list[float] = []
    unique_c: list[float] = []
    for r, c in zip(all_r, all_c):
        key = (round(r), round(c))
        if key not in seen:
            seen.add(key)
            unique_r.append(float(r))
            unique_c.append(float(c))

    return np.array(unique_r), np.array(unique_c), "dual_slicing"


def _slice_ridge_along_cols(
    density: np.ndarray,
    mask: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """For each occupied column, compute the density-weighted centroid row."""
    col_indices = np.where(np.any(mask, axis=0))[0]
    ridge_rows = []
    ridge_cols = []
    for col in col_indices:
        col_mask = mask[:, col]
        occupied_rows = np.where(col_mask)[0]
        if len(occupied_rows) == 0:
            continue
        weights = density[occupied_rows, col]
        total_weight = np.sum(weights)
        if total_weight <= 0:
            centroid_row = float(np.mean(occupied_rows))
        else:
            centroid_row = float(np.sum(occupied_rows * weights) / total_weight)
        ridge_rows.append(centroid_row)
        ridge_cols.append(float(col))
    return np.array(ridge_rows), np.array(ridge_cols)


def _slice_ridge_along_rows(
    density: np.ndarray,
    mask: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """For each occupied row, compute the density-weighted centroid column."""
    row_indices = np.where(np.any(mask, axis=1))[0]
    ridge_rows = []
    ridge_cols = []
    for row in row_indices:
        row_mask = mask[row, :]
        occupied_cols = np.where(row_mask)[0]
        if len(occupied_cols) == 0:
            continue
        weights = density[row, occupied_cols]
        total_weight = np.sum(weights)
        if total_weight <= 0:
            centroid_col = float(np.mean(occupied_cols))
        else:
            centroid_col = float(np.sum(occupied_cols * weights) / total_weight)
        ridge_rows.append(float(row))
        ridge_cols.append(centroid_col)
    return np.array(ridge_rows), np.array(ridge_cols)


# ---------------------------------------------------------------------------
# Spatial subsampling
# ---------------------------------------------------------------------------


def _spatial_subsample(
    xs: np.ndarray,
    ys: np.ndarray,
    max_points: int,
    cell_size: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Reduce point count by merging into coarser grid cells."""
    factor = max(2, int(math.ceil(math.sqrt(len(xs) / max_points))))
    coarse_size = cell_size * factor
    keys: dict[tuple[int, int], list[int]] = {}
    for idx in range(len(xs)):
        key = (int(xs[idx] // coarse_size), int(ys[idx] // coarse_size))
        keys.setdefault(key, []).append(idx)

    sampled_xs = []
    sampled_ys = []
    for indices in keys.values():
        sampled_xs.append(float(np.mean(xs[indices])))
        sampled_ys.append(float(np.mean(ys[indices])))
    return np.array(sampled_xs), np.array(sampled_ys)


# ---------------------------------------------------------------------------
# MST diameter ordering
# ---------------------------------------------------------------------------


def _order_by_mst_diameter(
    xs: np.ndarray,
    ys: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Order 2D points along the MST diameter (longest path)."""
    n = len(xs)
    if n <= 2:
        return xs, ys

    # Pairwise distance matrix
    dx = xs[:, None] - xs[None, :]
    dy = ys[:, None] - ys[None, :]
    dist_matrix = np.sqrt(dx ** 2 + dy ** 2)

    # Prim's MST
    adjacency: dict[int, list[tuple[int, float]]] = {i: [] for i in range(n)}
    in_tree = np.zeros(n, dtype=bool)
    in_tree[0] = True
    min_edge = dist_matrix[0].copy()
    min_source = np.zeros(n, dtype=int)

    for _ in range(n - 1):
        min_edge[in_tree] = np.inf
        target = int(np.argmin(min_edge))
        source = int(min_source[target])
        weight = float(min_edge[target])
        in_tree[target] = True
        adjacency[source].append((target, weight))
        adjacency[target].append((source, weight))

        # Update candidate edges
        for j in range(n):
            if not in_tree[j] and dist_matrix[target, j] < min_edge[j]:
                min_edge[j] = dist_matrix[target, j]
                min_source[j] = target

    # Tree diameter: two BFS passes
    far_a, _, _ = _furthest_node(0, adjacency)
    far_b, _, parents = _furthest_node(far_a, adjacency)

    # Trace the diameter path
    path = []
    current = far_b
    while current != far_a:
        path.append(current)
        current = parents[current]
    path.append(far_a)
    path.reverse()

    return xs[path], ys[path]


def _furthest_node(
    start: int,
    adjacency: dict[int, list[tuple[int, float]]],
) -> tuple[int, float, dict[int, int]]:
    """BFS/DFS to find the furthest node from *start* in a tree."""
    parents = {start: start}
    distances = {start: 0.0}
    stack = [start]
    while stack:
        current = stack.pop()
        for neighbor, weight in adjacency[current]:
            if neighbor in distances:
                continue
            parents[neighbor] = current
            distances[neighbor] = distances[current] + weight
            stack.append(neighbor)
    furthest = max(distances, key=distances.get)  # type: ignore[arg-type]
    return furthest, distances[furthest], parents


# ---------------------------------------------------------------------------
# Coordinate projection helpers
# ---------------------------------------------------------------------------


def _project_arrays(
    lons: list[float],
    lats: list[float],
    ref_lon: float,
    ref_lat: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Project WGS-84 lon/lat arrays to local XY metres."""
    ref_lat_rad = math.radians(ref_lat)
    cos_lat = max(1e-9, math.cos(ref_lat_rad))
    lons_arr = np.array(lons)
    lats_arr = np.array(lats)
    xs = np.radians(lons_arr - ref_lon) * EARTH_RADIUS_M * cos_lat
    ys = np.radians(lats_arr - ref_lat) * EARTH_RADIUS_M
    return xs, ys


def _unproject_to_lonlat(
    xs: np.ndarray,
    ys: np.ndarray,
    ref_lon: float,
    ref_lat: float,
) -> list[list[float]]:
    """Convert local XY metres back to [lon, lat] pairs."""
    ref_lat_rad = math.radians(ref_lat)
    cos_lat = max(1e-9, math.cos(ref_lat_rad))
    lons = ref_lon + np.degrees(xs / (EARTH_RADIUS_M * cos_lat))
    lats = ref_lat + np.degrees(ys / EARTH_RADIUS_M)
    return [[float(lon), float(lat)] for lon, lat in zip(lons, lats)]
