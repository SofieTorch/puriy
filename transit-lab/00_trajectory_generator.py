import marimo

__generated_with = "0.20.4"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.Html("""<style>
        label { white-space: nowrap; }
        .markdown p { margin: 0; padding: 0; }
        input[type="number"] { max-width: 5em; }
    </style>""")
    return


@app.cell
def _():
    import json
    import folium
    import math
    import marimo as mo
    import pandas as pd
    import pydeck as pdk
    import random
    from pathlib import Path
    from datetime import datetime, timedelta
    from branca.element import Element
    from folium.plugins import Draw

    from geodata.geo_math import (
        haversine_m,
        heading_and_perp,
        interpolate_route,
        offset_lon_lat,
    )
    from geodata.geojson import parse_route_from_geojson

    return (
        Draw,
        Element,
        Path,
        datetime,
        folium,
        heading_and_perp,
        interpolate_route,
        json,
        math,
        mo,
        offset_lon_lat,
        parse_route_from_geojson,
        pd,
        pdk,
        random,
        timedelta,
    )


@app.cell
def _(mo):
    get_last_generate_click, set_last_generate_click = mo.state(0)
    get_simulated_points, set_simulated_points = mo.state([])
    get_simulation_message, set_simulation_message = mo.state(
        "Set your controls and click **Generate simulated tracks**."
    )
    get_active_tab, set_active_tab = mo.state("Draw path")
    get_loaded_config, set_loaded_config = mo.state(None)
    return (
        get_active_tab,
        get_last_generate_click,
        get_loaded_config,
        get_simulated_points,
        get_simulation_message,
        set_active_tab,
        set_last_generate_click,
        set_loaded_config,
        set_simulated_points,
        set_simulation_message,
    )


@app.cell
def _(
    Draw,
    Element,
    folium,
    geojson_file_browser,
    mo,
    parse_route_from_geojson,
):
    draw_map = folium.Map(
        location=[-17.3895, -66.1568],
        zoom_start=13,
        tiles="CartoDB positron",
        control_scale=True,
    )

    Draw(
        export=True,
        filename="trajectory.geojson",
        position="topleft",
        draw_options={
            "polyline": True,
            "polygon": False,
            "rectangle": False,
            "circle": False,
            "marker": False,
            "circlemarker": False,
        },
        edit_options={"edit": False, "remove": True},
    ).add_to(draw_map)

    draw_map.get_root().html.add_child(Element("""<style>
        #export {
            background-color: #22c55e !important;
            color: white !important;
            padding: 6px 16px !important;
            border-radius: 4px !important;
            font-weight: 600 !important;
            font-size: 13px !important;
            text-decoration: none !important;
            box-shadow: 0 2px 4px rgba(0,0,0,0.2) !important;
            z-index: 1000 !important;
            position: absolute !important;
            top: 12px !important;
            right: 12px !important;
            left: auto !important;
            bottom: auto !important;
        }
        #export:hover {
            background-color: #16a34a !important;
        }
    </style>
    <script>
        document.addEventListener('DOMContentLoaded', function() {
            var exp = document.getElementById('export');
            if (exp && window.showSaveFilePicker) {
                exp.addEventListener('click', async function(e) {
                    e.preventDefault();
                    e.stopPropagation();
                    try {
                        var handle = await window.showSaveFilePicker({
                            suggestedName: 'trajectory.geojson',
                            types: [{description: 'GeoJSON', accept: {'application/geo+json': ['.geojson']}}]
                        });
                        var blob = new Blob([exp.href.startsWith('data:')
                            ? decodeURIComponent(exp.href.split(',')[1])
                            : ''], {type: 'application/geo+json'});
                        var writable = await handle.createWritable();
                        await writable.write(blob);
                        await writable.close();
                    } catch (err) {
                        if (err.name !== 'AbortError') exp.click();
                    }
                }, true);
            }
        });
    </script>"""))

    # Overlay the selected GeoJSON route
    _selected_path = geojson_file_browser.path(0) if geojson_file_browser.value else None
    if _selected_path:
        try:
            with open(_selected_path, encoding="utf-8") as _f:
                route_coords = parse_route_from_geojson(_f.read())
            if len(route_coords) >= 2:
                folium.PolyLine(
                    locations=[[lat, lon] for lon, lat in route_coords],
                    color="#6366f1",
                    weight=3,
                    opacity=0.7,
                    dash_array="8",
                ).add_to(draw_map)
                lats = [c[1] for c in route_coords]
                lons = [c[0] for c in route_coords]
                draw_map.fit_bounds([[min(lats), min(lons)], [max(lats), max(lons)]])
        except Exception:
            pass

    draw_map_section = mo.vstack(
        [
            mo.md(
                "Use the polyline tool to draw the path, then **Export** it as GeoJSON."
            ),
            mo.Html(draw_map._repr_html_()),
        ],
        gap=0.5,
        align="stretch",
    )
    return (draw_map_section,)


