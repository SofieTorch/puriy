import json
from uuid import uuid4

import pytest

from geodata.evaluate import discrete_frechet_distance_m
import geodata.match as match_module
from geodata.match import _TraceOutput
from geodata.reconstruction import (
    DBSCANGridSearchPreviewStrategy,
    EdgeGraphConsensusPreviewStrategy,
    EdgeSequenceOverlapAssemblyPreviewStrategy,
    MatchedEdgeRef,
    OverlapJoinPreviewStrategy,
    ReconstructionPoint,
    ReconstructionTrace,
    SegmentVoteConsensusPreviewStrategy,
    get_reconstruction_strategies,
)
from geodata.reconstruction.dbscan_grid_search_preview import strategy as dbscan_grid_search_strategy
from geodata.reconstruction.edge_graph_consensus_preview import strategy as edge_graph_strategy
from geodata.reconstruction.edge_sequence_overlap_assembly_preview import strategy as edge_sequence_strategy
from geodata.reconstruction.segment_vote_consensus_preview import strategy as segment_vote_strategy


def _make_trace(trace_id: str, lon_offset: float = 0.0) -> ReconstructionTrace:
    points = [
        ReconstructionPoint(longitude=lon_offset + 0.00000, latitude=0.0, point_index=0),
        ReconstructionPoint(longitude=lon_offset + 0.00100, latitude=0.0, point_index=1),
        ReconstructionPoint(longitude=lon_offset + 0.00200, latitude=0.0, point_index=2),
        ReconstructionPoint(longitude=lon_offset + 0.00300, latitude=0.0, point_index=3),
    ]
    return ReconstructionTrace(trace_id=trace_id, points=points)


def _make_edge_trace(
    trace_id: str,
    edge_ids: list[int],
    *,
    lon_start: float = 0.0,
    duplicate_first_edge: bool = False,
) -> ReconstructionTrace:
    point_count = max(2, len(edge_ids) + 1)
    points = [
        ReconstructionPoint(
            longitude=lon_start + (point_index * 0.001),
            latitude=0.0,
            point_index=point_index,
        )
        for point_index in range(point_count)
    ]

    matched_edge_ids = list(edge_ids)
    if duplicate_first_edge and matched_edge_ids:
        matched_edge_ids.insert(0, matched_edge_ids[0])

    matched_edges = [
        MatchedEdgeRef(
            valhalla_edge_id=edge_id,
            forward=True,
            sequence=sequence,
        )
        for sequence, edge_id in enumerate(matched_edge_ids)
    ]
    return ReconstructionTrace(
        trace_id=trace_id,
        points=points,
        matched_edges=matched_edges,
    )


def test_reconstruction_registry_exposes_dbscan_preview():
    strategies = get_reconstruction_strategies()

    assert "route_file_preview" in strategies
    assert "overlap_join_preview" in strategies
    assert "dbscan_consensus_preview" in strategies
    assert "dbscan_grid_search_preview" in strategies
    assert "edge_graph_consensus_preview" in strategies
    assert "edge_sequence_overlap_assembly_preview" in strategies
    assert "segment_vote_consensus_preview" in strategies
    assert strategies["overlap_join_preview"].label == "Pairwise overlap join (preview)"
    assert strategies["dbscan_consensus_preview"].label == "DBSCAN consensus (preview)"
    assert (
        strategies["dbscan_grid_search_preview"].label
        == "DBSCAN grid-search consensus (preview)"
    )
    assert (
        strategies["edge_graph_consensus_preview"].label
        == "Valhalla edge-graph consensus (preview)"
    )
    assert (
        strategies["edge_sequence_overlap_assembly_preview"].label
        == "Edge-sequence overlap assembly (preview)"
    )
    assert (
        strategies["segment_vote_consensus_preview"].label
        == "Segment-vote consensus (preview)"
    )
    assert strategies["route_file_preview"].label == "Route file preview"


