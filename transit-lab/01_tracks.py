import marimo

__generated_with = "0.20.4"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import pandas as pd
    import pydeck as pdk
    from geoalchemy2.shape import to_shape
    from sqlalchemy import select

    from database.connection import SessionLocal
    from database.models.line import Line, LineStatus
    from database.models.recording import LocationPoint, RecordingSession, RecordingStatus
    from geodata.reduce import reduce_linestring_from_recording_session

    return (
        Line,
        LocationPoint,
        RecordingSession,
        SessionLocal,
        mo,
        pd,
        pdk,
        select,
        to_shape,
    )


@app.cell
def _(SessionLocal):
    db = SessionLocal()
    return (db,)


@app.cell
def _(Line, db, mo, pd, select):
    all_lines = db.execute(select(Line).order_by(Line.name)).scalars().all()

    lines_df = pd.DataFrame(
        [
            {
                "id": line.id,
                "name": line.name,
                "status": line.status.value,
                "description": line.description or "",
                "created_at": line.created_at,
            }
            for line in all_lines
        ]
    )
    lines_table = mo.ui.table(data=lines_df, label="Lines", pagination=True)
    lines_table
    return (lines_table,)


@app.cell
def _(RecordingSession, db, lines_table, mo, pd, select):
    # Get selected lines from the table (value is selected rows, or None)
    selected = lines_table.value
    selected_line_ids = (
        selected["id"].tolist()
        if selected is not None and not selected.empty and "id" in selected.columns
        else []
    )

    if not selected_line_ids:
        detail_output = mo.md(
            "**Selecciona una o más líneas** en la tabla de arriba para ver sesiones y mapa."
        )
        sessions_table = None
        sessions = []
    else:
        sessions = list(
            db.execute(
                select(RecordingSession)
                .where(RecordingSession.line_id.in_(selected_line_ids))
                .order_by(RecordingSession.started_at.desc())
            ).scalars().all()
        )

        if not sessions:
            detail_output = mo.md(
                "No hay sesiones de grabación para las líneas seleccionadas."
            )
            sessions_table = None
        else:
            sessions_df = pd.DataFrame(
                [
                    {
                        "id": s.id,
                        "line_id": s.line_id,
                        "status": s.status.value,
                        "started_at": s.started_at,
                        "ended_at": s.ended_at,
                        "direction": s.direction or "—",
                        "device_model": s.device_model or "—",
                    }
                    for s in sessions
                ]
            )
            sessions_table = mo.ui.table(
                data=sessions_df,
                label="Recording sessions",
                pagination=True,
                selection="single",
            )
            detail_output = None  # Map + table rendered in next cell

    detail_output
    return sessions, sessions_table