@app.cell
def _(Path, mo):
    geojson_file_browser = mo.ui.file_browser(
        initial_path=Path.cwd(),
        filetypes=[".geojson"],
        multiple=False,
        label="Select a GeoJSON file",
    )
    return (geojson_file_browser,)


@app.cell
def _(get_loaded_config, mo):
    _cfg = (get_loaded_config() or {}).get("sim_params", {})

    sim_params = mo.ui.dictionary({
        "Number of tracks": mo.ui.number(value=_cfg.get("Number of tracks", 5), start=1, stop=500, step=1),
        "Sampling rate (s)": mo.ui.number(value=_cfg.get("Sampling rate (s)", 2.0), start=0.2, step=0.5),
        "Base speed (m/s)": mo.ui.number(value=_cfg.get("Base speed (m/s)", 8.0), start=0.5, step=0.5),
        "Speed jitter (%)": mo.ui.number(value=_cfg.get("Speed jitter (%)", 12.0), start=0, step=1),
        "Target pts/track (0=auto)": mo.ui.number(value=_cfg.get("Target pts/track (0=auto)", 0), start=0, step=10),
        "Seed (-1=random)": mo.ui.number(value=_cfg.get("Seed (-1=random)", 42), start=-1, step=1),
    }, label="General sampling")

    generate_tracks_button = mo.ui.button(
        label="Generate simulated tracks",
        value=0,
        on_click=lambda v: (v or 0) + 1,
        kind="success",
    )
    return generate_tracks_button, sim_params


@app.cell
def _(get_loaded_config, mo):
    _ncfg = (get_loaded_config() or {}).get("noise", {})

    def _nval(key: str, param: str, default):
        return _ncfg.get(key, {}).get(param, default)

    def _noise(key: str, name: str, tip: str, params: dict):
        return mo.ui.dictionary({
            "Enabled": mo.ui.checkbox(value=_nval(key, "Enabled", True)),
            "Description": mo.md(tip).batch(),
            **params,
        }, label=name)

    noise_config = {
        "gaussian": _noise("gaussian", "Gaussian GPS noise",
            "*Adds random isotropic noise to each point, simulating typical GPS inaccuracy.*",
            {"Sigma (m)": mo.ui.number(value=_nval("gaussian", "Sigma (m)", 3.0), start=0, step=0.5)}),
        "perpendicular": _noise("perpendicular", "Perpendicular road noise",
            "*Adds noise perpendicular to the road direction, simulating lane-width uncertainty.*",
            {"Sigma (m)": mo.ui.number(value=_nval("perpendicular", "Sigma (m)", 2.0), start=0, step=0.5)}),
        "zigzag": _noise("zigzag", "Zig-zag noise",
            "*Adds a periodic sine-wave offset perpendicular to the path, simulating systematic oscillation.*",
            {"Amplitude (m)": mo.ui.number(value=_nval("zigzag", "Amplitude (m)", 1.5), start=0, step=0.5),
             "Period (points)": mo.ui.number(value=_nval("zigzag", "Period (points)", 8), start=2, step=1)}),
        "jumps": _noise("jumps", "Random jumps",
            "*Occasionally teleports a point to a random nearby location, simulating GPS multipath errors.*",
            {"Probability": mo.ui.number(value=_nval("jumps", "Probability", 0.02), start=0, stop=1, step=0.01),
             "Distance (m)": mo.ui.number(value=_nval("jumps", "Distance (m)", 40.0), start=0, step=5)}),
        "missing": _noise("missing", "Missing points",
            "*Randomly drops points from the track, simulating signal loss or sampling gaps.*",
            {"Probability": mo.ui.number(value=_nval("missing", "Probability", 0.03), start=0, stop=0.95, step=0.01)}),
        "biased_drift": _noise("biased_drift", "Biased drift",
            "*Accumulates a constant offset in a fixed direction over time, simulating receiver bias drift.*",
            {"Drift (m/pt)": mo.ui.number(value=_nval("biased_drift", "Drift (m/pt)", 0.05), start=0, step=0.01),
             "Bearing (deg)": mo.ui.number(value=_nval("biased_drift", "Bearing (deg)", 70.0), start=0, stop=360, step=5)}),
        "lateral_drift": _noise("lateral_drift", "Lateral drift",
            "*Gradually shifts the track sideways along its length, simulating systematic lateral error.*",
            {"Total (m)": mo.ui.number(value=_nval("lateral_drift", "Total (m)", 3.0), step=0.5)}),
        "timestamp_jitter": _noise("timestamp_jitter", "Timestamp jitter",
            "*Adds random variation to the time interval between points, simulating irregular sampling.*",
            {"Sigma (s)": mo.ui.number(value=_nval("timestamp_jitter", "Sigma (s)", 0.15), start=0, step=0.05)}),
    }
    return (noise_config,)


