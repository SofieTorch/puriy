import marimo

__generated_with = "0.20.4"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    from components.styles import GLOBAL_STYLES

    mo.Html(GLOBAL_STYLES)
    return


@app.cell
def _():
    import json
    import marimo as mo
    import pandas as pd
    import pydeck as pdk
    from pathlib import Path

    from components.tracing import init_tracing
    from geodata.geojson import parse_route_from_geojson
    from database.connection import SessionLocal

    init_tracing()
    return Path, SessionLocal, json, mo, parse_route_from_geojson, pd, pdk


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
    get_noise_zones, set_noise_zones = mo.state([])
    return (
        get_active_tab,
        get_last_generate_click,
        get_loaded_config,
        get_noise_zones,
        get_save_db_message,
        get_simulated_points,
        get_simulation_message,
        set_active_tab,
        set_last_generate_click,
        set_loaded_config,
        set_noise_zones,
        set_save_db_message,
        set_simulated_points,
        set_simulation_message,
    )


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
def _(mo):
    export_filename = mo.ui.text(
        label="Export filename",
        value="trajectory.geojson",
        placeholder="my_route.geojson",
    )
    return (export_filename,)


@app.cell
def _(export_filename, geojson_file_browser, mo, parse_route_from_geojson):
    from components.maps import create_draw_map, overlay_route

    _draw_map = create_draw_map(
        export_filename=export_filename.value or "trajectory.geojson",
        draw_polyline=True,
    )

    _selected_path = geojson_file_browser.path(0) if geojson_file_browser.value else None
    if _selected_path:
        try:
            with open(_selected_path, encoding="utf-8") as _f:
                _route = parse_route_from_geojson(_f.read())
            overlay_route(_draw_map, _route)
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
            mo.Html(_draw_map._repr_html_()),
        ],
        gap=0.5,
        align="stretch",
    )
    return (draw_map_section,)


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
def _(get_loaded_config):
    from components.noise_ui import build_noise_config

    noise_config = build_noise_config(get_loaded_config())
    return (noise_config,)


@app.cell
def _(Path, mo):
    _zones_dir = Path.cwd() / "seed" / "zones"
    _zones_dir.mkdir(parents=True, exist_ok=True)
    zones_file_browser = mo.ui.file_browser(
        initial_path=_zones_dir,
        filetypes=[".geojson"],
        multiple=False,
        label="Load zones GeoJSON",
    )
    default_zone_mult = mo.ui.number(
        value=3.0,
        start=1.0,
        step=0.5,
        label="Default multiplier",
    )
    return default_zone_mult, zones_file_browser


@app.cell
def _(default_zone_mult, set_noise_zones, zones_file_browser):
    import json as _json

    if zones_file_browser.value:
        try:
            with open(zones_file_browser.path(0), encoding="utf-8") as _f:
                _gj = _json.load(_f)
            _zones = []
            for _feat in _gj.get("features", []):
                _mult = float(
                    (_feat.get("properties") or {}).get(
                        "multiplier", default_zone_mult.value
                    )
                )
                _zones.append({"geometry": _feat["geometry"], "multiplier": _mult})
            set_noise_zones(_zones)
        except Exception:
            set_noise_zones([])
    else:
        set_noise_zones([])
    return


@app.cell
def _(geojson_file_browser, mo, parse_route_from_geojson):
    from components.maps import create_draw_map as _create_draw_map
    from components.maps import overlay_route as _overlay_route

    _zones_map = _create_draw_map(
        export_filename="zones.geojson",
        draw_polygon=True,
        draw_rectangle=True,
        edit=True,
        button_color="#f59e0b",
        button_hover_color="#d97706",
    )

    _selected_path = geojson_file_browser.path(0) if geojson_file_browser.value else None
    if _selected_path:
        try:
            with open(_selected_path, encoding="utf-8") as _f:
                _route = parse_route_from_geojson(_f.read())
            _overlay_route(_zones_map, _route)
        except Exception:
            pass

    zones_map_section = mo.vstack([
        mo.md(
            "1. Draw polygons over the noisy areas &nbsp;&nbsp; "
            "2. Click **Export** (saves `zones.geojson`) &nbsp;&nbsp; "
            "3. Move the file to `seed/zones/` &nbsp;&nbsp; "
            "4. Load it with the sidebar file browser"
        ),
        mo.md(
            "Add a `multiplier` property to each feature in the GeoJSON "
            "to override the default multiplier per zone."
        ),
        mo.Html(_zones_map._repr_html_()),
    ], gap=0.5, align="stretch")
    return (zones_map_section,)


@app.cell
def _(
    default_zone_mult,
    generate_tracks_button,
    geojson_file_browser,
    mo,
    noise_config,
    sim_params,
    zones_file_browser,
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
            noise_config["ou_drift"],
            mo.md("---"),
            mo.md("**Noise zones**"),
            zones_file_browser,
            default_zone_mult,
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
    get_noise_zones,
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

        _sp = sim_params.value
        _noise_cfg = {}
        for _key, _dict in noise_config.items():
            _vals = _dict.value
            _noise_cfg[_key] = {k: v for k, v in _vals.items() if k != "Description"}
        _config = {"sim_params": _sp, "noise": _noise_cfg}

        _seed_value = int(_sp["Seed (-1=random)"])

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
            from shapely.geometry import shape as _shape
            _raw_zones = get_noise_zones()
            _zones = (
                [{"polygon": _shape(z["geometry"]), "multiplier": z["multiplier"]} for z in _raw_zones]
                if _raw_zones else None
            )
            _records = generate_tracks(
                _route,
                _config,
                seed=_seed_value if _seed_value >= 0 else None,
                noise_zones=_zones,
            )
            _num_tracks = max((r["track_id"] for r in _records), default=0)
            _has_accuracy = any("accuracy" in r for r in _records)
            _zone_info = f", {len(_zones)} zone(s) active" if _zones else ""
            _acc_info = " · accuracy tracked" if _has_accuracy else ""
            set_simulated_points(_records)
            set_simulation_message(
                f"Generated {_num_tracks} track(s) with {len(_records)} geopoint(s) total"
                f"{_zone_info}{_acc_info}."
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
    from components.tracks_viz import build_path_layers

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

        _layers, _tooltip = build_path_layers(generated_df)

        deck = pdk.Deck(
            map_style="light",
            map_provider="carto",
            initial_view_state=pdk.ViewState(
                latitude=float(generated_df["latitude"].mean()),
                longitude=float(generated_df["longitude"].mean()),
                zoom=13,
                pitch=0,
                bearing=0,
            ),
            layers=_layers,
            tooltip=_tooltip,
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
    zones_map_section,
):
    mo.ui.tabs(
        {
            "Draw path": draw_map_section,
            "Noise zones": zones_map_section,
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
