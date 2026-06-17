import random

from simlab.scenario import PersonaSpec, RouteSpec, ScenarioConfig, SpeedModel
from simlab.sim.gps import simulate_trip_points
from simlab.sim.personas import build_personas, generate_trip_history
from simlab.sim.route import parametrize
from simlab.sim.speed import simulate_speed_profile


def _straight_route(km: float = 4.0):
    # West→east at Cochabamba latitude, one point every ~100m.
    n = int(km * 10)
    return parametrize([(-66.157 + i * 0.00094, -17.3935) for i in range(n + 1)])


def _config(**kwargs) -> ScenarioConfig:
    return ScenarioConfig(
        name="test",
        route_geojson="unused.geojson",
        **kwargs,
    )


def test_param_route_roundtrip():
    route = _straight_route()
    assert route.length_m > 3500
    lon, lat = route.position_at(route.length_m / 2)
    assert -66.157 < lon < -66.10
    assert abs(lat - (-17.3935)) < 1e-6
    # Slice preserves arc length approximately.
    half = parametrize(route.slice(0, route.length_m / 2))
    assert abs(half.length_m - route.length_m / 2) < 5


def test_speed_profile_monotonic_and_dwells():
    rng = random.Random(1)
    model = SpeedModel()
    profile = simulate_speed_profile(0.0, 3000.0, model, rng)
    positions = profile.positions_m
    assert positions[0] == 0.0
    assert abs(positions[-1] - 3000.0) < 1e-6
    assert all(b >= a for a, b in zip(positions, positions[1:]))  # never reverses
    # Dwells exist: some consecutive ticks don't move.
    stalls = sum(1 for a, b in zip(positions, positions[1:]) if b == a)
    assert stalls > 5
    # Average speed is below cruise because of dwells.
    avg = 3000.0 / profile.duration_s
    assert avg < model.base_speed_mps


def test_trip_history_respects_calendar_and_travel_window():
    # One trip per device: `traces` traces => `traces` one-trip devices.
    config = _config(
        sim_days=21,
        personas=[PersonaSpec(name="p", traces=20, travel_window=(0.2, 0.7))],
    )
    route = _straight_route()
    rng = random.Random(3)
    personas = build_personas(config)
    trips = generate_trip_history(personas, route, config, rng)
    assert len(trips) == 20
    assert all(0 <= t.day < 21 for t in trips)
    assert all(t.board_m < t.alight_m for t in trips)
    # Every trip stays within the persona's travel window.
    assert all(t.board_m >= 0.2 * route.length_m - 1 for t in trips)
    assert all(t.alight_m <= 0.7 * route.length_m + 1 for t in trips)
    assert all(6 <= t.started_at.hour <= 21 for t in trips)
    devices = {t.device_id for t in trips}
    assert devices == {f"sim:p:{i}" for i in range(20)}


def test_fare_areas_price_by_most_expensive_traversed():
    from simlab.sim.fares import simulate_fares

    config = _config(
        personas=[PersonaSpec(
            name="p", traces=3, fare_report_prob=1.0,
            fare_areas=[
                dict(name="centro", start_fraction=0.0, end_fraction=0.5, amount_bob=2.4),
                dict(name="periferia", start_fraction=0.5, end_fraction=1.0, amount_bob=3.5),
            ],
        )],
        fares=dict(base_fare_bob=2.0, misreport_prob=0.0),
    )
    route = _straight_route()
    rng = random.Random(2)
    personas = build_personas(config)
    trips = generate_trip_history(personas, route, config, rng)
    # Force known stretches.
    trips = trips[:3]
    trips[0].board_m, trips[0].alight_m = 0.0, 0.4 * route.length_m       # centro only
    trips[1].board_m, trips[1].alight_m = 0.6 * route.length_m, route.length_m  # periferia
    trips[2].board_m, trips[2].alight_m = 0.2 * route.length_m, 0.9 * route.length_m  # both
    reports = simulate_fares(trips, route, config, rng)
    by_trip = {r.trip_id: r for r in reports}
    assert by_trip[trips[0].trip_id].amount_bob == 2.4
    assert by_trip[trips[0].trip_id].fare_area == "centro"
    assert by_trip[trips[1].trip_id].amount_bob == 3.5
    assert by_trip[trips[2].trip_id].amount_bob == 3.5
    assert by_trip[trips[2].trip_id].fare_area == "periferia"