@app.cell
def _(LocationPoint, db, mo, pdk, select, sessions, sessions_table, to_shape):
    # This cell builds map data and zoom buttons (does not access button .value)
    if sessions_table is None or not sessions:
        zoom_in_btn = zoom_out_btn = None
        view_3d_switch = None
        center_lat = center_lon = None
        layers = []
    else:
        selected_sessions = sessions_table.value
        selected_session = None
        if (
            selected_sessions is not None
            and not selected_sessions.empty
            and "id" in selected_sessions.columns
        ):
            sid = selected_sessions["id"].iloc[0]
            selected_session = next((s for s in sessions if s.id == sid), None)

        def _path_coords(session):
            if session.computed_path is not None:
                try:
                    geom = to_shape(session.computed_path)
                    return [[c[0], c[1], 0] for c in geom.coords]
                except Exception:
                    pass
            return None

        def _trip_data(path_coords, location_points=None):
            if location_points and len(location_points) >= 2:
                t0 = location_points[0].timestamp
                timestamps = [(p.timestamp - t0).total_seconds() for p in location_points]
                path = [
                    [p.longitude, p.latitude, p.altitude if p.altitude else 0]
                    for p in location_points
                ]
            else:
                timestamps = list(range(len(path_coords)))
                path = [[c[0], c[1], 0] for c in path_coords]
            return {"path": path, "timestamps": timestamps}

        PATH_COLORS = [
            [59, 130, 246],   # blue
            [34, 197, 94],    # green
            [234, 179, 8],    # amber
            [168, 85, 247],   # violet
            [236, 72, 153],   # pink
            [20, 184, 166],   # teal
        ]
        path_layer_data = []
        all_coords = []
        selected_trip_data = None
        scatter_data = []

        for i, s in enumerate(sessions):
            path_coords = _path_coords(s)
            if path_coords:
                is_selected = selected_session and s.id == selected_session.id
                if not is_selected:
                    path_layer_data.append({
                        "path": path_coords,
                        "color": PATH_COLORS[i % len(PATH_COLORS)],
                    })
                all_coords.extend(path_coords)

                if is_selected:
                    loc_pts = list(
                        db.execute(
                            select(LocationPoint)
                            .where(LocationPoint.session_id == s.id)
                            .order_by(LocationPoint.timestamp)
                        ).scalars().all()
                    )
                    selected_trip_data = _trip_data(path_coords, loc_pts if loc_pts else None)
                    scatter_data = [
                        {"coordinates": [p.longitude, p.latitude, p.altitude or 0]}
                        for p in (loc_pts or [])
                    ]

        layers = []
        if path_layer_data:
            layers.append(
                pdk.Layer(
                    "PathLayer",
                    path_layer_data,
                    get_path="path",
                    get_color="color",
                    get_width=5,
                    width_min_pixels=3,
                ),
            )
        if selected_trip_data:
            max_time = max(selected_trip_data["timestamps"]) if selected_trip_data["timestamps"] else 0
            layers.append(
                pdk.Layer(
                    "TripsLayer",
                    [selected_trip_data],
                    get_path="path",
                    get_timestamps="timestamps",
                    get_color=[239, 68, 68],
                    opacity=0.9,
                    width_min_pixels=10,
                    rounded=True,
                    trail_length=max_time + 1,
                    current_time=max_time,
                ),
            )
        if scatter_data:
            layers.append(
                pdk.Layer(
                    "ScatterplotLayer",
                    data=scatter_data,
                    get_position="coordinates",
                    get_color=[239, 68, 68],
                    get_radius=4,
                    radius_min_pixels=4,
                    stroked=True,
                    get_line_color=[255, 255, 255],
                    line_width_min_pixels=1,
                ),
            )

        if scatter_data:
            lons = [c["coordinates"][0] for c in scatter_data]
            lats = [c["coordinates"][1] for c in scatter_data]
        elif all_coords:
            lons = [c[0] for c in all_coords]
            lats = [c[1] for c in all_coords]
        else:
            lons, lats = [], []
        center_lat = sum(lats) / len(lats) if lats else 40.4
        center_lon = sum(lons) / len(lons) if lons else -3.7

        zoom_in_btn = mo.ui.button(
            label="+",
            value=0,
            on_click=lambda v: (v or 0) + 1,
            kind="neutral",
        )
        zoom_out_btn = mo.ui.button(
            label="−",
            value=0,
            on_click=lambda v: (v or 0) + 1,
            kind="neutral",
        )
        view_3d_switch = mo.ui.switch(value=True, label="3D view")
    return (
        center_lat,
        center_lon,
        layers,
        view_3d_switch,
        zoom_in_btn,
        zoom_out_btn,
    )


@app.cell
def _(
    center_lat,
    center_lon,
    layers,
    mo,
    pdk,
    sessions_table,
    view_3d_switch,
    zoom_in_btn,
    zoom_out_btn,
):
    # This cell reads zoom button and switch values (created in previous cell) to build the deck
    if (
        sessions_table is None
        or zoom_in_btn is None
        or zoom_out_btn is None
        or view_3d_switch is None
        or center_lat is None
        or center_lon is None
        or not layers
    ):
        map_display = None
    else:
        zoom_level = 14 + (zoom_in_btn.value or 0) - (zoom_out_btn.value or 0)
        zoom_level = min(20, max(8, zoom_level))
        pitch = 60 if view_3d_switch.value else 0

        deck = pdk.Deck(
            map_style="light",
            map_provider="carto",
            initial_view_state=pdk.ViewState(
                latitude=center_lat,
                longitude=center_lon,
                zoom=zoom_level,
                pitch=pitch,
                bearing=0,
            ),
            layers=layers,
            height=500,
        )
        zoom_controls = mo.hstack(
            [zoom_out_btn, zoom_in_btn, view_3d_switch],
            gap=0.5,
            justify="start",
        )
        map_section = mo.vstack(
            [
                mo.hstack(
                    [
                        zoom_controls,
                        mo.md("_Scroll to zoom · Drag to pan_"),
                    ],
                    justify="start",
                    gap=1,
                ),
                deck,
            ],
            align="stretch",
        )
        table_section = mo.vstack([sessions_table]).style(
            style={"max-width": "540px"},
            overflow_x="auto",
        )
        map_display = mo.hstack(
            [map_section, table_section],
            widths=[1, 1],
            gap=1,
            justify="start",
        )


    map_display
    return


if __name__ == "__main__":
    app.run()
