"""End-to-end evaluation helpers for route reconstruction strategies."""

import json
import math
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from shapely.geometry import LineString, MultiLineString, Point
from sqlalchemy import select

from .geo_math import haversine_m, interpolate_route
from .geojson import parse_route_from_geojson
from .reconstruction import (
    MatchedEdgeRef,
    ReconstructionPoint,
    ReconstructionStrategy,
    ReconstructionTrace,
    get_reconstruction_strategies,
)

EARTH_RADIUS_M = 6_371_000.0


@dataclass(frozen=True)
class ReconstructionEvaluationRun:
    """One end-to-end strategy evaluation run."""

    strategy_key: str
    strategy_label: str
    run_index: int
    seed: int
    trace_count: int
    frechet_distance_m: float | None
    coverage: float | None
    reconstructed_route_points: int | None
    error: str | None = None


@dataclass(frozen=True)
class ReconstructionEvaluationSummary:
    """Aggregated evaluation metrics for one strategy."""

    strategy_key: str
    strategy_label: str
    run_count: int
    success_count: int
    failure_count: int
    mean_frechet_distance_m: float | None
    mean_coverage: float | None
    runs: list[ReconstructionEvaluationRun]


@dataclass(frozen=True)
class ReconstructionEvaluationSuite:
    """Evaluation suite output across multiple strategies."""

    route_file: str
    line_id: str | None
    trace_source: str
    interval_meters: float | None
    route_points: int
    runs_per_strategy: int
    trace_count: int
    summaries: list[ReconstructionEvaluationSummary]


def build_evaluation_simulation_config(
    *,
    traces_per_run: int,
    mean_trace_proportion: float = 0.3,
    stddev_trace_proportion: float = 0.2,
) -> dict[str, Any]:
    """Return a moderate-noise simulation config suitable for evaluation."""

    return {
        "sim_params": {
            "Number of tracks": traces_per_run,
            "Sampling rate (s)": 2.0,
            "Base speed (m/s)": 8.0,
            "Speed jitter (%)": 12.0,
            "Target pts/track (0=auto)": 0,
            "Mean trace proportion (0-1)": mean_trace_proportion,
            "Stddev trace proportion": stddev_trace_proportion,
        },
        "noise": {
            "gaussian": {"Enabled": True, "Sigma (m)": 4.0},
            "perpendicular": {"Enabled": True, "Sigma (m)": 3.0},
            "zigzag": {"Enabled": False, "Amplitude (m)": 1.5, "Period (points)": 8},
            "jumps": {"Enabled": False, "Probability": 0.02, "Distance (m)": 40.0},
            "missing": {"Enabled": True, "Probability": 0.03},
            "biased_drift": {"Enabled": False, "Drift (m/pt)": 0.05, "Bearing (deg)": 70.0},
            "lateral_drift": {"Enabled": False, "Total (m)": 3.0},
            "timestamp_jitter": {"Enabled": True, "Sigma (s)": 0.15},
        },
    }


def simulated_records_to_traces(records: list[dict[str, Any]]) -> list[ReconstructionTrace]:
    """Convert simulator output rows into reconstruction traces."""

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[str(record["track_id"])].append(record)

    traces: list[ReconstructionTrace] = []
    for trace_id, trace_records in sorted(grouped.items(), key=lambda item: item[0]):
        points = [
            ReconstructionPoint(
                longitude=float(record["longitude"]),
                latitude=float(record["latitude"]),
                point_index=int(record["point_index"]),
                timestamp=datetime.fromisoformat(record["timestamp"]),
            )
            for record in sorted(trace_records, key=lambda row: int(row["point_index"]))
        ]
        traces.append(ReconstructionTrace(trace_id=trace_id, points=points))
    return traces


def extract_linestring_coordinates(geojson: dict[str, Any]) -> list[list[list[float]]]:
    """Extract all LineString coordinates from a GeoJSON payload."""

    lines: list[list[list[float]]] = []

    def _visit(node: Any) -> None:
        if not isinstance(node, dict):
            return

        node_type = node.get("type")
        if node_type == "FeatureCollection":
            for feature in node.get("features", []):
                _visit(feature)
            return
        if node_type == "Feature":
            _visit(node.get("geometry"))
            return
        if node_type == "LineString":
            coords = [
                [float(coord[0]), float(coord[1])]
                for coord in node.get("coordinates", [])
                if isinstance(coord, (list, tuple)) and len(coord) >= 2
            ]
            if len(coords) >= 2:
                lines.append(coords)
            return
        if node_type == "MultiLineString":
            for line in node.get("coordinates", []):
                coords = [
                    [float(coord[0]), float(coord[1])]
                    for coord in line
                    if isinstance(coord, (list, tuple)) and len(coord) >= 2
                ]
                if len(coords) >= 2:
                    lines.append(coords)

    _visit(geojson)
    return lines