def test_gps_points_follow_route_with_noise():
    # Jumps disabled: their exponential tail makes a hard corridor
    # bound luck-dependent; gaussian/cross-track noise stays bounded.
    config = _config(noise=dict(jump_probability=0.0))
    route = _straight_route()
    rng = random.Random(5)
    personas = build_personas(config)
    trips = generate_trip_history(personas, route, config, rng)
    trip = trips[0]
    trip.board_m, trip.alight_m, trip.forward = 0.0, route.length_m, True
    points = simulate_trip_points(trip, route, config, rng)
    assert len(points) > 50
    # All points within plausible noise of the corridor (lat fixed).
    assert all(abs(p.lat - (-17.3935)) * 111_320 < 80 for p in points)
    # Timestamps increase on average.
    seconds = [(p.timestamp - points[0].timestamp).total_seconds() for p in points]
    assert seconds[-1] > seconds[0]


def test_reverse_trip_travels_backwards():
    config = _config(noise=dict(gaussian_sigma_m=0.0, perpendicular_sigma_m=0.0,
                                jump_probability=0.0, missing_probability=0.0,
                                timestamp_jitter_s=0.0))
    route = _straight_route()
    rng = random.Random(7)
    personas = build_personas(config)
    trips = generate_trip_history(personas, route, config, rng)
    trip = trips[0]
    trip.board_m, trip.alight_m, trip.forward = 0.0, route.length_m, False
    points = simulate_trip_points(trip, route, config, rng)
    assert points[0].lon > points[-1].lon  # east → west


def test_reverse_trip_stays_inside_travel_window():
    # Regression: reverse runs used to mirror the window to the other
    # end of the route (geo = length - pos), leaking traces outside
    # the group's travel area.
    config = _config(noise=dict(gaussian_sigma_m=0.0, perpendicular_sigma_m=0.0,
                                jump_probability=0.0, missing_probability=0.0,
                                timestamp_jitter_s=0.0))
    route = _straight_route()  # west→east, lon grows with arc length
    rng = random.Random(9)
    personas = build_personas(config)
    trips = generate_trip_history(personas, route, config, rng)
    trip = trips[0]
    # Window = first 40% of the route, ridden in reverse.
    trip.board_m, trip.alight_m, trip.forward = 0.0, 0.4 * route.length_m, False
    points = simulate_trip_points(trip, route, config, rng)
    lon_at_40pct = route.position_at(0.4 * route.length_m)[0]
    assert all(p.lon <= lon_at_40pct + 1e-6 for p in points), "left the window"
    assert points[0].lon > points[-1].lon  # still travels backwards


def test_reverse_trip_fare_endpoints_swap_within_window():
    from simlab.sim.fares import simulate_fares

    config = _config(personas=[PersonaSpec(name="p", count=1, fare_report_prob=1.0)],
                     fares=dict(misreport_prob=0.0))
    route = _straight_route()
    rng = random.Random(3)
    personas = build_personas(config)
    trips = generate_trip_history(personas, route, config, rng)[:1]
    trip = trips[0]
    trip.board_m, trip.alight_m, trip.forward = 0.2 * route.length_m, 0.5 * route.length_m, False
    report = simulate_fares(trips, route, config, rng)[0]
    # Boards at the far (50%) end, alights at the near (20%) end.
    assert report.boarding_lon > report.alighting_lon
    assert abs(report.boarding_lon - route.position_at(0.5 * route.length_m)[0]) < 1e-6
    assert abs(report.alighting_lon - route.position_at(0.2 * route.length_m)[0]) < 1e-6


def test_groups_ride_their_assigned_route():
    config = ScenarioConfig(
        name="t",
        routes=[
            RouteSpec(name="main", path="a.geojson", role="main"),
            RouteSpec(name="variant", path="b.geojson", role="ramal"),
        ],
        personas=[
            PersonaSpec(name="m", count=1, route="main"),
            PersonaSpec(name="v", count=1, route="variant"),
        ],
    )
    main = _straight_route(4.0)
    variant = _straight_route(2.0)
    rng = random.Random(4)
    personas = build_personas(config)
    trips = generate_trip_history(
        personas, {"main": main, "variant": variant}, config, rng,
    )
    by_route = {t.route_name for t in trips}
    assert by_route == {"main", "variant"}
    for trip in trips:
        limit = (main if trip.route_name == "main" else variant).length_m
        assert trip.alight_m <= limit + 1


def test_detour_route_spec_validation():
    config = ScenarioConfig(
        name="t",
        routes=[
            RouteSpec(name="main", path="a.geojson"),
            RouteSpec(name="works", path="d.geojson", role="detour",
                      from_day=7, to_day=14, fraction_of_trips=0.5),
        ],
    )
    assert config.routes[1].replaces == "main"  # defaults to first rideable


def test_scenario_yaml_roundtrip(tmp_path):
    config = _config(seed=99)
    path = tmp_path / "s.yaml"
    config.to_yaml(path)
    loaded = ScenarioConfig.from_yaml(path)
    assert loaded == config


