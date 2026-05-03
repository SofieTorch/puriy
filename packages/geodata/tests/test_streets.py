"""Tests for `geodata.streets` — street summary + endpoint zone helpers."""

from unittest.mock import MagicMock, patch

import httpx

from geodata.streets import resolve_endpoint_zones, summarise_streets


# ------------------------------------------------------------------
# summarise_streets
# ------------------------------------------------------------------

def _edge(name: str | None, length_km: float) -> dict:
    """Build a minimal Valhalla `trace_attributes` edge dict."""
    return {"names": [name] if name else [], "length": length_km}


def test_empty_edges_returns_empty_list() -> None:
    assert summarise_streets([]) == []


def test_single_long_run_emits_one_name() -> None:
    edges = [_edge("Av. América", 0.3), _edge("Av. América", 0.4)]
    assert summarise_streets(edges, min_run_m=200.0) == ["Av. América"]


def test_short_cross_streets_dropped_below_threshold() -> None:
    """A 50m crossing of Calle Sucre between two long runs of Av. América
    should not appear in the output."""
    edges = [
        _edge("Av. América", 0.4),     # 400m
        _edge("Calle Sucre", 0.05),    # 50m — below 200m threshold
        _edge("Av. América", 0.4),     # 400m
    ]
    summary = summarise_streets(edges, min_run_m=200.0)
    assert summary == ["Av. América"]


def test_distinct_long_runs_emitted_in_order() -> None:
    edges = [
        _edge("Av. Beijing", 0.3),
        _edge("Av. América", 0.5),
        _edge("Av. Pacata", 0.4),
    ]
    assert summarise_streets(edges, min_run_m=200.0) == [
        "Av. Beijing", "Av. América", "Av. Pacata",
    ]


def test_consecutive_segments_of_same_street_dedup() -> None:
    """A->B->A doesn't emit 'A' twice if the last two A-runs are
    contiguous (no name break between them)."""
    edges = [
        _edge("Av. América", 0.3),
        _edge("Av. Pacata", 0.05),     # short — dropped
        _edge("Av. América", 0.3),
    ]
    # The Pacata edge is below threshold, so it acts as a name break;
    # but the two Av. América runs are separate after a break. The
    # de-dup guard prevents listing Av. América twice in a row.
    assert summarise_streets(edges, min_run_m=200.0) == ["Av. América"]


def test_unnamed_edges_treated_as_name_break() -> None:
    """An unnamed edge ends the current group and resets accumulation."""
    edges = [
        _edge("Av. América", 0.15),    # 150m — below threshold alone
        _edge(None, 0.05),              # break
        _edge("Av. América", 0.15),    # 150m — below threshold alone
    ]
    # Neither group hits 200m; nothing emitted (the break prevents
    # accidentally summing the two halves).
    assert summarise_streets(edges, min_run_m=200.0) == []


def test_threshold_is_configurable() -> None:
    """A loose threshold lets short streets through."""
    edges = [_edge("Calle Corta", 0.1)]   # 100m
    assert summarise_streets(edges, min_run_m=50.0) == ["Calle Corta"]
    assert summarise_streets(edges, min_run_m=200.0) == []


# ------------------------------------------------------------------
# resolve_endpoint_zones
# ------------------------------------------------------------------

def _mock_nominatim_response(zone: str | None, field: str = "suburb") -> MagicMock:
    """Build a fake httpx response carrying a Nominatim payload."""
    resp = MagicMock()
    resp.json.return_value = {"address": {field: zone}} if zone else {"address": {}}
    resp.raise_for_status.return_value = None
    return resp


def test_resolve_returns_pair_of_zones() -> None:
    with patch("geodata.streets.httpx.get") as mock_get:
        mock_get.side_effect = [
            _mock_nominatim_response("Beijing"),
            _mock_nominatim_response("Sacaba"),
        ]
        zones = resolve_endpoint_zones(
            [-66.170, -17.390], [-66.150, -17.390],
            nominatim_url="http://localhost:8088",
        )
    assert zones == ["Beijing", "Sacaba"]


def test_resolve_falls_through_zone_fields() -> None:
    """When `suburb` is empty, falls through to `neighbourhood` etc."""
    with patch("geodata.streets.httpx.get") as mock_get:
        mock_get.side_effect = [
            _mock_nominatim_response("Cala Cala", field="neighbourhood"),
            _mock_nominatim_response("Sacaba", field="city_district"),
        ]
        zones = resolve_endpoint_zones(
            [-66.170, -17.390], [-66.150, -17.390],
        )
    assert zones == ["Cala Cala", "Sacaba"]


def test_resolve_returns_none_for_each_failure() -> None:
    """A network error on one endpoint doesn't poison the other."""
    with patch("geodata.streets.httpx.get") as mock_get:
        mock_get.side_effect = [
            httpx.ConnectError("connection refused"),
            _mock_nominatim_response("Sacaba"),
        ]
        zones = resolve_endpoint_zones(
            [-66.170, -17.390], [-66.150, -17.390],
        )
    assert zones == [None, "Sacaba"]


def test_resolve_returns_none_when_no_admin_level_matches() -> None:
    """Nominatim returned data but none of the zone fields are populated."""
    with patch("geodata.streets.httpx.get") as mock_get:
        mock_get.return_value = _mock_nominatim_response(None)
        zones = resolve_endpoint_zones(
            [-66.170, -17.390], [-66.150, -17.390],
        )
    assert zones == [None, None]


def test_resolve_handles_malformed_input() -> None:
    """Empty / undersized coords don't crash — return None for that side."""
    with patch("geodata.streets.httpx.get") as mock_get:
        mock_get.return_value = _mock_nominatim_response("Sacaba")
        zones = resolve_endpoint_zones([], [-66.150, -17.390])
    assert zones[0] is None
    assert zones[1] == "Sacaba"