def primary_linestring_coordinates(geojson: dict[str, Any]) -> list[list[float]]:
    """Return the longest LineString extracted from GeoJSON."""

    lines = extract_linestring_coordinates(geojson)
    if not lines:
        raise ValueError("Reconstruction output does not contain a LineString geometry")
    return max(lines, key=_route_length_m)


def discrete_frechet_distance_m(
    expected_route: list[list[float]],
    candidate_route: list[list[float]],
) -> float:
    """Compute the discrete Fréchet distance in metres."""

    expected_xy = _project_route_to_meters(expected_route)
    candidate_xy = _project_route_to_meters(candidate_route, reference=expected_route)

    cache: list[list[float]] = [
        [-1.0 for _ in range(len(candidate_xy))]
        for _ in range(len(expected_xy))
    ]

    for i in range(len(expected_xy)):
        for j in range(len(candidate_xy)):
            distance = _euclidean_m(expected_xy[i], candidate_xy[j])
            if i == 0 and j == 0:
                cache[i][j] = distance
            elif i == 0:
                cache[i][j] = max(cache[i][j - 1], distance)
            elif j == 0:
                cache[i][j] = max(cache[i - 1][j], distance)
            else:
                cache[i][j] = max(
                    min(cache[i - 1][j], cache[i - 1][j - 1], cache[i][j - 1]),
                    distance,
                )

    return cache[-1][-1]


def coverage_score(
    expected_route: list[list[float]],
    reconstructed_geojson: dict[str, Any],
    *,
    coverage_step_meters: float = 10.0,
    coverage_tolerance_meters: float = 25.0,
) -> float:
    """Score what fraction of the expected route lies near reconstructed geometry."""

    reconstructed_lines = extract_linestring_coordinates(reconstructed_geojson)
    if not reconstructed_lines:
        raise ValueError("Reconstruction output does not contain any line geometry")

    reference_lon, reference_lat = _reference_lon_lat(expected_route)
    sampled_route = interpolate_route(expected_route, max(1.0, coverage_step_meters))
    if len(sampled_route) < 2:
        sampled_route = expected_route

    geometries = [
        LineString(_project_route_to_meters(line, reference=(reference_lon, reference_lat)))
        for line in reconstructed_lines
    ]
    merged_geometry = (
        geometries[0]
        if len(geometries) == 1
        else MultiLineString([list(geometry.coords) for geometry in geometries])
    )

    covered = 0
    for lon, lat in sampled_route:
        point = Point(_project_point_to_meters(lon, lat, reference_lon, reference_lat))
        if merged_geometry.distance(point) <= coverage_tolerance_meters:
            covered += 1

    return covered / len(sampled_route)


