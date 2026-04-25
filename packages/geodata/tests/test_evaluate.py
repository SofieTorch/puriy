import json
from dataclasses import dataclass
from uuid import UUID

import pytest

from geodata.evaluate import (
    coverage_score,
    discrete_frechet_distance_m,
    evaluate_reconstruction_suite,
)
from geodata.reconstruction import ReconstructionPoint, ReconstructionResult, ReconstructionTrace


def _write_route(tmp_path, coordinates):
    route_file = tmp_path / "route.geojson"
    route_file.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {},
                        "geometry": {
                            "type": "LineString",
                            "coordinates": coordinates,
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return route_file


def _make_trace(trace_id: str, coordinates: list[list[float]]) -> ReconstructionTrace:
    return ReconstructionTrace(
        trace_id=trace_id,
        points=[
            ReconstructionPoint(
                longitude=lon,
                latitude=lat,
                point_index=index,
            )
            for index, (lon, lat) in enumerate(coordinates)
        ],
    )


@dataclass(frozen=True)
class _EchoRouteStrategy:
    key: str = "echo_route"
    label: str = "Echo route"

    def default_params(self) -> dict:
        return {}

    def reconstruct(
        self,
        line_id: UUID,
        traces: list[ReconstructionTrace],
        params: dict | None = None,
    ) -> ReconstructionResult:
        route = params["route"]
        return ReconstructionResult(
            strategy_name=self.label,
            geojson={
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"line_id": str(line_id), "trace_count": len(traces)},
                        "geometry": {"type": "LineString", "coordinates": route},
                    }
                ],
            },
            diagnostics={},
        )


@dataclass(frozen=True)
class _FailingStrategy:
    key: str = "always_fails"
    label: str = "Always fails"

    def default_params(self) -> dict:
        return {}

    def reconstruct(
        self,
        line_id: UUID,
        traces: list[ReconstructionTrace],
        params: dict | None = None,
    ) -> ReconstructionResult:
        raise RuntimeError("boom")


def test_discrete_frechet_distance_is_zero_for_identical_routes():
    route = [[0.0, 0.0], [0.001, 0.0], [0.002, 0.0]]

    assert discrete_frechet_distance_m(route, route) == pytest.approx(0.0)


def test_coverage_score_penalizes_partial_reconstruction():
    expected_route = [[0.0, 0.0], [0.003, 0.0]]
    reconstructed_geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {},
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[0.0, 0.0], [0.0015, 0.0]],
                },
            }
        ],
    }

    score = coverage_score(
        expected_route,
        reconstructed_geojson,
        coverage_step_meters=25.0,
        coverage_tolerance_meters=5.0,
    )

    assert 0.4 < score < 0.7


def test_evaluate_reconstruction_suite_scores_route_file_preview_perfectly(tmp_path):
    route = [[0.0, 0.0], [0.001, 0.0], [0.002, 0.0]]
    route_file = _write_route(tmp_path, route)
    traces = [_make_trace("a", route), _make_trace("b", route)]

    suite = evaluate_reconstruction_suite(
        route_file,
        traces=traces,
        strategy_keys=["route_file_preview"],
        runs_per_strategy=1,
    )

    summary = suite.summaries[0]
    run = summary.runs[0]

    assert summary.strategy_key == "route_file_preview"
    assert summary.success_count == 1
    assert summary.failure_count == 0
    assert summary.mean_frechet_distance_m == pytest.approx(0.0)
    assert summary.mean_coverage == pytest.approx(1.0)
    assert run.error is None


def test_evaluate_reconstruction_suite_aggregates_successes_and_failures(tmp_path):
    route = [[0.0, 0.0], [0.001, 0.0], [0.002, 0.0]]
    route_file = _write_route(tmp_path, route)
    traces = [_make_trace("a", route), _make_trace("b", route)]
    strategies = {
        "echo_route": _EchoRouteStrategy(),
        "always_fails": _FailingStrategy(),
    }
    strategy_params = {"echo_route": {"route": route}}

    suite = evaluate_reconstruction_suite(
        route_file,
        traces=traces,
        strategy_keys=["echo_route", "always_fails"],
        strategy_params=strategy_params,
        runs_per_strategy=2,
        strategies=strategies,
    )

    summaries = {summary.strategy_key: summary for summary in suite.summaries}

    assert summaries["echo_route"].success_count == 2
    assert summaries["echo_route"].failure_count == 0
    assert summaries["echo_route"].mean_frechet_distance_m == pytest.approx(0.0)
    assert summaries["echo_route"].mean_coverage == pytest.approx(1.0)

    assert summaries["always_fails"].success_count == 0
    assert summaries["always_fails"].failure_count == 2
    assert summaries["always_fails"].mean_frechet_distance_m is None
    assert summaries["always_fails"].mean_coverage is None
    assert all(run.error == "boom" for run in summaries["always_fails"].runs)
