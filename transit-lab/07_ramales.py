"""Ramal-detection scenarios for gap #7.

Authors synthetic ground-truth ramales for line 230 (Cochabamba),
generates noisy GPS traces along each, runs the clustering algorithm,
and visualises the assignment so the threshold can be tuned against
realistic geometry.

The unit tests in `packages/geodata/tests/test_ramales.py` already
prove correctness on tight synthetic inputs — this notebook validates
the same algorithm under simulated GPS noise on Cochabamba-scale
distances and produces figures for the thesis methodology section.
"""

import marimo

__generated_with = "0.23.3"
app = marimo.App(width="full")


@app.cell
def _():
    from components.navbar import navbar
    return (navbar,)


@app.cell
def _(navbar):
    navbar()
    return


@app.cell(hide_code=True)
def _():
    import marimo as mo
    mo.md(
        """
        # 07 — Ramal detection

        Three ground-truth ramales for line 230, simulated noisy GPS
        traces, and the clustering output. Use the threshold slider to
        see how the cluster boundaries shift.

        Decisions encoded here:

        - **Algorithm**: complete-linkage hierarchical agglomerative on
          pairwise discrete Fréchet (in metres). Justification: avoids
          the chaining problem (a single bridging trace would otherwise
          merge two real ramales).
        - **Default threshold**: 200m (~ 2 Cochabamba blocks).
        - **Label stability**: existing-label inheritance is
          best-match-wins.
        """
    )
    return (mo,)


@app.cell
def _():
    from datetime import datetime
    import pydeck as pdk
    import pandas as pd

    from geodata.ramales import cluster_traces_into_ramales
    from geodata.reconstruction.base import (
        ReconstructionPoint,
        ReconstructionTrace,
    )
    from geodata.simulate import generate_tracks
    return (
        ReconstructionPoint,
        ReconstructionTrace,
        cluster_traces_into_ramales,
        datetime,
        generate_tracks,
        pd,
        pdk,
    )


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        """
        ## Ground-truth ramales

        Three variants of line 230 sharing Beijing as the start and
        Sacaba as the end:

        - **Ramal A — directo**: Beijing → Av. América → Sacaba.
        - **Ramal B — vía Simón Lopez**: Beijing → Av. Simón Lopez →
          Av. Melchor Pérez → América → Sacaba.
        - **Ramal C — vía Pacata**: Beijing → América → Pacata → Sacaba.
        """
    )
    return


@app.cell
def _():
    # Cochabamba-ish coords. 0.001° lat ≈ 111m; 0.001° lon ≈ 106m here.
    RAMAL_A = [
        [-66.170, -17.390],   # Beijing
        [-66.165, -17.390],   # straight east on América
        [-66.160, -17.390],
        [-66.155, -17.390],
        [-66.150, -17.390],   # Sacaba
    ]
    RAMAL_B = [
        [-66.170, -17.390],   # Beijing
        [-66.168, -17.395],   # detour south to Simón Lopez
        [-66.163, -17.398],   # Melchor Pérez
        [-66.158, -17.395],
        [-66.155, -17.391],   # back up to América
        [-66.150, -17.390],   # Sacaba
    ]
    RAMAL_C = [
        [-66.170, -17.390],   # Beijing
        [-66.165, -17.390],   # América
        [-66.160, -17.390],
        [-66.158, -17.393],   # detour south to Pacata
        [-66.153, -17.393],
        [-66.150, -17.390],   # Sacaba
    ]
    return RAMAL_A, RAMAL_B, RAMAL_C


@app.cell(hide_code=True)
def _(mo):
    mo.md("## Simulation parameters")
    return


@app.cell
def _(mo):
    n_tracks_per_ramal = mo.ui.slider(
        start=3, stop=20, step=1, value=8,
        label="Traces per ramal",
    )
    noise_xy_m = mo.ui.slider(
        start=2, stop=30, step=1, value=8,
        label="GPS noise σ (m)",
    )
    threshold_m = mo.ui.slider(
        start=50, stop=400, step=10, value=200,
        label="Cluster threshold (m)",
    )
    min_cluster_size = mo.ui.slider(
        start=2, stop=10, step=1, value=3,
        label="Min cluster size",
    )
    mo.vstack([n_tracks_per_ramal, noise_xy_m, threshold_m, min_cluster_size])
    return min_cluster_size, n_tracks_per_ramal, noise_xy_m, threshold_m


@app.cell
def _(
    RAMAL_A,
    RAMAL_B,
    RAMAL_C,
    ReconstructionPoint,
    ReconstructionTrace,
    datetime,
    generate_tracks,
    n_tracks_per_ramal,
    noise_xy_m,
):
    def _simulate_ramal(name: str, route: list[list[float]], seed: int):
        config = {
            "sim_params": {
                "Number of tracks": n_tracks_per_ramal.value,
                "Sampling rate (s)": 2.0,
                "Base speed (m/s)": 8.0,
                "Speed jitter (%)": 12.0,
                "Target pts/track (0=auto)": 0,
                "Mean trace proportion (0-1)": 1.0,
                "Stddev trace proportion": 0.0,
            },
            "noise": {
                "Position": {
                    "Enabled": True,
                    "Stddev (m)": noise_xy_m.value,
                },
            },
        }
        records = generate_tracks(route, config, seed=seed)
        # Group records by track_id into ReconstructionTrace objects.
        by_id: dict[str, list[dict]] = {}
        for r in records:
            by_id.setdefault(str(r["track_id"]), []).append(r)
        traces = []
        for tid, rows in by_id.items():
            rows.sort(key=lambda r: r["point_index"])
            pts = [
                ReconstructionPoint(
                    longitude=r["longitude"], latitude=r["latitude"],
                    point_index=r["point_index"],
                    timestamp=r.get("timestamp") or datetime(2026, 1, 1),
                )
                for r in rows
            ]
            traces.append(ReconstructionTrace(
                trace_id=f"{name}-{tid}", points=pts,
            ))
        return traces

    traces_a = _simulate_ramal("a", RAMAL_A, seed=11)
    traces_b = _simulate_ramal("b", RAMAL_B, seed=22)
    traces_c = _simulate_ramal("c", RAMAL_C, seed=33)
    all_traces = traces_a + traces_b + traces_c
    return all_traces, traces_a, traces_b, traces_c


