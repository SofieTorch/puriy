import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import geodata.match as match_module
from geodata.match import _filter_single_point_spikes


@dataclass
class _RawPointStub:
    timestamp: datetime
    horizontal_accuracy: float | None = None


def _raw_points(count: int, *, accuracy: float | None = 25.0) -> list[_RawPointStub]:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    return [
        _RawPointStub(timestamp=start + timedelta(seconds=i * 5), horizontal_accuracy=accuracy)
        for i in range(count)
    ]


def test_filter_single_point_spikes_removes_perpendicular_snap():
    matched_points = [
        {"type": "matched", "lon": 0.00000, "lat": 0.0, "distance_from_trace_point": 4.0},
        {"type": "matched", "lon": 0.00025, "lat": 0.0, "distance_from_trace_point": 5.0},
        {"type": "matched", "lon": 0.00025, "lat": 0.00040, "distance_from_trace_point": 34.0},
        {"type": "matched", "lon": 0.00050, "lat": 0.0, "distance_from_trace_point": 4.0},
        {"type": "matched", "lon": 0.00075, "lat": 0.0, "distance_from_trace_point": 4.0},
    ]

    filtered = _filter_single_point_spikes(matched_points, _raw_points(len(matched_points)))

    assert [i for i, _ in filtered] == [0, 1, 3, 4]


def test_filter_single_point_spikes_keeps_real_right_angle_turn():
    matched_points = [
        {"type": "matched", "lon": 0.00000, "lat": 0.0, "distance_from_trace_point": 2.0},
        {"type": "matched", "lon": 0.00010, "lat": 0.0, "distance_from_trace_point": 3.0},
        {"type": "matched", "lon": 0.00020, "lat": 0.0, "distance_from_trace_point": 4.0},
        {"type": "matched", "lon": 0.00020, "lat": 0.00010, "distance_from_trace_point": 4.0},
        {"type": "matched", "lon": 0.00020, "lat": 0.00020, "distance_from_trace_point": 3.0},
    ]

    filtered = _filter_single_point_spikes(matched_points, _raw_points(len(matched_points), accuracy=6.0))

    assert [i for i, _ in filtered] == [0, 1, 2, 3, 4]


def test_trace_match_returns_cached_result_for_matching_trace_id(tmp_path, monkeypatch):
    cache_file = tmp_path / "valhalla-cache.json"
    cache_file.write_text(
        json.dumps(
            {
                "version": 1,
                "traces": {
                    "cleaned-trace-1|bus|60|20": {
                        "costing": "bus",
                        "search_radius": 60,
                        "gps_accuracy": 20,
                        "shape_coords": [[0.0, 0.0], [0.001, 0.0]],
                        "edges": [{"id": 101, "forward": True}],
                        "matched_points": [{"type": "matched", "lon": 0.0, "lat": 0.0}],
                        "match_score": 1.0,
                        "mean_snap_distance": 0.0,
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("GEODATA_VALHALLA_EDGE_ID_CACHE", str(cache_file))
    monkeypatch.setattr(match_module, "_TRACE_MATCH_CACHE", None)

    def fail_post(*args, **kwargs):
        raise AssertionError("Valhalla should not be called when the trace is cached")

    monkeypatch.setattr(match_module.httpx, "post", fail_post)

    result = match_module.trace_match(
        [{"lat": 0.0, "lon": 0.0}],
        trace_id="cleaned-trace-1",
    )

    assert result.shape_coords == [(0.0, 0.0), (0.0, 0.001)]
    assert result.edges == [{"id": 101, "forward": True}]
    assert result.match_score == 1.0


def test_trace_match_persists_result_to_cache_on_miss(tmp_path, monkeypatch):
    cache_file = tmp_path / "valhalla-cache.json"
    monkeypatch.setenv("GEODATA_VALHALLA_EDGE_ID_CACHE", str(cache_file))
    monkeypatch.setattr(match_module, "_TRACE_MATCH_CACHE", None)
    monkeypatch.setattr(match_module, "_decode_polyline6", lambda encoded: [(0.0, 0.0), (0.0, 0.001)])

    class _Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "shape": "encoded",
                "edges": [{"id": 202, "forward": False}],
                "matched_points": [{"type": "matched", "lon": 0.0, "lat": 0.0}],
            }

    calls = {"count": 0}

    def fake_post(*args, **kwargs):
        calls["count"] += 1
        return _Response()

    monkeypatch.setattr(match_module.httpx, "post", fake_post)

    first = match_module.trace_match(
        [{"lat": 0.0, "lon": 0.0}],
        trace_id="cleaned-trace-2",
    )
    second = match_module.trace_match(
        [{"lat": 0.0, "lon": 0.0}],
        trace_id="cleaned-trace-2",
    )

    assert calls["count"] == 1
    assert first.edges == second.edges == [{"id": 202, "forward": False}]
    assert cache_file.exists()
    cached_payload = json.loads(cache_file.read_text(encoding="utf-8"))
    assert "cleaned-trace-2|bus|60|20" in cached_payload["traces"]