def test_dbscan_preview_strategy_returns_linestring_geojson(monkeypatch):
    strategy = get_reconstruction_strategies()["dbscan_consensus_preview"]

    def fake_trace_match(
        points,
        *,
        trace_id=None,
        costing="bus",
        search_radius=60,
        gps_accuracy=20,
    ):
        assert costing == "bus"
        assert search_radius == 60
        assert gps_accuracy == 20
        return _TraceOutput(
            shape_coords=[
                (0.0, 0.0),
                (0.0, 0.0010),
                (0.0, 0.0020),
                (0.0, 0.0030),
            ],
            edges=[],
            matched_points=[],
            match_score=1.0,
            mean_snap_distance=0.0,
        )

    monkeypatch.setattr(match_module, "trace_match", fake_trace_match)
    result = strategy.reconstruct(
        uuid4(),
        [
            _make_trace("a"),
            _make_trace("b", lon_offset=0.00001),
            _make_trace("c", lon_offset=-0.00001),
        ],
        params={"eps_meters": 20.0, "min_samples": 2},
    )

    assert result.strategy_name == "DBSCAN consensus (preview)"
    assert result.geojson["type"] == "FeatureCollection"
    assert len(result.geojson["features"]) == 1
    feature = result.geojson["features"][0]
    assert feature["geometry"]["type"] == "LineString"
    assert feature["geometry"]["coordinates"] == [
        [0.0, 0.0],
        [0.0010, 0.0],
        [0.0020, 0.0],
        [0.0030, 0.0],
    ]
    assert result.diagnostics["trace_count"] == 3
    assert result.diagnostics["ordering_method"] in {
        "learned_centerline_mst_diameter",
        "mean_point_index_fallback",
    }
    assert result.diagnostics["route_points"] == 4
    assert result.diagnostics["raw_route_points"] >= 2


def test_overlap_join_preview_strategy_stitches_partial_traces():
    strategy = OverlapJoinPreviewStrategy()
    traces = [
        ReconstructionTrace(
            trace_id="middle",
            points=[
                ReconstructionPoint(longitude=0.0010, latitude=0.0, point_index=0),
                ReconstructionPoint(longitude=0.0020, latitude=0.0, point_index=1),
                ReconstructionPoint(longitude=0.0030, latitude=0.0, point_index=2),
            ],
        ),
        ReconstructionTrace(
            trace_id="prefix",
            points=[
                ReconstructionPoint(longitude=0.0000, latitude=0.0, point_index=0),
                ReconstructionPoint(longitude=0.0010, latitude=0.0, point_index=1),
                ReconstructionPoint(longitude=0.0020, latitude=0.0, point_index=2),
            ],
        ),
        ReconstructionTrace(
            trace_id="suffix",
            points=[
                ReconstructionPoint(longitude=0.0020, latitude=0.0, point_index=0),
                ReconstructionPoint(longitude=0.0030, latitude=0.0, point_index=1),
                ReconstructionPoint(longitude=0.0040, latitude=0.0, point_index=2),
            ],
        ),
    ]

    result = strategy.reconstruct(uuid4(), traces)

    assert result.strategy_name == "Pairwise overlap join (preview)"
    assert result.geojson["features"][0]["geometry"]["coordinates"] == [
        [0.0000, 0.0],
        [0.0010, 0.0],
        [0.0020, 0.0],
        [0.0030, 0.0],
        [0.0040, 0.0],
    ]
    assert result.diagnostics["merges_with_overlap"] == 2
    assert result.diagnostics["merges_without_overlap"] == 0


def test_overlap_join_preview_strategy_reverses_trace_to_match_overlap():
    strategy = OverlapJoinPreviewStrategy()
    traces = [
        ReconstructionTrace(
            trace_id="forward",
            points=[
                ReconstructionPoint(longitude=0.0000, latitude=0.0, point_index=0),
                ReconstructionPoint(longitude=0.0010, latitude=0.0, point_index=1),
                ReconstructionPoint(longitude=0.0020, latitude=0.0, point_index=2),
            ],
        ),
        ReconstructionTrace(
            trace_id="reverse-suffix",
            points=[
                ReconstructionPoint(longitude=0.0040, latitude=0.0, point_index=0),
                ReconstructionPoint(longitude=0.0030, latitude=0.0, point_index=1),
                ReconstructionPoint(longitude=0.0020, latitude=0.0, point_index=2),
            ],
        ),
    ]

    result = strategy.reconstruct(uuid4(), traces)

    assert result.geojson["features"][0]["geometry"]["coordinates"] == [
        [0.0000, 0.0],
        [0.0010, 0.0],
        [0.0020, 0.0],
        [0.0030, 0.0],
        [0.0040, 0.0],
    ]
    assert result.diagnostics["reversed_trace_count"] == 1
    assert result.diagnostics["merges_with_overlap"] == 1