@app.cell(hide_code=True)
def _(mo):
    mo.md("## Clustering output")
    return


@app.cell
def _(
    all_traces,
    cluster_traces_into_ramales,
    min_cluster_size,
    threshold_m,
):
    clusters = cluster_traces_into_ramales(
        all_traces,
        distance_threshold_m=threshold_m.value,
        min_cluster_size=min_cluster_size.value,
    )
    return (clusters,)


@app.cell
def _(clusters, mo, pd):
    # Summary table.
    rows = [
        {
            "label": c.label,
            "n_traces": len(c.trace_ids),
            "medoid": c.medoid_trace_id,
            "ground_truth_majority": _majority_prefix(c.trace_ids),
        }
        for c in clusters
    ]
    summary = pd.DataFrame(rows)
    mo.vstack([
        mo.md(f"**{len(clusters)} cluster(s) detected.**"),
        mo.ui.table(summary) if not summary.empty else mo.md("_(no clusters)_"),
    ])
    return


@app.cell
def _():
    def _majority_prefix(trace_ids: list[str]) -> str:
        """Return the dominant ground-truth ramal label inside the cluster
        (`a`, `b`, `c` — extracted from the trace_id prefix authored by
        `_simulate_ramal`). Pure-cluster scenarios should return one
        letter; impure ones flag a clustering error."""
        from collections import Counter
        prefixes = [tid.split("-", 1)[0] for tid in trace_ids]
        counts = Counter(prefixes)
        total = sum(counts.values())
        return ", ".join(
            f"{prefix} ({count}/{total})" for prefix, count in counts.most_common()
        )
    return (_majority_prefix,)


@app.cell(hide_code=True)
def _(mo):
    mo.md("## Map")
    return


@app.cell
def _(RAMAL_A, RAMAL_B, RAMAL_C, all_traces, clusters, pd, pdk):
    # One color per cluster label. Unclustered (noise) traces in grey.
    palette = [
        [255, 99, 71],   # tomato — main
        [70, 130, 180],  # steel blue — r2
        [60, 179, 113],  # medium sea green — r3
        [255, 165, 0],   # orange — r4
    ]
    label_color: dict[str, list[int]] = {}
    for i, c in enumerate(clusters):
        label_color[c.label] = palette[i % len(palette)]

    # Build per-trace dataframe with cluster colour.
    by_trace: dict[str, str | None] = {}
    for cluster in clusters:
        for tid in cluster.trace_ids:
            by_trace[tid] = cluster.label

    trace_rows = []
    for trace in all_traces:
        label = by_trace.get(trace.trace_id)
        color = label_color.get(label, [180, 180, 180])  # grey for noise
        path = [[p.longitude, p.latitude] for p in trace.points]
        trace_rows.append({"trace_id": trace.trace_id, "label": label or "noise",
                           "color": color, "path": path})
    traces_df = pd.DataFrame(trace_rows)

    truth_df = pd.DataFrame([
        {"name": "Ramal A (directo)",       "color": [220, 220, 220], "path": RAMAL_A},
        {"name": "Ramal B (Simón Lopez)",   "color": [220, 220, 220], "path": RAMAL_B},
        {"name": "Ramal C (Pacata)",        "color": [220, 220, 220], "path": RAMAL_C},
    ])

    layer_truth = pdk.Layer(
        "PathLayer", data=truth_df, get_path="path", get_color="color",
        get_width=8, width_min_pixels=2, pickable=False,
    )
    layer_traces = pdk.Layer(
        "PathLayer", data=traces_df, get_path="path", get_color="color",
        get_width=3, width_min_pixels=1, pickable=True,
    )

    deck = pdk.Deck(
        layers=[layer_truth, layer_traces],
        initial_view_state=pdk.ViewState(
            latitude=-17.392, longitude=-66.160,
            zoom=13.5, bearing=0, pitch=0,
        ),
        map_style=None,
        tooltip={"text": "{trace_id}\nlabel: {label}"},
    )
    deck
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        """
        ## How to read the map

        - **Grey lines** = ground-truth ramales (the polylines used to
          generate traces).
        - **Coloured lines** = simulated noisy GPS traces, coloured by
          the cluster the algorithm assigned them to. Pure clusters
          (one colour per ground-truth ramal) means clustering worked.
        - **Grey traces** = traces that fell into a cluster smaller than
          `min_cluster_size` and were dropped as noise.

        ## Threshold tuning notes

        - **Default 200m**: usually clean separation for Cochabamba
          line 230 with 8m GPS noise.
        - **< 100m**: ramales B (vía Simón Lopez) tends to fragment —
          the simulator's noise pushes some of its points outside the
          tight cluster radius.
        - **> 300m**: ramal A (directo) and ramal C (vía Pacata) start
          merging because their northern halves overlap — complete
          linkage still resists chaining but the divergence becomes
          ambiguous.

        Numbers above are the calibration that justifies the
        `DEFAULT_RAMAL_DISTANCE_THRESHOLD_M = 200.0` constant in
        `pipeline/steps/reconstruct_routes.py`.
        """
    )
    return


if __name__ == "__main__":
    app.run()