def test_legacy_single_route_field_still_loads():
    config = ScenarioConfig(name="t", route_geojson="x.geojson")
    assert config.routes[0].path == "x.geojson"
    assert config.personas[0].route == "main"


def test_noise_layers_can_be_disabled_entirely():
    config = _config(noise=dict(
        gaussian_enabled=False, perpendicular_enabled=False,
        zigzag_enabled=False, jumps_enabled=False, missing_enabled=False,
        biased_drift_enabled=False, lateral_drift_enabled=False,
        timestamp_jitter_enabled=False,
    ))
    route = _straight_route()
    rng = random.Random(11)
    personas = build_personas(config)
    trips = generate_trip_history(personas, route, config, rng)
    trip = trips[0]
    trip.board_m, trip.alight_m, trip.forward = 0.0, route.length_m, True
    points = simulate_trip_points(trip, route, config, rng)
    # No noise at all: every point exactly on the corridor.
    assert all(abs(p.lat - (-17.3935)) * 111_320 < 0.01 for p in points)


def test_zigzag_oscillates_cross_track():
    config = _config(noise=dict(
        gaussian_enabled=False, perpendicular_enabled=False,
        missing_enabled=False, timestamp_jitter_enabled=False,
        zigzag_enabled=True, zigzag_amplitude_m=5.0, zigzag_period_points=6,
    ))
    route = _straight_route()
    rng = random.Random(12)
    personas = build_personas(config)
    trips = generate_trip_history(personas, route, config, rng)
    trip = trips[0]
    trip.board_m, trip.alight_m, trip.forward = 0.0, route.length_m, True
    points = simulate_trip_points(trip, route, config, rng)
    offsets = [(p.lat - (-17.3935)) * 111_320 for p in points]
    assert max(offsets) > 3.0 and min(offsets) < -3.0   # oscillates both ways
    assert max(abs(o) for o in offsets) <= 5.1          # bounded by amplitude


def test_effective_gps_accuracy_derivation():
    from simlab.runner import _effective_gps_accuracy_m

    config = _config(noise=dict(gaussian_sigma_m=3.0, perpendicular_sigma_m=1.5))
    spec = PersonaSpec(name="p", noise_multiplier=1.0)
    # sqrt(2*9 + 2.25) = 4.5 → 4
    assert _effective_gps_accuracy_m(config, spec) == 4
    cheap = PersonaSpec(name="q", noise_multiplier=2.0)
    assert _effective_gps_accuracy_m(config, cheap) == 9
    # Explicit override wins.
    config2 = _config(gps_accuracy_m=15)
    assert _effective_gps_accuracy_m(config2, spec) == 15
    # Disabled layers → floor.
    config3 = _config(noise=dict(gaussian_enabled=False, perpendicular_enabled=False))
    assert _effective_gps_accuracy_m(config3, spec) == 3


def test_backward_direction_reverses_trips():
    config = _config(
        personas=[PersonaSpec(name="p", count=1, direction="backward")],
        noise=dict(gaussian_enabled=False, perpendicular_enabled=False,
                   missing_enabled=False, timestamp_jitter_enabled=False),
    )
    route = _straight_route()  # west→east
    rng = random.Random(8)
    personas = build_personas(config)
    trips = generate_trip_history(personas, route, config, rng)
    trip = trips[0]
    assert trip.forward is False
    trip.board_m, trip.alight_m = 0.0, route.length_m
    points = simulate_trip_points(trip, route, config, rng)
    assert points[0].lon > points[-1].lon  # travels east→west


def test_correlated_noise_smooths_perpendicular_jaggedness():
    import math

    def tickiness(corr_time):
        config = _config(noise=dict(gaussian_sigma_m=6.0, perpendicular_sigma_m=3.0,
                                    missing_enabled=False, timestamp_jitter_enabled=False,
                                    gps_correlation_time_s=corr_time))
        route = _straight_route()
        rng = random.Random(4)
        trip = generate_trip_history(build_personas(config), route, config, rng)[0]
        trip.board_m, trip.alight_m = 0.0, route.length_m
        pts = simulate_trip_points(trip, route, config, rng)
        devs = []
        for i in range(1, len(pts) - 1):
            a, b, c = pts[i - 1], pts[i], pts[i + 1]
            base = math.hypot(c.lon - a.lon, c.lat - a.lat) or 1e-12
            devs.append(abs((c.lon - a.lon) * (a.lat - b.lat) -
                            (a.lon - b.lon) * (c.lat - a.lat)) / base * 111320)
        return sum(devs) / len(devs)

    white = tickiness(0.0)
    correlated = tickiness(20.0)
    # Correlated error wanders smoothly → much less point-to-point jag.
    assert correlated < white * 0.6, (white, correlated)