def test_overlap_join_preview_strategy_falls_back_to_endpoint_join_without_overlap():
    strategy = OverlapJoinPreviewStrategy()
    traces = [
        ReconstructionTrace(
            trace_id="a",
            points=[
                ReconstructionPoint(longitude=0.0000, latitude=0.0, point_index=0),
                ReconstructionPoint(longitude=0.0010, latitude=0.0, point_index=1),
            ],
        ),
        ReconstructionTrace(
            trace_id="b",
            points=[
                ReconstructionPoint(longitude=0.0020, latitude=0.0, point_index=0),
                ReconstructionPoint(longitude=0.0030, latitude=0.0, point_index=1),
            ],
        ),
    ]

    result = strategy.reconstruct(
        uuid4(),
        traces,
        params={"overlap_tolerance_meters": 5.0, "min_overlap_points": 2},
    )

    assert result.geojson["features"][0]["geometry"]["coordinates"] == [
        [0.0000, 0.0],
        [0.0010, 0.0],
        [0.0020, 0.0],
        [0.0030, 0.0],
    ]
    assert result.diagnostics["merges_with_overlap"] == 0
    assert result.diagnostics["merges_without_overlap"] == 1


def test_dbscan_preview_strategy_handles_traces_with_different_start_offsets(monkeypatch):
    strategy = get_reconstruction_strategies()["dbscan_consensus_preview"]
    expected_route = [
        [0.0000, 0.0000],
        [0.0010, 0.0000],
        [0.0020, 0.0000],
        [0.0020, 0.0010],
        [0.0020, 0.0020],
    ]
    traces = [
        ReconstructionTrace(
            trace_id="full",
            points=[
                ReconstructionPoint(longitude=0.0000, latitude=0.0000, point_index=0),
                ReconstructionPoint(longitude=0.0010, latitude=0.0000, point_index=1),
                ReconstructionPoint(longitude=0.0020, latitude=0.0000, point_index=2),
                ReconstructionPoint(longitude=0.0020, latitude=0.0010, point_index=3),
                ReconstructionPoint(longitude=0.0020, latitude=0.0020, point_index=4),
            ],
        ),
        ReconstructionTrace(
            trace_id="mid-start",
            points=[
                ReconstructionPoint(longitude=0.0010, latitude=0.0000, point_index=0),
                ReconstructionPoint(longitude=0.0020, latitude=0.0000, point_index=1),
                ReconstructionPoint(longitude=0.0020, latitude=0.0010, point_index=2),
                ReconstructionPoint(longitude=0.0020, latitude=0.0020, point_index=3),
            ],
        ),
        ReconstructionTrace(
            trace_id="late-start",
            points=[
                ReconstructionPoint(longitude=0.0020, latitude=0.0000, point_index=0),
                ReconstructionPoint(longitude=0.0020, latitude=0.0010, point_index=1),
                ReconstructionPoint(longitude=0.0020, latitude=0.0020, point_index=2),
            ],
        ),
    ]

    def fake_trace_match(
        points,
        *,
        trace_id=None,
        costing="bus",
        search_radius=60,
        gps_accuracy=20,
    ):
        return _TraceOutput(
            shape_coords=[
                (0.0, 0.0),
                (0.0, 0.0010),
                (0.0, 0.0020),
                (0.0010, 0.0020),
                (0.0020, 0.0020),
            ],
            edges=[],
            matched_points=[],
            match_score=1.0,
            mean_snap_distance=0.0,
        )

    monkeypatch.setattr(match_module, "trace_match", fake_trace_match)

    result = strategy.reconstruct(
        uuid4(),
        traces,
        params={"eps_meters": 30.0, "min_samples": 1},
    )

    reconstructed_route = result.geojson["features"][0]["geometry"]["coordinates"]
    assert result.diagnostics["ordering_method"] == "learned_centerline_mst_diameter"
    assert discrete_frechet_distance_m(expected_route, reconstructed_route) < 150.0


