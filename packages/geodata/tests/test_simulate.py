from geodata.simulate import generate_tracks


def _base_config(
    mean_trace_proportion: float, stddev_trace_proportion: float = 0.0
) -> dict:
    return {
        "sim_params": {
            "Number of tracks": 1,
            "Sampling rate (s)": 10.0,
            "Base speed (m/s)": 10.0,
            "Speed jitter (%)": 0.0,
            "Target pts/track (0=auto)": 0,
            "Mean trace proportion (0-1)": mean_trace_proportion,
            "Stddev trace proportion": stddev_trace_proportion,
        },
        "noise": {
            "gaussian": {"Enabled": False},
            "perpendicular": {"Enabled": False},
            "zigzag": {"Enabled": False},
            "jumps": {"Enabled": False},
            "missing": {"Enabled": False},
            "biased_drift": {"Enabled": False},
            "lateral_drift": {"Enabled": False},
            "timestamp_jitter": {"Enabled": False},
        },
    }


def test_mean_trace_proportion_keeps_contiguous_random_subsequence():
    route = [[0.0, 0.0], [0.01, 0.0]]

    full_track = generate_tracks(route, _base_config(1.0), seed=7)
    partial_track = generate_tracks(route, _base_config(0.4), seed=7)

    full_points = [(p["longitude"], p["latitude"]) for p in full_track]
    partial_points = [(p["longitude"], p["latitude"]) for p in partial_track]

    assert len(full_points) > len(partial_points) >= 2

    expected_len = max(2, int(len(full_points) * 0.4 + 0.999999999))
    assert len(partial_points) == expected_len

    start_idx = full_points.index(partial_points[0])
    end_idx = start_idx + len(partial_points)
    assert full_points[start_idx:end_idx] == partial_points


def test_zero_mean_trace_proportion_still_emits_minimum_contiguous_trace():
    route = [[0.0, 0.0], [0.01, 0.0]]

    partial_track = generate_tracks(route, _base_config(0.0), seed=11)
    partial_points = [(p["longitude"], p["latitude"]) for p in partial_track]

    assert len(partial_points) == 2


def test_stddev_trace_proportion_randomizes_subset_length_but_keeps_contiguous():
    route = [[0.0, 0.0], [0.01, 0.0]]

    full_track = generate_tracks(route, _base_config(1.0), seed=3)
    randomized_track = generate_tracks(route, _base_config(0.6, 0.2), seed=3)

    full_points = [(p["longitude"], p["latitude"]) for p in full_track]
    randomized_points = [(p["longitude"], p["latitude"]) for p in randomized_track]

    assert 2 <= len(randomized_points) <= len(full_points)
    assert len(randomized_points) != len(full_points)

    start_idx = full_points.index(randomized_points[0])
    end_idx = start_idx + len(randomized_points)
    assert full_points[start_idx:end_idx] == randomized_points
