from geodata.simulate import generate_tracks


def _base_config(trace_proportion: float) -> dict:
    return {
        "sim_params": {
            "Number of tracks": 1,
            "Sampling rate (s)": 10.0,
            "Base speed (m/s)": 10.0,
            "Speed jitter (%)": 0.0,
            "Target pts/track (0=auto)": 0,
            "Trace proportion (0-1)": trace_proportion,
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


def test_trace_proportion_keeps_contiguous_random_subsequence():
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


def test_trace_proportion_zero_still_emits_minimum_contiguous_trace():
    route = [[0.0, 0.0], [0.01, 0.0]]

    partial_track = generate_tracks(route, _base_config(0.0), seed=11)
    partial_points = [(p["longitude"], p["latitude"]) for p in partial_track]

    assert len(partial_points) == 2