def test_dbscan_preview_strategy_surfaces_too_few_points():
    strategy = get_reconstruction_strategies()["dbscan_consensus_preview"]
    line_id = uuid4()
    traces = [
        ReconstructionTrace(
            trace_id="too-short",
            points=[ReconstructionPoint(longitude=0.0, latitude=0.0, point_index=0)],
        )
    ]

    with pytest.raises(ValueError, match="At least 2 pooled points"):
        strategy.reconstruct(line_id, traces, params={"eps_meters": 20.0})


def test_dbscan_grid_search_strategy_selects_best_overlap_candidate(monkeypatch):
    strategy = DBSCANGridSearchPreviewStrategy()
    line_id = uuid4()
    traces = [
        ReconstructionTrace(
            trace_id="trace-a",
            points=[
                ReconstructionPoint(longitude=0.0000, latitude=0.0000, point_index=0),
                ReconstructionPoint(longitude=0.0010, latitude=0.0000, point_index=1),
                ReconstructionPoint(longitude=0.0020, latitude=0.0000, point_index=2),
            ],
        ),
        ReconstructionTrace(
            trace_id="trace-b",
            points=[
                ReconstructionPoint(longitude=0.0000, latitude=0.0000, point_index=0),
                ReconstructionPoint(longitude=0.0010, latitude=0.0000, point_index=1),
                ReconstructionPoint(longitude=0.0020, latitude=0.0000, point_index=2),
            ],
        ),
    ]

    def fake_cluster(_line_id, _traces, *, eps_meters=30.0, min_samples=None):
        assert _line_id == line_id
        assert _traces == traces
        route = (
            [[0.0, 0.0], [0.0010, 0.0], [0.0020, 0.0]]
            if eps_meters == 5.0 and min_samples == 1
            else [[0.0, 0.0010], [0.0010, 0.0010], [0.0020, 0.0010]]
        )
        ordering_method = (
            "learned_centerline_mst_diameter"
            if eps_meters == 5.0 and min_samples == 1
            else "mean_point_index_fallback"
        )
        fake_preview = type("FakePreview", (), {})()
        fake_preview.line_id = _line_id
        fake_preview.route_coordinates = route
        fake_preview.geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {},
                    "geometry": {"type": "LineString", "coordinates": route},
                }
            ],
        }
        fake_preview.n_traces = len(_traces)
        fake_preview.n_points_total = sum(len(trace.points) for trace in _traces)
        fake_preview.n_noise_points = 0
        fake_preview.n_clusters = len(route)
        fake_preview.min_samples = 1 if min_samples is None else min_samples
        fake_preview.ordering_method = ordering_method
        return fake_preview

    monkeypatch.setattr(
        dbscan_grid_search_strategy,
        "cluster_traces_preview",
        fake_cluster,
    )

    def fake_trace_match(
        points,
        *,
        trace_id=None,
        costing="bus",
        search_radius=60,
        gps_accuracy=20,
    ):
        assert costing == "bus"
        assert search_radius == 60
        assert gps_accuracy == 20
        return _TraceOutput(
            shape_coords=[
                (10.0, 20.0),
                (30.0, 40.0),
            ],
            edges=[],
            matched_points=[],
            match_score=1.0,
            mean_snap_distance=0.0,
        )

    monkeypatch.setattr(match_module, "trace_match", fake_trace_match)

    result = strategy.reconstruct(
        line_id,
        traces,
        params={
            "eps_start_meters": 5.0,
            "eps_stop_meters": 10.0,
            "eps_step_meters": 5.0,
            "min_samples_min": 1,
            "min_samples_max": 1,
            "overlap_tolerance_meters": 25.0,
        },
    )

    assert result.strategy_name == "DBSCAN grid-search consensus (preview)"
    assert result.geojson["features"][0]["geometry"]["coordinates"] == [
        [20.0, 10.0],
        [40.0, 30.0],
    ]
    assert result.diagnostics["eps_meters"] == 5.0
    assert result.diagnostics["min_samples"] == 1
    assert result.diagnostics["attempted_candidates"] == 2
    assert result.diagnostics["failed_candidates"] == 0
    assert result.diagnostics["overlap_ratio"] == pytest.approx(1.0)
    assert result.diagnostics["route_support_ratio"] == pytest.approx(1.0)
    assert result.diagnostics["route_points"] == 2
    assert result.diagnostics["raw_route_points"] == 3