@app.cell
def _(
    generate_tracks_button,
    geojson_file_browser,
    mo,
    noise_config,
    sim_params,
):
    mo.sidebar(
        [
            mo.md("## Trajectory generator"),
            mo.md("---"),
            geojson_file_browser,
            mo.md("---"),
            sim_params,
            mo.md("---"),
            noise_config["gaussian"],
            noise_config["perpendicular"],
            noise_config["zigzag"],
            mo.md("---"),
            noise_config["jumps"],
            noise_config["missing"],
            mo.md("---"),
            noise_config["biased_drift"],
            noise_config["lateral_drift"],
            noise_config["timestamp_jitter"],
            mo.md("---"),
            generate_tracks_button,
        ],
        width="310px",
    )
    return


@app.cell
def _(
    datetime,
    generate_tracks_button,
    geojson_file_browser,
    get_last_generate_click,
    heading_and_perp,
    interpolate_route,
    math,
    noise_config,
    offset_lon_lat,
    parse_route_from_geojson,
    random,
    set_active_tab,
    set_last_generate_click,
    set_simulated_points,
    set_simulation_message,
    sim_params,
    timedelta,
):
    def _on(key: str) -> bool:
        return noise_config[key].value["Enabled"]

    def _p(key: str, param: str) -> float:
        return noise_config[key].value[param]

    generate_click = generate_tracks_button.value or 0
    if generate_click <= get_last_generate_click():
        pass  # no new click
    else:
        set_last_generate_click(generate_click)

        # General params from sim_params dictionary
        _sp = sim_params.value
        num_tracks = _sp["Number of tracks"]
        sampling_rate_s = _sp["Sampling rate (s)"]
        base_speed_mps = _sp["Base speed (m/s)"]
        speed_jitter_pct = _sp["Speed jitter (%)"]
        target_points = _sp["Target pts/track (0=auto)"]
        seed_value = int(_sp["Seed (-1=random)"])

        # Noise params
        gaussian_m = _p("gaussian", "Sigma (m)")
        perpendicular_m = _p("perpendicular", "Sigma (m)")
        zigzag_amp_m = _p("zigzag", "Amplitude (m)")
        zigzag_period = max(2, int(_p("zigzag", "Period (points)")))
        jump_prob = _p("jumps", "Probability")
        jump_dist_mean = _p("jumps", "Distance (m)")
        missing_prob = _p("missing", "Probability")
        drift_step = _p("biased_drift", "Drift (m/pt)")
        drift_bearing = math.radians(_p("biased_drift", "Bearing (deg)"))
        lat_drift_total = _p("lateral_drift", "Total (m)")
        ts_jitter = _p("timestamp_jitter", "Sigma (s)")

        # Load route
        route_error = None
        try:
            if not geojson_file_browser.value:
                raise ValueError("Select a GeoJSON file first")
            selected_path = str(geojson_file_browser.path(0))
            with open(selected_path, encoding="utf-8") as f:
                route = parse_route_from_geojson(f.read())
        except Exception as exc:
            route = []
            route_error = str(exc)

        if route_error:
            set_simulated_points([])
            set_simulation_message(f"Route error: {route_error}")
        elif len(route) < 2:
            set_simulated_points([])
            set_simulation_message("Route needs at least 2 points.")
        else:
            records = []
            start_time = datetime.utcnow().replace(microsecond=0)

            for track_idx in range(num_tracks):
                track_seed = None if seed_value < 0 else seed_value + track_idx * 1009
                rng = random.Random(track_seed)

                speed_factor = max(0.1, 1 + rng.gauss(0, speed_jitter_pct / 100.0))
                step_m = max(0.5, base_speed_mps * speed_factor * sampling_rate_s)
                base_points = interpolate_route(route, step_m)

                if target_points > 1 and len(base_points) > target_points:
                    idxs = [
                        round(i * (len(base_points) - 1) / (target_points - 1))
                        for i in range(target_points)
                    ]
                    base_points = [base_points[i] for i in idxs]

                drift_acc_m = 0.0
                noisy_points = []
                elapsed_s = 0.0

                for i, (lon, lat) in enumerate(base_points):
                    _, perp = heading_and_perp(base_points, i)
                    east_m = 0.0
                    north_m = 0.0

                    if _on("gaussian"):
                        east_m += rng.gauss(0, gaussian_m)
                        north_m += rng.gauss(0, gaussian_m)

                    if _on("perpendicular") and perpendicular_m > 0:
                        perp_offset = rng.gauss(0, perpendicular_m)
                        east_m += perp[0] * perp_offset
                        north_m += perp[1] * perp_offset

                    if _on("zigzag") and zigzag_amp_m > 0:
                        zigzag_offset = zigzag_amp_m * math.sin(
                            (2 * math.pi * i) / zigzag_period
                        )
                        east_m += perp[0] * zigzag_offset
                        north_m += perp[1] * zigzag_offset

                    if (
                        _on("jumps")
                        and jump_prob > 0
                        and rng.random() < jump_prob
                        and jump_dist_mean > 0
                    ):
                        jump_angle = rng.uniform(0, 2 * math.pi)
                        jump_dist = max(
                            0.0, rng.gauss(jump_dist_mean, jump_dist_mean * 0.35)
                        )
                        east_m += math.cos(jump_angle) * jump_dist
                        north_m += math.sin(jump_angle) * jump_dist

                    if _on("biased_drift"):
                        drift_acc_m += drift_step
                        east_m += math.sin(drift_bearing) * drift_acc_m
                        north_m += math.cos(drift_bearing) * drift_acc_m

                    if (
                        _on("lateral_drift")
                        and len(base_points) > 1
                        and lat_drift_total != 0
                    ):
                        lateral_progress = i / (len(base_points) - 1)
                        lateral_offset = lateral_progress * lat_drift_total
                        east_m += perp[0] * lateral_offset
                        north_m += perp[1] * lateral_offset

                    nlon, nlat = offset_lon_lat(lon, lat, east_m, north_m)

                    if i > 0:
                        jitter = rng.gauss(0, ts_jitter) if _on("timestamp_jitter") else 0.0
                        elapsed_s += max(0.2, sampling_rate_s + jitter)

                    noisy_points.append((nlon, nlat, elapsed_s))

                if _on("missing"):
                    kept_points = []
                    for i, point in enumerate(noisy_points):
                        if i in (0, len(noisy_points) - 1) or rng.random() >= missing_prob:
                            kept_points.append(point)
                    if len(kept_points) < 2 and len(noisy_points) >= 2:
                        kept_points = [noisy_points[0], noisy_points[-1]]
                else:
                    kept_points = noisy_points

                track_start = start_time + timedelta(minutes=track_idx)
                for point_idx, (plon, plat, t_s) in enumerate(kept_points):
                    timestamp = track_start + timedelta(seconds=t_s)
                    records.append(
                        {
                            "track_id": track_idx + 1,
                            "point_index": point_idx + 1,
                            "timestamp": timestamp.isoformat(),
                            "longitude": plon,
                            "latitude": plat,
                        }
                    )

            set_simulated_points(records)
            set_simulation_message(
                f"Generated {num_tracks} track(s) with {len(records)} geopoint(s) total."
            )
            set_active_tab("Generated tracks")
    return


