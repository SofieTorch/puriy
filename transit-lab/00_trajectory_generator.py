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
    import marimo as mo
    import pandas as pd
    import pydeck as pdk
    from pathlib import Path
    from branca.element import Element
    from folium.plugins import Draw

    from components.tracing import init_tracing
    from geodata.geojson import parse_route_from_geojson
    from database.connection import SessionLocal

    init_tracing()

    return (
        Draw,
        Element,
        Path,
        SessionLocal,
        folium,
        json,
        mo,
        parse_route_from_geojson,
        pd,
        pdk,
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
    get_save_db_message, set_save_db_message = mo.state("")
    return (
        get_active_tab,
        get_last_generate_click,
        get_loaded_config,
        get_save_db_message,
        get_simulated_points,
        get_simulation_message,
        set_active_tab,
        set_last_generate_click,
        set_loaded_config,
        set_save_db_message,
        set_simulated_points,
        set_simulation_message,
    )


@app.cell
def _(mo):
    export_filename = mo.ui.text(
        label="Export filename",
        value="trajectory.geojson",
        placeholder="my_route.geojson",
    )
    return (export_filename,)


@app.cell
def _(
    Draw,
    Element,
    export_filename,
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

        filename=export_filename.value or "trajectory.geojson",
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
    </style>"""))

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
                "1. Choose a filename &nbsp;&nbsp; 2. Draw the path &nbsp;&nbsp;"
                " 3. Click **Export** &nbsp;&nbsp; 4. Move the file to `seed/routes/` &nbsp;&nbsp;"
                " 5. Select it in the sidebar file browser"
            ),
            mo.hstack([export_filename], align="center"),
            mo.Html(draw_map._repr_html_()),
        ],
        gap=0.5,
        align="stretch",
    )
    return (draw_map_section,)


@app.cell
def _(Path, mo):
    _routes_dir = Path.cwd() / "seed" / "routes"
    _routes_dir.mkdir(parents=True, exist_ok=True)
    geojson_file_browser = mo.ui.file_browser(
        initial_path=_routes_dir,
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
        "Trace proportion (0-1)": mo.ui.number(value=_cfg.get("Trace proportion (0-1)", 1.0), start=0, stop=1, step=0.05),
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
    generate_tracks_button,
    geojson_file_browser,
    get_last_generate_click,
    noise_config,
    parse_route_from_geojson,
    set_active_tab,
    set_last_generate_click,
    set_simulated_points,
    set_simulation_message,
    sim_params,
):
    from geodata.simulate import generate_tracks

    generate_click = generate_tracks_button.value or 0
    if generate_click <= get_last_generate_click():
        pass  # no new click
    else:
        set_last_generate_click(generate_click)

        # Build config dict matching the saved JSON format
        _sp = sim_params.value
        _noise_cfg = {}
        for _key, _dict in noise_config.items():
            _vals = _dict.value
            _noise_cfg[_key] = {k: v for k, v in _vals.items() if k != "Description"}
        _config = {"sim_params": _sp, "noise": _noise_cfg}

        _seed_value = int(_sp["Seed (-1=random)"])

        # Load route
        _route_error = None
        try:
            if not geojson_file_browser.value:
                raise ValueError("Select a GeoJSON file first")
            _selected_path = str(geojson_file_browser.path(0))
            with open(_selected_path, encoding="utf-8") as _f:
                _route = parse_route_from_geojson(_f.read())
        except Exception as _exc:
            _route = []
            _route_error = str(_exc)

        if _route_error:
            set_simulated_points([])
            set_simulation_message(f"Route error: {_route_error}")
        elif len(_route) < 2:
            set_simulated_points([])
            set_simulation_message("Route needs at least 2 points.")
        else:
            _records = generate_tracks(
                _route,
                _config,
                seed=_seed_value if _seed_value >= 0 else None,
            )
            _num_tracks = max((r["track_id"] for r in _records), default=0)
            set_simulated_points(_records)
            set_simulation_message(
                f"Generated {_num_tracks} track(s) with {len(_records)} geopoint(s) total."
            )
            set_active_tab("Generated tracks")
    return


@app.cell
def _(SessionLocal, mo):
    from database.models import Line

    _db = SessionLocal()
    try:
        _lines = _db.query(Line).order_by(Line.name).all()
        _options = {f"{l.name} (id={l.id})": l.id for l in _lines}
    finally:
        _db.close()
    line_dropdown = mo.ui.dropdown(
        options=_options,
        label="Assign to line",
    )
    save_to_db_button = mo.ui.button(
        label="Save to database",
        value=0,
        on_click=lambda v: (v or 0) + 1,
        kind="success",
    )
    return line_dropdown, save_to_db_button


@app.cell
def _(
    get_save_db_message,
    get_simulated_points,
    get_simulation_message,
    line_dropdown,
    mo,
    pd,
    pdk,
    save_to_db_button,
):
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

        _db_msg = get_save_db_message()
        generated_tracks_section = mo.vstack(
            [
                mo.md(simulation_message),
                deck,
                preview_table,
                mo.md("---"),
                mo.md("### Save to database"),
                mo.hstack([line_dropdown, save_to_db_button], align="end", gap=0.5),
                mo.md(_db_msg) if _db_msg else mo.md(""),
            ],
            gap=1,
            align="stretch",
        )
    return (generated_tracks_section,)


@app.cell
def _(
    SessionLocal,
    get_simulated_points,
    line_dropdown,
    save_to_db_button,
    set_save_db_message,
):
    from geodata.persist import save_tracks_to_db

    if save_to_db_button.value:
        _records = get_simulated_points()
        _line_id = line_dropdown.value
        if not _records:
            set_save_db_message("No generated tracks to save.")
        elif not _line_id:
            set_save_db_message("Select a line first.")
        else:
            _db = SessionLocal()
            try:
                _sessions = save_tracks_to_db(_db, _records, line_id=_line_id)
                set_save_db_message(
                    f"Saved **{len(_sessions)}** trip session(s) to line **{_line_id}**."
                )
            except Exception as _exc:
                set_save_db_message(f"Error saving: {_exc}")
            finally:
                _db.close()
    return


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
    _config_dir = __import__("pathlib").Path.cwd() / "seed" / "config"
    _config_dir.mkdir(parents=True, exist_ok=True)
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
        initial_path=_config_dir,
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
        _path = __import__("pathlib").Path.cwd() / "seed" / "config" / (save_filename.value or "config.json")
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