def test_dbscan_grid_search_strategy_surfaces_failure_when_all_candidates_fail():
    strategy = DBSCANGridSearchPreviewStrategy()
    traces = [
        ReconstructionTrace(
            trace_id="too-short",
            points=[ReconstructionPoint(longitude=0.0, latitude=0.0, point_index=0)],
        )
    ]

    with pytest.raises(ValueError, match="Grid-search DBSCAN could not produce a valid route"):
        strategy.reconstruct(
            uuid4(),
            traces,
            params={
                "eps_start_meters": 5.0,
                "eps_stop_meters": 5.0,
                "eps_step_meters": 5.0,
                "min_samples_min": 1,
                "min_samples_max": 1,
            },
        )


def test_route_file_preview_strategy_returns_geojson_from_file(tmp_path):
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
                            "coordinates": [[1.0, 2.0], [3.0, 4.0]],
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    strategy = get_reconstruction_strategies()["route_file_preview"]
    result = strategy.reconstruct(
        uuid4(),
        [_make_trace("a")],
        params={"route_file": str(route_file)},
    )

    assert result.strategy_name == "Route file preview"
    assert result.geojson["features"][0]["geometry"]["coordinates"] == [
        [1.0, 2.0],
        [3.0, 4.0],
    ]
    assert result.diagnostics["route_file"] == "route.geojson"


def test_edge_graph_consensus_preview_strategy_returns_consensus_linestring(monkeypatch):
    strategy = EdgeGraphConsensusPreviewStrategy()
    response_queue = [
        {
            "shape_coords": [
                (0.0, 0.0),
                (0.0, 0.001),
                (0.0, 0.002),
                (0.0, 0.003),
                (0.0, 0.004),
            ],
            "edges": [
                {"id": 101, "forward": True, "begin_shape_index": 0, "end_shape_index": 1},
                {"id": 102, "forward": True, "begin_shape_index": 1, "end_shape_index": 2},
                {"id": 103, "forward": True, "begin_shape_index": 2, "end_shape_index": 3},
                {"id": 104, "forward": True, "begin_shape_index": 3, "end_shape_index": 4},
            ],
        },
        {
            "shape_coords": [
                (0.0, 0.0),
                (0.0, 0.001),
                (0.0, 0.002),
                (0.0, 0.004),
            ],
            "edges": [
                {"id": 101, "forward": True, "begin_shape_index": 0, "end_shape_index": 1},
                {"id": 102, "forward": True, "begin_shape_index": 1, "end_shape_index": 2},
                {"id": 104, "forward": True, "begin_shape_index": 2, "end_shape_index": 3},
            ],
        },
        {
            "shape_coords": [
                (0.0, 0.0),
                (0.0, 0.001),
                (0.0, 0.002),
                (0.0, 0.003),
                (0.0, 0.004),
            ],
            "edges": [
                {"id": 101, "forward": True, "begin_shape_index": 0, "end_shape_index": 1},
                {"id": 102, "forward": True, "begin_shape_index": 1, "end_shape_index": 2},
                {"id": 103, "forward": True, "begin_shape_index": 2, "end_shape_index": 3},
                {"id": 104, "forward": True, "begin_shape_index": 3, "end_shape_index": 4},
            ],
        },
    ]

    def fake_trace_match(
        points,
        *,
        trace_id=None,
        costing="bus",
        search_radius=60,
        gps_accuracy=20,
    ):
        payload = response_queue.pop(0)
        return _TraceOutput(
            shape_coords=payload["shape_coords"],
            edges=payload["edges"],
            matched_points=[],
            match_score=1.0,
            mean_snap_distance=0.0,
        )

    monkeypatch.setattr(edge_graph_strategy, "trace_match", fake_trace_match)

    traces = [
        _make_trace("a"),
        _make_trace("b", lon_offset=0.00001),
        _make_trace("c", lon_offset=-0.00001),
    ]
    result = strategy.reconstruct(uuid4(), traces)

    assert result.strategy_name == "Valhalla edge-graph consensus (preview)"
    assert result.geojson["features"][0]["geometry"]["type"] == "LineString"
    assert result.geojson["features"][0]["geometry"]["coordinates"] == [
        [0.0, 0.0],
        [0.001, 0.0],
        [0.002, 0.0],
        [0.003, 0.0],
        [0.004, 0.0],
    ]
    assert result.diagnostics["matched_trace_count"] == 3
    assert result.diagnostics["consensus_edge_count"] == 4
    assert result.diagnostics["consensus_method"] == "beam_search_weighted_path"


