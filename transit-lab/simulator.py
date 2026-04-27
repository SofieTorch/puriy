import marimo

__generated_with = "0.23.3"
app = marimo.App(width="full")


@app.cell
def _():
    import marimo as mo
    from components.navbar import navbar

    return mo, navbar


@app.cell
def _(navbar):
    navbar()
    return


@app.cell
def _():
    from database.connection import SessionLocal

    db = SessionLocal()
    return (db,)


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
    _options = {"— Draw or upload —": "", **{row["name"]: row["id"] for row in _lines}}
    line_source = mo.ui.dropdown(options=_options, value="", label="Load route from line")
    line_source
    return (line_source,)


@app.cell
def _(mo):
    import folium
    from folium.plugins import Draw

    m = folium.Map(location=[-17.3935, -66.1570], zoom_start=14, tiles="CartoDB positron")
    Draw(
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

    draw_map = mo.Html(m._repr_html_())
    draw_map
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
def _(mo):
    sim_params = mo.ui.dictionary(
        {
            "Number of tracks": mo.ui.number(value=5, start=1, stop=50, step=1, label="Number of tracks"),
            "Sampling rate (s)": mo.ui.number(value=2.0, start=0.5, stop=10.0, step=0.5, label="Sampling rate (s)"),
            "Base speed (m/s)": mo.ui.number(value=8.0, start=1.0, stop=30.0, step=0.5, label="Base speed (m/s)"),
            "Speed jitter (%)": mo.ui.number(value=12.0, start=0.0, stop=50.0, step=1.0, label="Speed jitter (%)"),
            "Mean trace proportion (0-1)": mo.ui.number(value=1.0, start=0.1, stop=1.0, step=0.05, label="Mean trace proportion"),
            "Stddev trace proportion": mo.ui.number(value=0.0, start=0.0, stop=0.5, step=0.05, label="Stddev trace proportion"),
        }
    )
    sim_params
    return (sim_params,)


@app.cell
def _(mo):
    noise_config = mo.ui.dictionary(
        {
            "gaussian": mo.ui.dictionary({
                "Enabled": mo.ui.switch(value=True, label="Enabled"),
                "Sigma (m)": mo.ui.number(value=4.0, start=0.0, stop=20.0, step=0.5, label="Sigma (m)"),
            }),
            "perpendicular": mo.ui.dictionary({
                "Enabled": mo.ui.switch(value=True, label="Enabled"),
                "Sigma (m)": mo.ui.number(value=3.0, start=0.0, stop=20.0, step=0.5, label="Sigma (m)"),
            }),
            "missing": mo.ui.dictionary({
                "Enabled": mo.ui.switch(value=True, label="Enabled"),
                "Probability": mo.ui.number(value=0.03, start=0.0, stop=0.3, step=0.01, label="Probability"),
            }),
            "jumps": mo.ui.dictionary({
                "Enabled": mo.ui.switch(value=False, label="Enabled"),
                "Probability": mo.ui.number(value=0.02, start=0.0, stop=0.1, step=0.01, label="Probability"),
                "Distance (m)": mo.ui.number(value=40.0, start=5.0, stop=200.0, step=5.0, label="Distance (m)"),
            }),
            "timestamp_jitter": mo.ui.dictionary({
                "Enabled": mo.ui.switch(value=True, label="Enabled"),
                "Sigma (s)": mo.ui.number(value=0.15, start=0.0, stop=2.0, step=0.05, label="Sigma (s)"),
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

    # From uploaded file
    if not route and geojson_upload.value:
        raw = geojson_upload.value[0].contents.decode("utf-8")
        route = parse_route_from_geojson(raw)

    mo.stop(not route or len(route) < 2, mo.md("**Draw a route on the map, upload a GeoJSON, or select a line.**"))

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
def _(base_route, generated_records, mo):
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
        [path_layer(paths, id="sim-traces")],
        view_state=_view,
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

    mo.vstack([mo.md("### Generated traces"), stats, sim_map])
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

    sessions = save_tracks_to_db(
        db,
        generated_records,
        line_id=_UUID(save_line.value),
        notes="simulated",
    )

    # Assign device to all sessions
    _device = device_id_input.value.strip() or "simulator"
    for session in sessions:
        session.device_id = _device
    db.commit()

    mo.md(f"Saved **{len(sessions)}** session(s) to line, assigned to device `{_device}`.")
    return


if __name__ == "__main__":
    app.run()
