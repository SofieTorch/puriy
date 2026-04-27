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
def _(mo, seed_file_browser):
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

    # Overlay the selected seed-file route as a dashed reference line.
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
    mo.hstack([draw_map, seed_file_browser], gap=1, align="start", widths=[3, 1])
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


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ---
    ### Simulate votes

    Closes the loop: existing simulator-tagged trips → reconstructed route → synthetic votes.
    For each voter (a round-robin bucket of TripSessions whose `device_id` starts with
    `simulator`), we compute the segment of edges they'd be asked to vote on (same logic
    as the live API), then vote **approve** if most of those edges fit the voter's actual
    path, **reject** otherwise.
    """)
    return


@app.cell
def _(db, mo):
    from components.data import load_lines as _load_lines

    _lines = _load_lines(db)
    _options = {row["name"]: row["id"] for row in _lines}
    vote_sim_line = mo.ui.dropdown(options=_options, label="Line")
    n_voters = mo.ui.number(value=10, start=1, stop=200, step=1, label="Number of voters")
    fit_threshold = mo.ui.number(
        value=0.7, start=0.0, stop=1.0, step=0.05,
        label="Approve if fit ratio ≥",
    )
    tight_tolerance = mo.ui.number(
        value=15.0, start=1.0, stop=100.0, step=1.0,
        label="Tight overlap tolerance (m)",
    )
    reset_synthetic = mo.ui.switch(
        value=False,
        label="Reset synthetic votes (wipe & regenerate; real-user votes untouched)",
    )
    sim_votes_button = mo.ui.run_button(label="Simulate votes", kind="success")
    mo.vstack(
        [
            mo.hstack([vote_sim_line, n_voters, fit_threshold, tight_tolerance], gap=1, align="end"),
            mo.hstack([reset_synthetic, sim_votes_button], gap=2, align="end"),
        ],
        gap=0.5,
    )
    return (
        fit_threshold,
        n_voters,
        reset_synthetic,
        sim_votes_button,
        tight_tolerance,
        vote_sim_line,
    )


@app.cell
def _(
    db,
    fit_threshold,
    mo,
    n_voters,
    reset_synthetic,
    sim_votes_button,
    tight_tolerance,
    vote_sim_line,
):
    from uuid import UUID as _UUID
    from components.vote_simulator import simulate_votes_for_line

    mo.stop(not sim_votes_button.value)
    mo.stop(not vote_sim_line.value, mo.md("**Pick a line first.**"))

    vote_sim_result = simulate_votes_for_line(
        db,
        _UUID(vote_sim_line.value),
        n_voters=int(n_voters.value),
        fit_threshold=float(fit_threshold.value),
        tight_tolerance_m=float(tight_tolerance.value),
        reset_synthetic=bool(reset_synthetic.value),
    )
    return (vote_sim_result,)


@app.cell
def _(mo, vote_sim_result):
    if vote_sim_result.error:
        _view = mo.md(f"**{vote_sim_result.error}**")
    else:
        _stats = mo.hstack(
            [
                mo.stat(label="Sessions considered", value=str(vote_sim_result.sessions_considered)),
                mo.stat(label="Voters (total)", value=str(vote_sim_result.voters_total)),
                mo.stat(label="Voters (eligible)", value=str(vote_sim_result.voters_eligible)),
                mo.stat(label="Vote events", value=str(vote_sim_result.events_created)),
                mo.stat(label="Approve", value=str(vote_sim_result.approve)),
                mo.stat(label="Reject", value=str(vote_sim_result.reject)),
                mo.stat(label="Edges affected", value=str(vote_sim_result.edges_affected)),
                mo.stat(label="Synthetic wiped", value=str(vote_sim_result.synthetic_votes_wiped)),
            ],
            gap=1,
            justify="start",
        )
        _table = mo.ui.table(
            vote_sim_result.voter_breakdown or [],
            selection=None,
            label="Per-voter breakdown",
        )
        _view = mo.vstack([_stats, _table], gap=1, align="stretch")
    _view
    return


if __name__ == "__main__":
    app.run()