def test_edge_graph_consensus_preview_strategy_requires_matched_edges(monkeypatch):
    strategy = EdgeGraphConsensusPreviewStrategy()

    def fake_trace_match(
        points,
        *,
        trace_id=None,
        costing="bus",
        search_radius=60,
        gps_accuracy=20,
    ):
        return _TraceOutput(
            shape_coords=[],
            edges=[],
            matched_points=[],
            match_score=0.0,
            mean_snap_distance=0.0,
        )

    monkeypatch.setattr(edge_graph_strategy, "trace_match", fake_trace_match)

    with pytest.raises(ValueError, match="did not return any matched edges"):
        strategy.reconstruct(uuid4(), [_make_trace("a")])


def test_segment_vote_consensus_preview_handles_reversed_infixes_and_outlier(monkeypatch):
    strategy = SegmentVoteConsensusPreviewStrategy()
    response_queue = [
        {
            "shape_coords": [
                (0.0, 0.0),
                (0.0, 0.001),
                (0.0, 0.002),
                (0.0, 0.003),
                (0.0, 0.004),
            ],
            "edges": [
                {"id": 101, "begin_shape_index": 0, "end_shape_index": 1},
                {"id": 102, "begin_shape_index": 1, "end_shape_index": 2},
                {"id": 103, "begin_shape_index": 2, "end_shape_index": 3},
                {"id": 104, "begin_shape_index": 3, "end_shape_index": 4},
            ],
        },
        {
            "shape_coords": [
                (0.0, 0.001),
                (0.0, 0.002),
                (0.0, 0.003),
            ],
            "edges": [
                {"id": 102, "begin_shape_index": 0, "end_shape_index": 1},
                {"id": 103, "begin_shape_index": 1, "end_shape_index": 2},
            ],
        },
        {
            "shape_coords": [
                (0.0, 0.004),
                (0.0, 0.003),
                (0.0, 0.002),
                (0.0, 0.001),
                (0.0, 0.0),
            ],
            "edges": [
                {"id": 104, "begin_shape_index": 0, "end_shape_index": 1},
                {"id": 103, "begin_shape_index": 1, "end_shape_index": 2},
                {"id": 102, "begin_shape_index": 2, "end_shape_index": 3},
                {"id": 101, "begin_shape_index": 3, "end_shape_index": 4},
            ],
        },
        {
            "shape_coords": [
                (1.0, 1.0),
                (1.0, 1.001),
                (1.0, 1.002),
            ],
            "edges": [
                {"id": 901, "begin_shape_index": 0, "end_shape_index": 1},
                {"id": 902, "begin_shape_index": 1, "end_shape_index": 2},
            ],
        },
    ]

    def fake_trace_match(
        points,
        *,
        trace_id=None,
        costing="bus",
        search_radius=60,
        gps_accuracy=20,
    ):
        payload = response_queue.pop(0)
        return _TraceOutput(
            shape_coords=payload["shape_coords"],
            edges=payload["edges"],
            matched_points=[],
            match_score=1.0,
            mean_snap_distance=0.0,
        )

    monkeypatch.setattr(segment_vote_strategy, "trace_match", fake_trace_match)

    traces = [
        _make_trace("full"),
        _make_trace("infix", lon_offset=0.00001),
        _make_trace("reverse", lon_offset=-0.00001),
        _make_trace("outlier", lon_offset=0.1),
    ]
    result = strategy.reconstruct(
        uuid4(),
        traces,
        params={"min_edge_support": 2, "min_pair_support": 2},
    )

    assert result.strategy_name == "Segment-vote consensus (preview)"
    assert result.geojson["type"] == "FeatureCollection"
    assert len(result.geojson["features"]) == 1
    feature = result.geojson["features"][0]
    assert feature["geometry"]["type"] == "LineString"
    assert feature["geometry"]["coordinates"] == [
        [0.0, 0.0],
        [0.001, 0.0],
        [0.002, 0.0],
        [0.003, 0.0],
        [0.004, 0.0],
    ]
    assert result.diagnostics["matched_trace_count"] == 4
    assert result.diagnostics["reversed_trace_count"] == 1
    assert result.diagnostics["supported_edge_count"] == 4
    assert result.diagnostics["supported_pair_count"] == 3
    assert result.diagnostics["consensus_method"] == "segment_vote_local_support"


