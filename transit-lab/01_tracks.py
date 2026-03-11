import marimo

__generated_with = "0.20.4"
app = marimo.App(width="medium")


@app.cell
def _():
    import math

    import marimo as mo
    import pandas as pd
    import pydeck as pdk
    from geoalchemy2.shape import to_shape
    from sqlalchemy import func, select

    from database.connection import SessionLocal
    from database.models.line import Line, LineStatus
    from database.models.recording import LocationPoint, RecordingSession, RecordingStatus
    from geodata.reduce import reduce_linestring_from_recording_session

    return (
        Line,
        LocationPoint,
        RecordingSession,
        SessionLocal,
        func,
        math,
        mo,
        pd,
        pdk,
        reduce_linestring_from_recording_session,
        select,
        to_shape,
    )


@app.cell
def _(mo, SessionLocal):
    db = SessionLocal()
    get_refresh, set_refresh = mo.state(0)
    return (db, get_refresh, set_refresh)


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
                        "reduced_points": s.reduced_points if s.reduced_points is not None else "—",
                    }
                    for s in sessions
                ]
            )
            sessions_table = mo.ui.table(
                data=sessions_df,
                label="",
                pagination=True,
                selection="single",
            )
            detail_output = None  # Map + table rendered in next cell

    detail_output
    return sessions, sessions_table


@app.cell
def _(LocationPoint, db, func, get_refresh, math, mo, pdk, select, sessions, sessions_table, to_shape):
    # This cell builds map data and zoom buttons (does not access button .value)
    if sessions_table is None or not sessions:
        zoom_in_btn = zoom_out_btn = None
        view_3d_switch = None
        reduce_btn = None
        center_lat = center_lon = None
        layers = []
        geo_points_count = None
        selected_session = None
        duration_seconds = None
        distance_m = None
        agg_geo_points = None
        agg_reduced = None
        agg_duration_seconds = None
        agg_distance_m = None
    else:
        _ = get_refresh()  # Re-run when refresh is triggered (e.g. after reduce)
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
        def _haversine_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
            R = 6_371_000  # Earth radius in meters
            phi1, phi2 = math.radians(lat1), math.radians(lat2)
            dphi = math.radians(lat2 - lat1)
            dlambda = math.radians(lon2 - lon1)
            a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
            return R * c

        path_layer_data = []
        all_coords = []
        selected_trip_data = None
        scatter_data = []
        geo_points_count = None
        duration_seconds = None
        distance_m = None

        # Aggregated stats across all sessions
        session_ids = [s.id for s in sessions]
        geo_counts = dict(
            db.execute(
                select(LocationPoint.session_id, func.count(LocationPoint.id))
                .where(LocationPoint.session_id.in_(session_ids))
                .group_by(LocationPoint.session_id)
            ).all()
        )
        agg_geo_points = sum(geo_counts.get(sid, 0) for sid in session_ids)
        agg_reduced = sum((s.reduced_points or 0) for s in sessions)
        agg_duration_seconds = 0
        agg_distance_m = 0.0

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

                # Per-session distance and duration for aggregates
                session_distance = 0.0
                for j in range(len(path_coords) - 1):
                    lon1, lat1 = path_coords[j][0], path_coords[j][1]
                    lon2, lat2 = path_coords[j + 1][0], path_coords[j + 1][1]
                    session_distance += _haversine_m(lon1, lat1, lon2, lat2)
                agg_distance_m += session_distance
                end_time = s.ended_at or s.last_activity_at
                if end_time:
                    agg_duration_seconds += int((end_time - s.started_at).total_seconds())

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
                    geo_points_count = len(loc_pts) if loc_pts else 0
                    duration_seconds = (
                        int((end_time - s.started_at).total_seconds())
                        if end_time else None
                    )
                    distance_m = session_distance

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
        reduce_btn = mo.ui.button(
            label="Simplify path",
            value=0,
            on_click=lambda v: (v or 0) + 1,
            kind="neutral",
            disabled=selected_session is None,
        )
    return (
        agg_distance_m,
        agg_duration_seconds,
        agg_geo_points,
        agg_reduced,
        center_lat,
        center_lon,
        distance_m,
        duration_seconds,
        geo_points_count,
        layers,
        reduce_btn,
        selected_session,
        view_3d_switch,
        zoom_in_btn,
        zoom_out_btn,
    )



@app.cell
def _(
    agg_distance_m,
    agg_duration_seconds,
    agg_geo_points,
    agg_reduced,
    center_lat,
    center_lon,
    db,
    distance_m,
    duration_seconds,
    geo_points_count,
    layers,
    mo,
    pdk,
    reduce_btn,
    reduce_linestring_from_recording_session,
    selected_session,
    sessions_table,
    set_refresh,
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
        def _format_duration(seconds: int | None) -> str:
            if seconds is None:
                return "—"
            h, r = divmod(seconds, 3600)
            m, s = divmod(r, 60)
            if h:
                return f"{h}h {m}m"
            if m:
                return f"{m}m {s}s"
            return f"{s}s"


        def _format_distance(m: float | None) -> str:
            if m is None:
                return "—"
            if m >= 1000:
                return f"{m / 1000:.1f} km"
            return f"{int(m)} m"

        if reduce_btn and (reduce_btn.value or 0) > 0:
            session_selection = sessions_table.value
            if (
                session_selection is not None
                and not session_selection.empty
                and "id" in session_selection.columns
            ):
                session_id = int(session_selection["id"].iloc[0])
                try:
                    reduce_linestring_from_recording_session(db, session_id)
                    db.commit()
                    if selected_session and selected_session.id == session_id:
                        db.refresh(selected_session)
                    set_refresh(lambda v: v + 1)  # Trigger re-fetch so map/stats update
                except Exception:
                    db.rollback()
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
        table_header = (
            mo.hstack(
                [mo.md("**Recording sessions**"), reduce_btn],
                justify="space-between",
                align="center",
            )
            if reduce_btn
            else mo.md("**Recording sessions**")
        )
        stats_display = None
        if selected_session and geo_points_count is not None:
            reduced = selected_session.reduced_points or 0
            stats_display = mo.hstack(
                [
                    mo.stat(geo_points_count, label="Geopoints", bordered=False),
                    mo.stat(reduced, label="Reduced", bordered=False),
                    mo.stat(_format_duration(duration_seconds), label="Time", bordered=False),
                    mo.stat(_format_distance(distance_m), label="Distance", bordered=False),
                ],
                gap=1,
                align="stretch",
                justify="start",
            )
        elif selected_session is None and agg_geo_points is not None:
            stats_display = mo.hstack(
                [
                    mo.stat(agg_geo_points, label="Geopoints", bordered=False),
                    mo.stat(agg_reduced or 0, label="Reduced", bordered=False),
                    mo.stat(_format_duration(agg_duration_seconds or 0), label="Time", bordered=False),
                    mo.stat(
                        f"{agg_distance_m / 1000:.1f} km" if agg_distance_m else "—",
                        label="Distance",
                        bordered=False,
                    ),
                ],
                gap=1,
                align="stretch",
                justify="start",
            )
        table_content = []
        if stats_display is not None:
            table_content.append(stats_display)
        table_content.extend([table_header, sessions_table])
        table_section = mo.vstack(table_content).style(
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