def evaluate_reconstruction_suite(
    route_file: str | Path,
    *,
    line_id: UUID | str | None = None,
    trace_source: str = "cleaned",
    interval_meters: float | None = None,
    min_match_score: float | None = None,
    traces: list[ReconstructionTrace] | None = None,
    strategy_keys: list[str] | None = None,
    strategy_params: dict[str, dict[str, Any]] | None = None,
    runs_per_strategy: int = 1,
    coverage_step_meters: float = 10.0,
    coverage_tolerance_meters: float = 25.0,
    strategies: dict[str, ReconstructionStrategy] | None = None,
) -> ReconstructionEvaluationSuite:
    """Reconstruct routes from DB-backed cleaned traces and score the outputs."""

    route_path = Path(route_file).expanduser()
    route = parse_route_from_geojson(route_path.read_text(encoding="utf-8"))
    if len(route) < 2:
        raise ValueError("Route file must contain at least 2 coordinates")

    available_strategies = strategies or get_reconstruction_strategies()
    selected_keys = strategy_keys or list(available_strategies.keys())
    requested_params = strategy_params or {}
    source_traces = traces or load_reconstruction_traces_from_db(
        line_id=_coerce_uuid(line_id, field_name="line_id"),
        trace_source=trace_source,
        interval_meters=interval_meters,
        min_match_score=min_match_score,
    )
    if not source_traces:
        raise ValueError("No traces available for evaluation")

    summaries: list[ReconstructionEvaluationSummary] = []
    for strategy_key in selected_keys:
        if strategy_key not in available_strategies:
            raise ValueError(f"Unknown reconstruction strategy: {strategy_key}")

        strategy = available_strategies[strategy_key]
        runs: list[ReconstructionEvaluationRun] = []
        for run_index in range(runs_per_strategy):
            run_seed = run_index
            params = dict(requested_params.get(strategy_key, {}))
            if strategy_key == "route_file_preview":
                params.setdefault("route_file", str(route_path))

            try:
                result = strategy.reconstruct(uuid4(), source_traces, params=params)
                reconstructed_route = primary_linestring_coordinates(result.geojson)
                runs.append(
                    ReconstructionEvaluationRun(
                        strategy_key=strategy_key,
                        strategy_label=strategy.label,
                        run_index=run_index,
                        seed=run_seed,
                        trace_count=len(source_traces),
                        frechet_distance_m=discrete_frechet_distance_m(route, reconstructed_route),
                        coverage=coverage_score(
                            route,
                            result.geojson,
                            coverage_step_meters=coverage_step_meters,
                            coverage_tolerance_meters=coverage_tolerance_meters,
                        ),
                        reconstructed_route_points=len(reconstructed_route),
                    )
                )
            except Exception as exc:
                runs.append(
                    ReconstructionEvaluationRun(
                        strategy_key=strategy_key,
                        strategy_label=strategy.label,
                        run_index=run_index,
                        seed=run_seed,
                        trace_count=len(source_traces),
                        frechet_distance_m=None,
                        coverage=None,
                        reconstructed_route_points=None,
                        error=str(exc),
                    )
                )

        successful_runs = [run for run in runs if run.error is None]
        mean_frechet = (
            sum(run.frechet_distance_m for run in successful_runs if run.frechet_distance_m is not None)
            / len(successful_runs)
            if successful_runs
            else None
        )
        mean_coverage = (
            sum(run.coverage for run in successful_runs if run.coverage is not None)
            / len(successful_runs)
            if successful_runs
            else None
        )
        summaries.append(
            ReconstructionEvaluationSummary(
                strategy_key=strategy_key,
                strategy_label=strategy.label,
                run_count=len(runs),
                success_count=len(successful_runs),
                failure_count=len(runs) - len(successful_runs),
                mean_frechet_distance_m=mean_frechet,
                mean_coverage=mean_coverage,
                runs=runs,
            )
        )

    return ReconstructionEvaluationSuite(
        route_file=str(route_path),
        line_id=str(line_id) if line_id is not None else None,
        trace_source=trace_source,
        interval_meters=interval_meters,
        route_points=len(route),
        runs_per_strategy=runs_per_strategy,
        trace_count=len(source_traces),
        summaries=summaries,
    )


def suite_to_dict(suite: ReconstructionEvaluationSuite) -> dict[str, Any]:
    """Convert a suite dataclass tree into plain JSON-friendly dicts."""

    return asdict(suite)


def load_strategy_params(path: str | Path) -> dict[str, dict[str, Any]]:
    """Load strategy parameter overrides from a JSON file."""

    payload = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Strategy params file must contain a JSON object")

    parsed: dict[str, dict[str, Any]] = {}
    for strategy_key, params in payload.items():
        if not isinstance(strategy_key, str) or not isinstance(params, dict):
            raise ValueError("Strategy params must map strategy keys to JSON objects")
        parsed[strategy_key] = params
    return parsed