def test_segment_vote_consensus_preview_requires_supported_edges(monkeypatch):
    strategy = SegmentVoteConsensusPreviewStrategy()

    def fake_trace_match(
        points,
        *,
        trace_id=None,
        costing="bus",
        search_radius=60,
        gps_accuracy=20,
    ):
        return _TraceOutput(
            shape_coords=[],
            edges=[],
            matched_points=[],
            match_score=0.0,
            mean_snap_distance=0.0,
        )

    monkeypatch.setattr(segment_vote_strategy, "trace_match", fake_trace_match)

    with pytest.raises(ValueError, match="did not return any matched edges"):
        strategy.reconstruct(uuid4(), [_make_trace("a")])


def test_edge_sequence_overlap_assembly_preview_stitches_persisted_edge_sequences(monkeypatch):
    strategy = EdgeSequenceOverlapAssemblyPreviewStrategy()
    responses = {
        "prefix": {
            "shape_coords": [
                (0.0, 0.0),
                (0.0, 0.001),
                (0.0, 0.002),
                (0.0, 0.003),
            ],
            "edges": [
                {"id": 101, "forward": True, "begin_shape_index": 0, "end_shape_index": 1},
                {"id": 102, "forward": True, "begin_shape_index": 1, "end_shape_index": 2},
                {"id": 103, "forward": True, "begin_shape_index": 2, "end_shape_index": 3},
            ],
        },
        "suffix": {
            "shape_coords": [
                (0.0, 0.002),
                (0.0, 0.003),
                (0.0, 0.004),
            ],
            "edges": [
                {"id": 103, "forward": True, "begin_shape_index": 0, "end_shape_index": 1},
                {"id": 104, "forward": True, "begin_shape_index": 1, "end_shape_index": 2},
            ],
        },
        "contained": {
            "shape_coords": [
                (0.0, 0.001),
                (0.0, 0.002),
                (0.0, 0.003),
            ],
            "edges": [
                {"id": 102, "forward": True, "begin_shape_index": 0, "end_shape_index": 1},
                {"id": 103, "forward": True, "begin_shape_index": 1, "end_shape_index": 2},
            ],
        },
    }

    def fake_trace_match(
        points,
        *,
        trace_id=None,
        costing="bus",
        search_radius=60,
        gps_accuracy=20,
    ):
        payload = responses[str(trace_id)]
        return _TraceOutput(
            shape_coords=payload["shape_coords"],
            edges=payload["edges"],
            matched_points=[],
            match_score=1.0,
            mean_snap_distance=0.0,
        )

    monkeypatch.setattr(edge_sequence_strategy, "trace_match", fake_trace_match)

    traces = [
        _make_edge_trace("prefix", [101, 102, 103], duplicate_first_edge=True),
        _make_edge_trace("suffix", [103, 104], lon_start=0.002),
        _make_edge_trace("contained", [102, 103], lon_start=0.001),
    ]
    result = strategy.reconstruct(uuid4(), traces)

    assert result.strategy_name == "Edge-sequence overlap assembly (preview)"
    assert result.geojson["features"][0]["geometry"]["coordinates"] == [
        [0.0, 0.0],
        [0.001, 0.0],
        [0.002, 0.0],
        [0.003, 0.0],
        [0.004, 0.0],
    ]
    assert result.geojson["features"][0]["properties"]["consensus_edge_ids"] == [101, 102, 103, 104]
    assert result.diagnostics["persisted_trace_count"] == 3
    assert result.diagnostics["fallback_trace_match_count"] == 0
    assert result.diagnostics["contained_trace_count"] == 1
    assert result.diagnostics["consensus_method"] == "edge_sequence_overlap_assembly"


