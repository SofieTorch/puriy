import marimo

__generated_with = "0.20.4"
app = marimo.App(width="full")


@app.cell
def _():
    from components.navbar import navbar

    return (navbar,)


@app.cell
def _(navbar):
    navbar()
    return


@app.cell
def _():
    import marimo as mo
    import pandas as pd
    import pydeck as pdk
    from pathlib import Path
    from sqlalchemy import select

    from components.tracing import init_tracing
    from database.connection import SessionLocal
    from database.models.line import Line
    from database.models.route import Trip, TripPoint
    from database.models.trip import TripSession
    from geodata.reconstruction import (
        ReconstructionPoint,
        ReconstructionTrace,
        get_reconstruction_strategies,
    )

    return (
        Line,
        Path,
        ReconstructionPoint,
        ReconstructionTrace,
        SessionLocal,
        Trip,
        TripPoint,
        TripSession,
        get_reconstruction_strategies,
        init_tracing,
        mo,
        pd,
        pdk,
        select,
    )


@app.cell
def _(SessionLocal, init_tracing, mo):
    db = SessionLocal()
    init_tracing()
    get_last_run_click, set_last_run_click = mo.state(0)
    get_reconstruction_result, set_reconstruction_result = mo.state(None)
    get_run_message, set_run_message = mo.state(
        "Select a line and run a reconstruction strategy."
    )
    return (
        db,
        get_last_run_click,
        get_reconstruction_result,
        get_run_message,
        set_last_run_click,
        set_reconstruction_result,
        set_run_message,
    )


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    # Route Reconstruction Lab

    Preview reconstruction strategies against cleaned traces for a selected line.
    """)
    return


@app.cell
def _(Line, db, mo, select):
    db.rollback()
    lines = db.execute(select(Line).order_by(Line.name)).scalars().all()
    line_options = {
        f"{line.name} ({line.id})": str(line.id)
        for line in lines
    }
    default_line = next(iter(line_options), None)
    line_dropdown = mo.ui.dropdown(
        options=line_options,
        value=default_line,
        label="Line",
    )
    return (line_dropdown,)


@app.cell
def _(get_reconstruction_strategies, mo):
    strategy_registry = get_reconstruction_strategies()
    strategy_options = {
        strategy.label: key for key, strategy in strategy_registry.items()
    }
    default_strategy = next(iter(strategy_options), None)
    strategy_dropdown = mo.ui.dropdown(
        options=strategy_options,
        value=default_strategy,
        label="Strategy",
    )
    return strategy_dropdown, strategy_registry


@app.cell
def _(Path, mo):
    routes_dir = Path.cwd() / "seed" / "routes"
    route_file_options = {
        route_path.name: str(route_path.resolve())
        for route_path in sorted(routes_dir.glob("*.geojson"))
    }
    route_file_selector = mo.ui.dropdown(
        options=route_file_options,
        value=next(iter(route_file_options), None),
        label="Route file",
    )
    return (route_file_selector,)


@app.cell
def _(mo, route_file_selector, strategy_dropdown, strategy_registry):
    selected_strategy_key = strategy_dropdown.value
    _selected_strategy = strategy_registry.get(selected_strategy_key)
    default_params = (
        _selected_strategy.default_params() if _selected_strategy is not None else {}
    )
    if selected_strategy_key == "route_file_preview":
        strategy_params = mo.ui.dictionary(
            {
                "route_file": route_file_selector,
            },
            label="Strategy parameters",
        )
    elif selected_strategy_key == "dbscan_consensus_preview":
        strategy_params = mo.ui.dictionary(
            {
                "eps_meters": mo.ui.number(
                    value=float(default_params.get("eps_meters", 30.0)),
                    start=1.0,
                    step=1.0,
                    label="DBSCAN radius (m)",
                ),
                "min_samples": mo.ui.number(
                    value=int(default_params.get("min_samples", 0)),
                    start=0,
                    step=1,
                    label="Min samples (0=auto)",
                ),
            },
            label="Strategy parameters",
        )
    elif selected_strategy_key == "dbscan_grid_search_preview":
        strategy_params = mo.ui.dictionary(
            {
                "eps_start_meters": mo.ui.number(
                    value=float(default_params.get("eps_start_meters", 5.0)),
                    start=1.0,
                    step=1.0,
                    label="DBSCAN radius start (m)",
                ),
                "eps_stop_meters": mo.ui.number(
                    value=float(default_params.get("eps_stop_meters", 40.0)),
                    start=1.0,
                    step=1.0,
                    label="DBSCAN radius stop (m)",
                ),
                "eps_step_meters": mo.ui.number(
                    value=float(default_params.get("eps_step_meters", 5.0)),
                    start=1.0,
                    step=1.0,
                    label="DBSCAN radius step (m)",
                ),
                "min_samples_min": mo.ui.number(
                    value=int(default_params.get("min_samples_min", 1)),
                    start=1,
                    step=1,
                    label="Min samples start",
                ),
                "min_samples_max": mo.ui.number(
                    value=int(default_params.get("min_samples_max", 0)),
                    start=0,
                    step=1,
                    label="Min samples stop (0=auto)",
                ),
                "overlap_tolerance_meters": mo.ui.number(
                    value=float(default_params.get("overlap_tolerance_meters", 25.0)),
                    start=1.0,
                    step=1.0,
                    label="Overlap tolerance (m)",
                ),
                "route_support_step_meters": mo.ui.number(
                    value=float(default_params.get("route_support_step_meters", 10.0)),
                    start=1.0,
                    step=1.0,
                    label="Route support step (m)",
                ),
            },
            label="Strategy parameters",
        )
    elif selected_strategy_key == "edge_graph_consensus_preview":
        strategy_params = mo.ui.dictionary(
            {
                "costing": mo.ui.text(
                    value=str(default_params.get("costing", "bus")),
                    label="Valhalla costing",
                ),
                "search_radius": mo.ui.number(
                    value=int(default_params.get("search_radius", 60)),
                    start=1,
                    step=1,
                    label="Search radius (m)",
                ),
                "gps_accuracy": mo.ui.number(
                    value=int(default_params.get("gps_accuracy", 20)),
                    start=1,
                    step=1,
                    label="GPS accuracy (m)",
                ),
                "beam_width": mo.ui.number(
                    value=int(default_params.get("beam_width", 8)),
                    start=1,
                    step=1,
                    label="Beam width",
                ),
                "start_candidates": mo.ui.number(
                    value=int(default_params.get("start_candidates", 5)),
                    start=1,
                    step=1,
                    label="Start candidates",
                ),
                "transition_weight": mo.ui.number(
                    value=float(default_params.get("transition_weight", 2.0)),
                    start=0.0,
                    step=0.25,
                    label="Transition weight",
                ),
            },
            label="Strategy parameters",
        )
    elif selected_strategy_key == "segment_vote_consensus_preview":
        strategy_params = mo.ui.dictionary(
            {
                "costing": mo.ui.text(
                    value=str(default_params.get("costing", "bus")),
                    label="Valhalla costing",
                ),
                "search_radius": mo.ui.number(
                    value=int(default_params.get("search_radius", 60)),
                    start=1,
                    step=1,
                    label="Search radius (m)",
                ),
                "gps_accuracy": mo.ui.number(
                    value=int(default_params.get("gps_accuracy", 20)),
                    start=1,
                    step=1,
                    label="GPS accuracy (m)",
                ),
                "beam_width": mo.ui.number(
                    value=int(default_params.get("beam_width", 8)),
                    start=1,
                    step=1,
                    label="Beam width",
                ),
                "transition_weight": mo.ui.number(
                    value=float(default_params.get("transition_weight", 2.0)),
                    start=0.0,
                    step=0.25,
                    label="Transition weight",
                ),
                "min_edge_support": mo.ui.number(
                    value=int(default_params.get("min_edge_support", 0)),
                    start=0,
                    step=1,
                    label="Min edge support (0=auto)",
                ),
                "min_pair_support": mo.ui.number(
                    value=int(default_params.get("min_pair_support", 0)),
                    start=0,
                    step=1,
                    label="Min pair support (0=auto)",
                ),
                "edge_support_fraction": mo.ui.number(
                    value=float(default_params.get("edge_support_fraction", 0.34)),
                    start=0.0,
                    step=0.05,
                    label="Auto edge support fraction",
                ),
                "pair_support_fraction": mo.ui.number(
                    value=float(default_params.get("pair_support_fraction", 0.34)),
                    start=0.0,
                    step=0.05,
                    label="Auto pair support fraction",
                ),
            },
            label="Strategy parameters",
        )
    else:
        strategy_params = mo.ui.dictionary({}, label="Strategy parameters")

    run_button = mo.ui.button(
        label="Run reconstruction",
        value=0,
        on_click=lambda v: (v or 0) + 1,
        kind="success",
    )
    return run_button, strategy_params


@app.cell
def _(Line, Trip, TripPoint, TripSession, db, line_dropdown, select):
    db.rollback()
    selected_line_id = line_dropdown.value
    selected_line = db.get(Line, selected_line_id) if selected_line_id else None

    session_lookup = {}
    trips = []
    points_by_trip = {}
    all_points = []

    if selected_line is not None:
        trips = (
            db.execute(
                select(Trip)
                .where(Trip.line_id == selected_line.id)
                .order_by(Trip.processed_at)
            )
            .scalars()
            .all()
        )
        session_ids = [trip.session_id for trip in trips]
        if session_ids:
            sessions = (
                db.execute(select(TripSession).where(TripSession.id.in_(session_ids)))
                .scalars()
                .all()
            )
            session_lookup = {session.id: session for session in sessions}
        points_by_trip = {trip.id: [] for trip in trips}
        trip_ids = [trip.id for trip in trips]
        if trip_ids:
            all_points = (
                db.execute(
                    select(TripPoint)
                    .where(TripPoint.trip_id.in_(trip_ids))
                    .order_by(TripPoint.trip_id, TripPoint.point_index)
                )
                .scalars()
                .all()
            )
            for point in all_points:
                points_by_trip.setdefault(point.trip_id, []).append(point)
    return all_points, points_by_trip, selected_line, session_lookup, trips


@app.cell
def _(ReconstructionPoint, ReconstructionTrace, points_by_trip, trips):
    traces = []
    for _trip in trips:
        _trip_points = points_by_trip.get(_trip.id, [])
        if not _trip_points:
            continue
        traces.append(
            ReconstructionTrace(
                trace_id=str(_trip.id),
                points=[
                    ReconstructionPoint(
                        longitude=point.longitude,
                        latitude=point.latitude,
                        point_index=idx,
                        timestamp=point.timestamp,
                    )
                    for idx, point in enumerate(_trip_points)
                ],
            )
        )
    return (traces,)


@app.cell
def _(
    get_last_run_click,
    run_button,
    set_last_run_click,
    set_reconstruction_result,
    set_run_message,
):
    run_click = run_button.value or 0
    should_run = run_click > get_last_run_click()
    if should_run:
        set_last_run_click(run_click)
        set_reconstruction_result(None)
        set_run_message("Running reconstruction...")
    return (should_run,)


@app.cell
def _(
    get_reconstruction_result,
    run_button,
    selected_line,
    set_reconstruction_result,
    set_run_message,
    should_run,
    strategy_dropdown,
    strategy_params,
    strategy_registry,
    traces,
):
    if should_run:
        if selected_line is None:
            set_run_message("Select a line first.")
        elif not traces:
            set_run_message("This line has no cleaned traces to reconstruct.")
        else:
            strategy = strategy_registry.get(strategy_dropdown.value)
            if strategy is None:
                set_run_message("Select a valid reconstruction strategy.")
            else:
                try:
                    result = strategy.reconstruct(
                        selected_line.id,
                        traces,
                        params=strategy_params.value,
                    )
                    set_reconstruction_result(result)
                    route_points = len(
                        result.geojson.get("features", [{}])[0]
                        .get("geometry", {})
                        .get("coordinates", [])
                    )
                    set_run_message(
                        f"Reconstruction complete: {result.strategy_name} "
                        f"produced {route_points} route point(s)."
                    )
                except Exception as exc:
                    set_reconstruction_result(None)
                    set_run_message(f"Reconstruction failed: {exc}")
    reconstruction_result = get_reconstruction_result()
    run_trigger = run_button.value
    return (reconstruction_result,)


@app.cell
def _(
    all_points,
    mo,
    selected_line,
    strategy_dropdown,
    strategy_registry,
    trips,
):
    if selected_line is None:
        line_info = mo.md("No line selected.")
    else:
        _selected_strategy = strategy_registry.get(strategy_dropdown.value)
        line_info = mo.hstack(
            [
                mo.stat(selected_line.name, label="Line", bordered=False),
                mo.stat(len(trips), label="Cleaned traces", bordered=False),
                mo.stat(len(all_points), label="Trace points", bordered=False),
                mo.stat(
                    _selected_strategy.label if _selected_strategy is not None else "None",
                    label="Strategy",
                    bordered=False,
                ),
            ],
            gap=1,
            justify="start",
            align="stretch",
        )
    return (line_info,)


@app.cell
def _(mo, pd, points_by_trip, session_lookup, trips):
    trip_rows = []
    for _trip in trips:
        _trip_points = points_by_trip.get(_trip.id, [])
        _session = session_lookup.get(_trip.session_id)
        trip_rows.append(
            {
                "trip_id": str(_trip.id),
                "session_id": str(_trip.session_id),
                "processed_at": _trip.processed_at,
                "status": _trip.status.value,
                "direction": (_session.direction if _session is not None else "") or "",
                "match_score": _trip.match_score,
                "points": len(_trip_points),
            }
        )
    sessions_table = mo.ui.table(
        data=pd.DataFrame(trip_rows),
        label="Cleaned traces",
        pagination=True,
        selection=None,
    )
    return (sessions_table,)


@app.cell
def _(all_points, pdk, points_by_trip, reconstruction_result):
    path_palette = [
        [59, 130, 246],
        [34, 197, 94],
        [234, 179, 8],
        [168, 85, 247],
        [236, 72, 153],
        [20, 184, 166],
    ]

    session_path_data = []
    for idx, _trip_points in enumerate(points_by_trip.values()):
        if len(_trip_points) < 2:
            continue
        session_path_data.append(
            {
                "path": [
                    [point.longitude, point.latitude, 0]
                    for point in _trip_points
                ],
                "color": path_palette[idx % len(path_palette)],
            }
        )

    scatter_data = [
        {"coordinates": [point.longitude, point.latitude, 0]}
        for point in all_points
    ]

    reconstruction_path_data = []
    if reconstruction_result is not None:
        features = reconstruction_result.geojson.get("features", [])
        if features:
            coords = features[0].get("geometry", {}).get("coordinates", [])
            if len(coords) >= 2:
                reconstruction_path_data.append(
                    {
                        "path": [[coord[0], coord[1], 0] for coord in coords],
                        "color": [239, 68, 68],
                    }
                )

    layers = []
    if session_path_data:
        layers.append(
            pdk.Layer(
                "PathLayer",
                session_path_data,
                get_path="path",
                get_color="color",
                get_width=2,
                width_min_pixels=1,
                opacity=0.35,
            )
        )
    if scatter_data:
        layers.append(
            pdk.Layer(
                "ScatterplotLayer",
                scatter_data,
                get_position="coordinates",
                get_color=[37, 99, 235],
                get_radius=3,
                radius_min_pixels=3,
                pickable=True,
                opacity=0.8,
            )
        )
    if reconstruction_path_data:
        layers.append(
            pdk.Layer(
                "PathLayer",
                reconstruction_path_data,
                get_path="path",
                get_color="color",
                get_width=6,
                width_min_pixels=4,
                opacity=0.95,
            )
        )

    if all_points:
        center_lat = sum(point.latitude for point in all_points) / len(all_points)
        center_lon = sum(point.longitude for point in all_points) / len(all_points)
    else:
        center_lat = -17.3895
        center_lon = -66.1568

    deck = pdk.Deck(
        map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
        initial_view_state=pdk.ViewState(
            latitude=center_lat,
            longitude=center_lon,
            zoom=13,
            pitch=0,
            bearing=0,
        ),
        layers=layers,
        height=520,
    )
    return (deck,)


@app.cell
def _(get_run_message, mo, pd, reconstruction_result):
    run_message = get_run_message()
    if reconstruction_result is None:
        result_panel = mo.callout(mo.md(run_message), kind="info")
    else:
        diagnostics_df = pd.DataFrame(
            [
                {"metric": key, "value": value}
                for key, value in reconstruction_result.diagnostics.items()
            ]
        )
        result_panel = mo.vstack(
            [
                mo.callout(mo.md(run_message), kind="success"),
                mo.ui.table(
                    data=diagnostics_df,
                    label="Diagnostics",
                    pagination=False,
                    selection=None,
                ),
            ],
            gap=0.75,
            align="stretch",
        )
    return (result_panel,)


@app.cell
def _(
    deck,
    line_dropdown,
    line_info,
    mo,
    result_panel,
    run_button,
    sessions_table,
    strategy_dropdown,
    strategy_params,
):
    controls = mo.hstack(
        [line_dropdown, strategy_dropdown, strategy_params, run_button],
        gap=1,
        align="end",
    )

    mo.vstack(
        [
            controls,
            line_info,
            mo.hstack(
                [result_panel, sessions_table],
                widths=[1, 1],
                gap=1,
                align="start",
            ),
            deck,
        ],
        gap=1,
        align="stretch",
    )
    return


if __name__ == "__main__":
    app.run()