def load_reconstruction_traces_from_db(
    *,
    line_id: UUID,
    trace_source: str = "cleaned",
    interval_meters: float | None = None,
    min_match_score: float | None = None,
) -> list[ReconstructionTrace]:
    """Load cleaned or resampled traces for a line from the database."""

    from database.connection import SessionLocal
    from database.models import (
        ResampledTrip,
        ResampledTripPoint,
        Trip,
        TripMatchedEdge,
        TripPoint,
    )

    if trace_source not in {"cleaned", "resampled"}:
        raise ValueError("trace_source must be 'cleaned' or 'resampled'")

    db = SessionLocal()
    try:
        if trace_source == "cleaned":
            trips = (
                db.execute(
                    select(Trip)
                    .where(Trip.line_id == line_id)
                    .order_by(Trip.processed_at)
                )
                .scalars()
                .all()
            )
            traces: list[ReconstructionTrace] = []
            for trip in trips:
                points = (
                    db.execute(
                        select(TripPoint)
                        .where(TripPoint.trip_id == trip.id)
                        .order_by(TripPoint.timestamp)
                    )
                    .scalars()
                    .all()
                )
                matched_edges = (
                    db.execute(
                        select(TripMatchedEdge)
                        .where(TripMatchedEdge.trip_id == trip.id)
                        .order_by(TripMatchedEdge.sequence)
                    )
                    .scalars()
                    .all()
                )
                traces.append(
                    _rows_to_trace(
                        trace_id=str(trip.id),
                        points=points,
                        point_index_attr="point_index",
                        matched_edges=matched_edges,
                    )
                )
            return [trace for trace in traces if len(trace.points) >= 2]

        if interval_meters is None:
            raise ValueError("interval_meters is required when trace_source='resampled'")

        score_filter = (
            ResampledTrip.match_score.is_(None)
            if min_match_score is None
            else ResampledTrip.match_score == min_match_score
        )
        resampled_trips = (
            db.execute(
                select(ResampledTrip)
                .join(Trip, ResampledTrip.trip_id == Trip.id)
                .where(
                    Trip.line_id == line_id,
                    ResampledTrip.interval_meters == interval_meters,
                    score_filter,
                )
                .order_by(ResampledTrip.created_at)
            )
            .scalars()
            .all()
        )
        traces = []
        for resampled_trip in resampled_trips:
            points = (
                db.execute(
                    select(ResampledTripPoint)
                    .where(ResampledTripPoint.resampled_trip_id == resampled_trip.id)
                    .order_by(ResampledTripPoint.point_index)
                )
                .scalars()
                .all()
            )
            traces.append(
                _rows_to_trace(
                    trace_id=str(resampled_trip.id),
                    points=points,
                    point_index_attr="point_index",
                )
            )
        return [trace for trace in traces if len(trace.points) >= 2]
    finally:
        db.close()


def _rows_to_trace(
    *,
    trace_id: str,
    points: list[Any],
    point_index_attr: str,
    matched_edges: list[Any] | None = None,
) -> ReconstructionTrace:
    return ReconstructionTrace(
        trace_id=trace_id,
        points=[
            ReconstructionPoint(
                longitude=float(point.longitude),
                latitude=float(point.latitude),
                point_index=int(getattr(point, point_index_attr)),
                timestamp=point.timestamp,
            )
            for point in points
        ],
        matched_edges=(
            [
                MatchedEdgeRef(
                    valhalla_edge_id=int(edge.valhalla_edge_id),
                    forward=bool(edge.forward),
                    sequence=int(edge.sequence),
                )
                for edge in matched_edges
            ]
            if matched_edges
            else None
        ),
    )


def _coerce_uuid(value: UUID | str | None, *, field_name: str) -> UUID:
    if value is None:
        raise ValueError(f"{field_name} is required when traces are not provided")
    return value if isinstance(value, UUID) else UUID(str(value))


def _reference_lon_lat(route: list[list[float]]) -> tuple[float, float]:
    if not route:
        raise ValueError("Route must contain at least 1 coordinate")
    lon = sum(point[0] for point in route) / len(route)
    lat = sum(point[1] for point in route) / len(route)
    return lon, lat


def _project_route_to_meters(
    route: list[list[float]],
    reference: list[list[float]] | tuple[float, float] | None = None,
) -> list[tuple[float, float]]:
    if isinstance(reference, tuple):
        reference_lon, reference_lat = reference
    else:
        reference_lon, reference_lat = _reference_lon_lat(reference or route)
    return [
        _project_point_to_meters(lon, lat, reference_lon, reference_lat)
        for lon, lat in route
    ]


def _project_point_to_meters(
    lon: float,
    lat: float,
    reference_lon: float,
    reference_lat: float,
) -> tuple[float, float]:
    ref_lat_rad = math.radians(reference_lat)
    x = (
        math.radians(lon - reference_lon)
        * EARTH_RADIUS_M
        * max(1e-9, math.cos(ref_lat_rad))
    )
    y = math.radians(lat - reference_lat) * EARTH_RADIUS_M
    return (x, y)


def _euclidean_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    return (dx * dx + dy * dy) ** 0.5


def _route_length_m(route: list[list[float]]) -> float:
    return sum(
        haversine_m(lon0, lat0, lon1, lat1)
        for (lon0, lat0), (lon1, lat1) in zip(route, route[1:], strict=False)
    )
