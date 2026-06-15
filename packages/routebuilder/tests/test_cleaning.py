"""Edge-geometry de-spiking against the matched-point band."""

import math


def _ll(dx_m, dy_m, lat=-17.3935, lon0=-66.22):
    mlon = 111_320 * math.cos(math.radians(lat))
    return (lon0 + dx_m / mlon, lat + dy_m / 110_540)


def test_despike_drops_intersection_detour_vertex():
    from routebuilder.cleaning import _despike_geometry, _PointBand

    # Clean matched band: a straight north-south corridor.
    band_pts = [_ll(0, y) for y in range(0, 300, 10)]
    band = _PointBand(band_pts, 30.0)

    # Edge shape whose first vertex detours 62m onto a cross street
    # (the Valhalla corner spike), then rejoins the corridor.
    spike = _ll(-62, 150)
    geom = [spike, _ll(0, 160), _ll(0, 175)]
    cleaned = _despike_geometry(geom, band, 30.0)

    assert spike not in cleaned
    assert len(cleaned) == 2
    assert all(band.min_dist_m(p) <= 30.0 for p in cleaned)


def test_despike_keeps_clean_geometry_untouched():
    from routebuilder.cleaning import _despike_geometry, _PointBand

    band_pts = [_ll(0, y) for y in range(0, 300, 10)]
    band = _PointBand(band_pts, 30.0)
    geom = [_ll(2, 100), _ll(-3, 120), _ll(1, 140)]  # all hug the corridor
    assert _despike_geometry(geom, band, 30.0) == geom


def test_despike_preserves_edge_when_all_offband():
    from routebuilder.cleaning import _despike_geometry, _PointBand

    band_pts = [_ll(0, y) for y in range(0, 300, 10)]
    band = _PointBand(band_pts, 30.0)
    # An edge entirely off the band: don't fabricate — keep original and
    # let support-graph pruning handle it.
    geom = [_ll(-200, 100), _ll(-205, 120)]
    assert _despike_geometry(geom, band, 30.0) == geom


def test_despike_disabled_when_threshold_zero():
    from routebuilder.cleaning import _despike_geometry, _PointBand

    band_pts = [_ll(0, y) for y in range(0, 300, 10)]
    band = _PointBand(band_pts, 30.0)
    geom = [_ll(-62, 150), _ll(0, 160), _ll(0, 175)]
    assert _despike_geometry(geom, band, 0.0) == geom
