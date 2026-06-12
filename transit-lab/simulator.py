import marimo

__generated_with = "0.23.3"
app = marimo.App(width="full")


@app.cell
def _():
    from pathlib import Path

    import marimo as mo
    from components.navbar import navbar

    return Path, mo, navbar


@app.cell
def _(navbar):
    navbar()
    return


@app.cell
def _():
    from database.connection import SessionLocal

    db = SessionLocal()
    return (db,)


@app.cell
def _(mo):
    get_loaded_config, set_loaded_config = mo.state(None)
    get_estimated_config, set_estimated_config = mo.state(None)
    get_fit_message, set_fit_message = mo.state("")
    return (
        get_estimated_config,
        get_fit_message,
        get_loaded_config,
        set_estimated_config,
        set_fit_message,
        set_loaded_config,
    )


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ### Route source
    """)
    return


@app.cell
def _(db, mo):
    from components.data import load_lines as _load_lines

    _lines = _load_lines(db)
    _options = {row["name"]: row["id"] for row in _lines}
    line_source = mo.ui.dropdown(options=_options, label="Load route from line")
    line_source
    return (line_source,)


@app.cell
def _(Path, mo):
    _seed_dir = Path(__file__).parent / "seed"
    _seed_dir.mkdir(parents=True, exist_ok=True)
    seed_file_browser = mo.ui.file_browser(
        initial_path=_seed_dir,
        filetypes=[".geojson"],
        multiple=False,
        label="Server seed files",
        restrict_navigation=True,
    )
    return (seed_file_browser,)


@app.cell
def _(mo):
    export_filename = mo.ui.text(
        label="Export filename",
        value="trajectory.geojson",
        placeholder="my_route.geojson",
    )
    return (export_filename,)


@app.cell
def _(export_filename, mo, seed_file_browser):
    import folium
    from branca.element import Element
    from folium.plugins import Draw

    m = folium.Map(location=[-17.3935, -66.1570], zoom_start=14, tiles="CartoDB positron")
    Draw(
        export=True,
        filename=export_filename.value or "trajectory.geojson",
        draw_options={
            "polyline": {"shapeOptions": {"color": "#3b82f6", "weight": 4}},
            "polygon": False,
            "rectangle": False,
            "circle": False,
            "circlemarker": False,
            "marker": False,
        },
        edit_options={"edit": True, "remove": True},
    ).add_to(m)

    # Style the Leaflet-draw export button (top-right, green).
    m.get_root().html.add_child(Element("""<style>
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

    # Overlay the selected seed-file route as a dashed reference line.
    # (Added directly to the map, not to the draw layer, so Export ignores it.)
    if seed_file_browser.value:
        from geodata.geojson import parse_route_from_geojson as _parse

        try:
            _selected = seed_file_browser.path(0)
            with open(_selected, encoding="utf-8") as _f:
                _coords = _parse(_f.read())
            if len(_coords) >= 2:
                folium.PolyLine(
                    locations=[[lat, lon] for lon, lat in _coords],
                    color="#6366f1",
                    weight=3,
                    opacity=0.8,
                    dash_array="8",
                ).add_to(m)
                _lats = [c[1] for c in _coords]
                _lons = [c[0] for c in _coords]
                m.fit_bounds([[min(_lats), min(_lons)], [max(_lats), max(_lons)]])
        except Exception:
            pass

    draw_map = mo.Html(m._repr_html_())
    mo.vstack(
        [
            mo.md(
                "Draw a polyline, then click the green **Export** button (top-right of "
                "the map) to download it as GeoJSON. A dashed line from a loaded file is "
                "**not** exported — only the polyline you draw."
            ),
            mo.hstack([export_filename], align="center"),
            mo.hstack([draw_map, seed_file_browser], gap=1, align="start", widths=[3, 1]),
        ],
        gap=0.5,
        align="stretch",
    )
    return