def test_edge_sequence_overlap_assembly_preview_fails_on_gap():
    strategy = EdgeSequenceOverlapAssemblyPreviewStrategy()
    traces = [
        _make_edge_trace("left", [101, 102]),
        _make_edge_trace("right", [104, 105], lon_start=0.003),
    ]

    with pytest.raises(ValueError, match="gap with no supported overlap"):
        strategy.reconstruct(
            uuid4(),
            traces,
            params={"recover_geometry": False},
        )


def test_edge_sequence_overlap_assembly_preview_handles_inserted_edge_noise(monkeypatch):
    strategy = EdgeSequenceOverlapAssemblyPreviewStrategy()
    responses = {
        "canonical": {
            "shape_coords": [
                (0.0, 0.0),
                (0.0, 0.001),
                (0.0, 0.002),
                (0.0, 0.003),
                (0.0, 0.004),
            ],
            "edges": [
                {"id": 101, "forward": True, "begin_shape_index": 0, "end_shape_index": 1},
                {"id": 102, "forward": True, "begin_shape_index": 1, "end_shape_index": 2},
                {"id": 103, "forward": True, "begin_shape_index": 2, "end_shape_index": 3},
                {"id": 104, "forward": True, "begin_shape_index": 3, "end_shape_index": 4},
            ],
        },
        "noisy-full": {
            "shape_coords": [
                (0.0, 0.0),
                (0.0, 0.001),
                (0.0003, 0.0015),
                (0.0, 0.002),
                (0.0, 0.003),
                (0.0, 0.004),
            ],
            "edges": [
                {"id": 101, "forward": True, "begin_shape_index": 0, "end_shape_index": 1},
                {"id": 102, "forward": True, "begin_shape_index": 1, "end_shape_index": 2},
                {"id": 999, "forward": True, "begin_shape_index": 2, "end_shape_index": 3},
                {"id": 103, "forward": True, "begin_shape_index": 3, "end_shape_index": 4},
                {"id": 104, "forward": True, "begin_shape_index": 4, "end_shape_index": 5},
            ],
        },
        "partial": {
            "shape_coords": [
                (0.0, 0.001),
                (0.0, 0.002),
                (0.0, 0.003),
            ],
            "edges": [
                {"id": 102, "forward": True, "begin_shape_index": 0, "end_shape_index": 1},
                {"id": 103, "forward": True, "begin_shape_index": 1, "end_shape_index": 2},
            ],
        },
    }

    def fake_trace_match(
        points,
        *,
        trace_id=None,
        costing="bus",
        search_radius=60,
        gps_accuracy=20,
    ):
        payload = responses[str(trace_id)]
        return _TraceOutput(
            shape_coords=payload["shape_coords"],
            edges=payload["edges"],
            matched_points=[],
            match_score=1.0,
            mean_snap_distance=0.0,
        )

    monkeypatch.setattr(edge_sequence_strategy, "trace_match", fake_trace_match)

    traces = [
        _make_edge_trace("canonical", [101, 102, 103, 104]),
        _make_edge_trace("noisy-full", [101, 102, 999, 103, 104]),
        _make_edge_trace("partial", [102, 103], lon_start=0.001),
    ]
    result = strategy.reconstruct(uuid4(), traces)

    assert result.geojson["features"][0]["properties"]["consensus_edge_ids"] == [101, 102, 103, 104]
    assert result.diagnostics["merge_steps"] >= 0
