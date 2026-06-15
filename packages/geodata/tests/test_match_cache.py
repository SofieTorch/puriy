"""Trace-match cache eviction bounds."""


import geodata.match as M


def _fresh_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("GEODATA_VALHALLA_EDGE_ID_CACHE", str(tmp_path / "cache.json"))
    M._TRACE_MATCH_CACHE = None
    return M._load_trace_match_cache()


def _entry(i: int) -> dict:
    return {"costing": "bus", "search_radius": 40, "gps_accuracy": 20,
            "shape_coords": [[-66.1, -17.4]] * 20, "edges": [{"id": i, "forward": True}],
            "matched_points": [], "match_score": 0.9, "mean_snap_distance": 1.0}


def test_entry_count_bound_evicts_oldest(tmp_path, monkeypatch):
    cache = _fresh_cache(tmp_path, monkeypatch)
    monkeypatch.setenv("GEODATA_TRACE_CACHE_MAX_ENTRIES", "5")
    monkeypatch.setenv("GEODATA_TRACE_CACHE_MAX_BYTES", "0")  # disable byte bound
    for i in range(20):
        cache[f"k{i:02d}"] = _entry(i)
    M._write_trace_match_cache(cache)
    # Only the 5 newest survive; oldest (k00..k14) evicted.
    assert len(cache) == 5
    assert set(cache) == {f"k{i:02d}" for i in range(15, 20)}


def test_byte_bound_brings_file_under_cap(tmp_path, monkeypatch):
    cache = _fresh_cache(tmp_path, monkeypatch)
    monkeypatch.setenv("GEODATA_TRACE_CACHE_MAX_ENTRIES", "0")  # disable count bound
    # Each entry ~ a few KB; cap the file at 20 KB.
    monkeypatch.setenv("GEODATA_TRACE_CACHE_MAX_BYTES", "20000")
    for i in range(200):
        cache[f"k{i:03d}"] = _entry(i)
    M._write_trace_match_cache(cache)
    size = (tmp_path / "cache.json").stat().st_size
    assert size <= 20000
    assert len(cache) < 200  # something was evicted
    # Survivors are the most-recent.
    assert max(cache) == "k199"


def test_prune_function_reports_before_after(tmp_path, monkeypatch):
    cache = _fresh_cache(tmp_path, monkeypatch)
    for i in range(50):
        cache[f"k{i:02d}"] = _entry(i)
    M._write_trace_match_cache(cache)
    result = M.prune_trace_match_cache(max_entries=10, max_bytes=0)
    assert result["before"] == 50
    assert result["after"] == 10
    assert result["bytes"] > 0