@app.cell
def _(get_simulated_points, get_simulation_message, mo, pd, pdk):
    generated_records = get_simulated_points()
    simulation_message = get_simulation_message()

    if not generated_records:
        generated_tracks_section = mo.md(simulation_message)
    else:
        generated_df = pd.DataFrame(generated_records)
        preview_table = mo.ui.table(
            data=generated_df.head(300),
            label="Generated geopoints (first 300 rows)",
            pagination=True,
        )

        palette = [
            [59, 130, 246],
            [34, 197, 94],
            [234, 179, 8],
            [168, 85, 247],
            [236, 72, 153],
            [20, 184, 166],
        ]
        path_layer_data = []
        for idx, (track_id, group) in enumerate(
            generated_df.sort_values(["track_id", "point_index"]).groupby("track_id")
        ):
            path_layer_data.append(
                {
                    "track_id": int(track_id),
                    "path": group[["longitude", "latitude"]].values.tolist(),
                    "color": palette[idx % len(palette)],
                }
            )

        center_lat = float(generated_df["latitude"].mean())
        center_lon = float(generated_df["longitude"].mean())
        deck = pdk.Deck(
            map_style="light",
            map_provider="carto",
            initial_view_state=pdk.ViewState(
                latitude=center_lat,
                longitude=center_lon,
                zoom=13,
                pitch=0,
                bearing=0,
            ),
            layers=[
                pdk.Layer(
                    "PathLayer",
                    path_layer_data,
                    get_path="path",
                    get_color="color",
                    get_width=0.5,
                    width_min_pixels=1,
                    pickable=True,
                )
            ],
            tooltip={"text": "Track {track_id}"},
            height=420,
        )

        generated_tracks_section = mo.vstack(
            [
                mo.md(simulation_message),
                deck,
                preview_table,
            ],
            gap=1,
            align="stretch",
        )
    return (generated_tracks_section,)