@app.cell
def _(mo):
    geojson_upload = mo.ui.file(filetypes=[".geojson", ".json"], label="Or upload GeoJSON")
    geojson_upload
    return (geojson_upload,)


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ### Simulation parameters
    """)
    return


@app.cell
def _(get_loaded_config, mo):
    _cfg = (get_loaded_config() or {}).get("sim_params", {})
    sim_params = mo.ui.dictionary(
        {
            "Number of tracks": mo.ui.number(value=_cfg.get("Number of tracks", 5), start=1, stop=500, step=1, label="Number of tracks"),
            "Sampling rate (s)": mo.ui.number(value=_cfg.get("Sampling rate (s)", 2.0), start=0.2, step=0.5, label="Sampling rate (s)"),
            "Base speed (m/s)": mo.ui.number(value=_cfg.get("Base speed (m/s)", 8.0), start=0.5, step=0.5, label="Base speed (m/s)"),
            "Speed jitter (%)": mo.ui.number(value=_cfg.get("Speed jitter (%)", 12.0), start=0.0, step=1.0, label="Speed jitter (%)"),
            "Mean trace proportion (0-1)": mo.ui.number(value=_cfg.get("Mean trace proportion (0-1)", 1.0), start=0.0, stop=1.0, step=0.05, label="Mean trace proportion"),
            "Stddev trace proportion": mo.ui.number(value=_cfg.get("Stddev trace proportion", 0.0), start=0.0, step=0.05, label="Stddev trace proportion"),
        }
    )
    sim_params
    return (sim_params,)


@app.cell
def _(get_loaded_config, mo):
    _ncfg = (get_loaded_config() or {}).get("noise", {})

    def _nval(key, param, default):
        return _ncfg.get(key, {}).get(param, default)

    noise_config = mo.ui.dictionary(
        {
            "gaussian": mo.ui.dictionary({
                "Enabled": mo.ui.switch(value=_nval("gaussian", "Enabled", True), label="Enabled"),
                "Sigma (m)": mo.ui.number(value=_nval("gaussian", "Sigma (m)", 4.0), start=0.0, step=0.5, label="Sigma (m)"),
            }),
            "perpendicular": mo.ui.dictionary({
                "Enabled": mo.ui.switch(value=_nval("perpendicular", "Enabled", True), label="Enabled"),
                "Sigma (m)": mo.ui.number(value=_nval("perpendicular", "Sigma (m)", 3.0), start=0.0, step=0.5, label="Sigma (m)"),
            }),
            "zigzag": mo.ui.dictionary({
                "Enabled": mo.ui.switch(value=_nval("zigzag", "Enabled", False), label="Enabled"),
                "Amplitude (m)": mo.ui.number(value=_nval("zigzag", "Amplitude (m)", 1.5), start=0.0, step=0.5, label="Amplitude (m)"),
                "Period (points)": mo.ui.number(value=_nval("zigzag", "Period (points)", 8), start=2, step=1, label="Period (points)"),
            }),
            "jumps": mo.ui.dictionary({
                "Enabled": mo.ui.switch(value=_nval("jumps", "Enabled", False), label="Enabled"),
                "Probability": mo.ui.number(value=_nval("jumps", "Probability", 0.02), start=0.0, stop=1.0, step=0.01, label="Probability"),
                "Distance (m)": mo.ui.number(value=_nval("jumps", "Distance (m)", 40.0), start=0.0, step=5.0, label="Distance (m)"),
            }),
            "missing": mo.ui.dictionary({
                "Enabled": mo.ui.switch(value=_nval("missing", "Enabled", True), label="Enabled"),
                "Probability": mo.ui.number(value=_nval("missing", "Probability", 0.03), start=0.0, stop=0.95, step=0.01, label="Probability"),
            }),
            "biased_drift": mo.ui.dictionary({
                "Enabled": mo.ui.switch(value=_nval("biased_drift", "Enabled", False), label="Enabled"),
                "Drift (m/pt)": mo.ui.number(value=_nval("biased_drift", "Drift (m/pt)", 0.05), start=0.0, step=0.01, label="Drift (m/pt)"),
                "Bearing (deg)": mo.ui.number(value=_nval("biased_drift", "Bearing (deg)", 70.0), start=0.0, stop=360.0, step=5.0, label="Bearing (deg)"),
            }),
            "lateral_drift": mo.ui.dictionary({
                "Enabled": mo.ui.switch(value=_nval("lateral_drift", "Enabled", False), label="Enabled"),
                "Total (m)": mo.ui.number(value=_nval("lateral_drift", "Total (m)", 3.0), step=0.5, label="Total (m)"),
            }),
            "timestamp_jitter": mo.ui.dictionary({
                "Enabled": mo.ui.switch(value=_nval("timestamp_jitter", "Enabled", True), label="Enabled"),
                "Sigma (s)": mo.ui.number(value=_nval("timestamp_jitter", "Sigma (s)", 0.15), start=0.0, step=0.05, label="Sigma (s)"),
            }),
        }
    )
    mo.vstack([mo.md("### Noise configuration"), noise_config])
    return (noise_config,)


@app.cell
def _(mo):
    generate_button = mo.ui.run_button(label="Generate traces")
    seed_input = mo.ui.number(value=42, start=0, stop=9999, step=1, label="Seed")
    mo.hstack([generate_button, seed_input], gap=2, align="end")
    return generate_button, seed_input


@app.cell
def _(
    db,
    generate_button,
    geojson_upload,
    line_source,
    mo,
    noise_config,
    seed_file_browser,
    seed_input,
    sim_params,
):
    import json
    from geodata.simulate import generate_tracks
    from geodata.geojson import parse_route_from_geojson

    mo.stop(not generate_button.value)

    # Determine route source
    route = None

    # From DB line
    if line_source.value:
        from uuid import UUID as _UUID
        from components.data import load_route_edges
        edges = load_route_edges(db, _UUID(line_source.value))
        if edges:
            route = []
            for edge in edges:
                if edge["path"] and len(edge["path"]) >= 2:
                    route.extend(edge["path"] if not route else edge["path"][1:])

    # From server seed file
    if not route and seed_file_browser.value:
        with open(seed_file_browser.path(0), encoding="utf-8") as _f:
            route = parse_route_from_geojson(_f.read())

    # From uploaded file
    if not route and geojson_upload.value:
        raw = geojson_upload.value[0].contents.decode("utf-8")
        route = parse_route_from_geojson(raw)

    mo.stop(
        not route or len(route) < 2,
        mo.md("**Draw a route on the map, pick a server seed file, upload a GeoJSON, or select a line.**"),
    )

    config = {
        "sim_params": {k: w.value for k, w in sim_params.items()},
        "noise": {
            k: {nk: nw.value for nk, nw in v.items()}
            for k, v in noise_config.items()
        },
    }

    generated_records = generate_tracks(route, config, seed=int(seed_input.value))
    base_route = route
    generated_records, base_route
    return base_route, generated_records


@app.cell
def _(mo):
    fit_view = mo.ui.switch(value=False, label="Fit to route")
    line_width = mo.ui.slider(start=0.25, stop=3.0, step=0.25, value=1.0, label="Line thickness", show_value=True)
    return fit_view, line_width


@app.cell
def _(base_route, fit_view, line_width, generated_records, mo):
    from components.maps import path_layer, deck, default_view_state
    from components.style import cycle_color

    # Group records by track_id
    tracks: dict[int, list[list[float]]] = {}
    for rec in generated_records:
        tid = rec["track_id"]
        tracks.setdefault(tid, []).append([rec["longitude"], rec["latitude"]])

    paths = [
        {"path": base_route, "color": [30, 30, 30, 200], "name": "Base route"},
    ]
    for tid, coords in sorted(tracks.items()):
        if len(coords) >= 2:
            paths.append({"path": coords, "color": cycle_color(tid), "name": f"Track {tid}"})

    mid = len(base_route) // 2
    _view = default_view_state(lat=base_route[mid][1], lon=base_route[mid][0], zoom=14)

    sim_map = deck(
        [path_layer(paths, id="sim-traces", width=1, width_min_pixels=1)],
        view_state=None if fit_view.value else _view,
        fit=fit_view.value,
        line_scale=line_width.value,
        height=500,
        tooltip_html="<b>{name}</b>",
    )

    stats = mo.hstack(
        [
            mo.stat(label="Tracks", value=str(len(tracks))),
            mo.stat(label="Total points", value=str(len(generated_records))),
            mo.stat(label="Base route points", value=str(len(base_route))),
        ],
        gap=1,
        justify="start",
    )

    mo.vstack([mo.md("### Generated traces"), stats, mo.hstack([fit_view, line_width], gap=2, align="center"), sim_map])
    return


@app.cell
def _(db, mo):
    from database.models import Line as _Line
    from database.models import TripSession as _TripSession
    from database.models import TripSessionPoint as _TripSessionPoint
    from sqlalchemy import func as _func
    from sqlalchemy import select as _select

    _counts = dict(
        db.execute(
            _select(_TripSessionPoint.session_id, _func.count(_TripSessionPoint.id))
            .group_by(_TripSessionPoint.session_id)
        ).all()
    )
    _rows = db.execute(
        _select(_TripSession, _Line.name)
        .join(_Line, _Line.id == _TripSession.line_id, isouter=True)
        .order_by(_TripSession.started_at.desc())
    ).all()

    _trace_options = {}
    for _sess, _line_name in _rows:
        _n = _counts.get(_sess.id, 0)
        _trace_options[f"{_line_name or 'no line'} — {str(_sess.id)[:8]} ({_n} pts)"] = _sess.id

    trace_dropdown = mo.ui.dropdown(options=_trace_options, label="Recorded trace")
    estimate_button = mo.ui.run_button(label="Estimate config from trace")
    return estimate_button, trace_dropdown


@app.cell
def _(
    db,
    estimate_button,
    set_estimated_config,
    set_fit_message,
    set_loaded_config,
    trace_dropdown,
):
    from geodata.fit_config import fit_config_from_session

    if estimate_button.value:
        if not trace_dropdown.value:
            set_fit_message("Select a recorded trace first.")
        else:
            try:
                _cfg = fit_config_from_session(db, trace_dropdown.value)
                set_estimated_config(_cfg)
                set_loaded_config(_cfg)
                set_fit_message(
                    "Estimated config from the selected trace and applied it to the "
                    "controls above. Download it below, or tweak the controls and save."
                )
            except Exception as _exc:
                set_estimated_config(None)
                set_fit_message(f"Could not estimate config: {_exc}")
    return


@app.cell
def _(Path, mo):
    _config_dir = Path(__file__).parent / "seed" / "config"
    _config_dir.mkdir(parents=True, exist_ok=True)
    config_filename = mo.ui.text(value="config.json", label="Filename")
    save_config_button = mo.ui.run_button(label="Save config")
    config_load_browser = mo.ui.file_browser(
        initial_path=_config_dir,
        filetypes=[".json"],
        multiple=False,
        label="Select a config file to load",
    )
    return config_filename, config_load_browser, save_config_button


@app.cell
def _(config_load_browser, set_loaded_config):
    import json as _json

    if config_load_browser.value:
        with open(config_load_browser.path(0), encoding="utf-8") as _f:
            set_loaded_config(_json.load(_f))
    return


@app.cell
def _(
    Path,
    config_filename,
    config_load_browser,
    estimate_button,
    get_estimated_config,
    get_fit_message,
    mo,
    noise_config,
    save_config_button,
    sim_params,
    trace_dropdown,
):
    import json as _json

    _save_msg = ""
    if save_config_button.value:
        _cfg = {
            "sim_params": {k: w.value for k, w in sim_params.items()},
            "noise": {
                k: {nk: nw.value for nk, nw in v.items()}
                for k, v in noise_config.items()
            },
        }
        _path = Path(__file__).parent / "seed" / "config" / (config_filename.value or "config.json")
        with open(_path, "w", encoding="utf-8") as _f:
            _json.dump(_cfg, _f, indent=2)
        _save_msg = f"Saved to `{_path}`"

    _estimated = get_estimated_config()
    _download_el = (
        mo.download(
            data=_json.dumps(_estimated, indent=2).encode("utf-8"),
            filename="estimated_config.json",
            mimetype="application/json",
            label="Download estimated config (JSON)",
        )
        if _estimated
        else mo.md("")
    )
    _fit_msg = get_fit_message()

    mo.vstack([
        mo.md("### Configuration"),
        mo.md(
            "**Estimate from a recorded trace** — map-matches the selected real trace "
            "with Valhalla, fits simulator parameters from how it deviates, and applies "
            "them to the controls above so you can review, tweak, and download."
        ),
        mo.hstack([trace_dropdown, estimate_button], align="end", gap=1),
        mo.md(_fit_msg) if _fit_msg else mo.md(""),
        _download_el,
        mo.md("---"),
        mo.md("**Save current config**"),
        mo.hstack([config_filename, save_config_button], align="end", gap=1),
        mo.md(_save_msg) if _save_msg else mo.md(""),
        mo.md("---"),
        mo.md("**Load config from file**"),
        config_load_browser,
    ], gap=0.5)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ### Save to database
    """)
    return


@app.cell
def _(db, mo):
    from components.data import load_lines as _load_lines

    _lines = _load_lines(db)
    _options = {row["name"]: row["id"] for row in _lines}
    save_line = mo.ui.dropdown(options=_options, label="Assign to line")
    device_id_input = mo.ui.text(value="simulator", label="Device ID")
    save_button = mo.ui.run_button(label="Save traces to DB")
    mo.hstack([save_line, device_id_input, save_button], gap=1, align="end")
    return device_id_input, save_button, save_line


@app.cell
def _(db, device_id_input, generated_records, mo, save_button, save_line):
    from uuid import UUID as _UUID
    from geodata.persist import save_tracks_to_db

    mo.stop(not save_button.value)
    mo.stop(not save_line.value, mo.md("**Select a line to save traces to.**"))

    # save_tracks_to_db registers the device row (FK-safe) before inserting.
    _device = device_id_input.value.strip() or "simulator"
    sessions = save_tracks_to_db(
        db,
        generated_records,
        line_id=_UUID(save_line.value),
        device_id=_device,
        notes="simulated",
    )

    mo.md(f"Saved **{len(sessions)}** session(s) to line, assigned to device `{_device}`.")
    return


if __name__ == "__main__":
    app.run()