@app.cell
def _(
    draw_map_section,
    generated_tracks_section,
    get_active_tab,
    mo,
    save_load_config_section,
):
    mo.ui.tabs(
        {
            "Draw path": draw_map_section,
            "Generated tracks": generated_tracks_section,
            "Configuration": save_load_config_section,
        },
        value=get_active_tab(),
    )
    return


@app.cell
def _(mo):
    save_filename = mo.ui.text(
        label="Filename",
        value="config.json",
        placeholder="config.json",
    )
    save_button = mo.ui.button(
        label="Save config",
        value=0,
        on_click=lambda v: (v or 0) + 1,
        kind="success",
    )
    load_browser = mo.ui.file_browser(
        initial_path=__import__("pathlib").Path.cwd(),
        filetypes=[".json"],
        multiple=False,
        label="Select a config file to load",
    )
    return load_browser, save_button, save_filename


@app.cell
def _(
    json,
    load_browser,
    mo,
    noise_config,
    save_button,
    save_filename,
    sim_params,
):
    _save_msg = ""
    if save_button.value:
        _cfg = {"sim_params": sim_params.value, "noise": {}}
        for _key, _dict in noise_config.items():
            _vals = _dict.value
            _cfg["noise"][_key] = {
                k: v for k, v in _vals.items() if k != "Description"
            }
        _path = save_filename.value or "config.json"
        with open(_path, "w", encoding="utf-8") as _f:
            json.dump(_cfg, _f, indent=2)
        _save_msg = f"Saved to `{_path}`"

    save_load_config_section = mo.vstack([
        mo.md("### Save config"),
        mo.hstack([save_filename, save_button], align="end", gap=0.5),
        mo.md(_save_msg) if _save_msg else mo.md(""),
        mo.md("---"),
        mo.md("### Load config"),
        load_browser,
    ], gap=0.5)
    return (save_load_config_section,)


@app.cell
def _(json, load_browser, set_loaded_config):
    if load_browser.value:
        _path = load_browser.path(0)
        with open(_path, encoding="utf-8") as _f:
            _cfg = json.load(_f)
        set_loaded_config(_cfg)
    return


if __name__ == "__main__":
    app.run()
