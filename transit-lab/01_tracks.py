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
    import math

    import marimo as mo
    import pandas as pd
    import pydeck as pdk
    from geoalchemy2.shape import to_shape
    from sqlalchemy import func, select

    from components.tracing import init_tracing
    from database.connection import SessionLocal
    from database.models.line import Line, LineStatus
    from database.models.trip import TripSessionPoint, TripSession, SessionStatus
    from database.models.route import Trip, TripPoint

    return (
        Line,
        SessionLocal,
        Trip,
        TripPoint,
        TripSession,
        TripSessionPoint,
        func,
        init_tracing,
        math,
        mo,
        pd,
        pdk,
        select,
        to_shape,
    )


@app.cell
def _(SessionLocal, init_tracing):
    db = SessionLocal()
    init_tracing()
    return (db,)


@app.cell
def _(Line, db, mo, pd, select):
    db.rollback()
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
def _(TripSession, db, lines_table, mo, pd, select):
    db.rollback()
    selected = lines_table.value
    selected_line_ids = (
        selected["id"].tolist()
        if selected is not None and not selected.empty and "id" in selected.columns
        else []
    )

    if not selected_line_ids:
        detail_output = mo.md(
            "**Selecciona una o m\u00e1s l\u00edneas** en la tabla de arriba para ver sesiones y mapa."
        )
        sessions_table = None
        sessions = []
    else:
        sessions = list(
            db.execute(
                select(TripSession)
                .where(TripSession.line_id.in_(selected_line_ids))
                .order_by(TripSession.started_at.desc())
            ).scalars().all()
        )

        if not sessions:
            detail_output = mo.md(
                "No hay sesiones de grabaci\u00f3n para las l\u00edneas seleccionadas."
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
                        "direction": s.direction or "\u2014",
                        "device_model": s.device_model or "\u2014",
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
            detail_output = None

    detail_output
    return sessions, sessions_table


@app.cell
def _(
    TripSessionPoint,
    db,
    func,
    math,
    mo,
    pdk,
    select,
    sessions,
    sessions_table,
    to_shape,
):
    db.rollback()
    if sessions_table is None or not sessions:
        zoom_in_btn = zoom_out_btn = None
        view_3d_switch = None
        center_lat = center_lon = None
        layers = []
        agg_geo_points = None
        agg_duration_seconds = None
        agg_distance_m = None
    else:
        def _path_coords_fn(session):
            if session.computed_path is not None:
                try:
                    geom = to_shape(session.computed_path)
                    return [[c[0], c[1], 0] for c in geom.coords]
                except Exception:
                    pass
            return None

        _PATH_COLORS = [
            [59, 130, 246],   # blue
            [34, 197, 94],    # green
            [234, 179, 8],    # amber
            [168, 85, 247],   # violet
            [236, 72, 153],   # pink
            [20, 184, 166],   # teal
        ]

        def _haversine_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
            R = 6_371_000
            phi1, phi2 = math.radians(lat1), math.radians(lat2)
            dphi = math.radians(lat2 - lat1)
            dlambda = math.radians(lon2 - lon1)
            a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
            return R * c

        _path_layer_data = []
        _all_coords = []

        _session_ids = [s.id for s in sessions]
        _geo_counts = dict(
            db.execute(
                select(TripSessionPoint.session_id, func.count(TripSessionPoint.id))
                .where(TripSessionPoint.session_id.in_(_session_ids))
                .group_by(TripSessionPoint.session_id)
            ).all()
        )
        agg_geo_points = sum(_geo_counts.get(_sid, 0) for _sid in _session_ids)
        agg_duration_seconds = 0
        agg_distance_m = 0.0

        for _i, _s in enumerate(sessions):
            _path_coords = _path_coords_fn(_s)
            if _path_coords:
                _path_layer_data.append({
                    "path": _path_coords,
                    "color": _PATH_COLORS[_i % len(_PATH_COLORS)],
                })
                _all_coords.extend(_path_coords)
                _session_distance = 0.0
                for _j in range(len(_path_coords) - 1):
                    _lon1, _lat1 = _path_coords[_j][0], _path_coords[_j][1]
                    _lon2, _lat2 = _path_coords[_j + 1][0], _path_coords[_j + 1][1]
                    _session_distance += _haversine_m(_lon1, _lat1, _lon2, _lat2)
                agg_distance_m += _session_distance
                _end_time = _s.ended_at or _s.last_activity_at
                if _end_time:
                    agg_duration_seconds += int((_end_time - _s.started_at).total_seconds())

        layers = []
        if _path_layer_data:
            layers.append(
                pdk.Layer(
                    "PathLayer",
                    _path_layer_data,
                    get_path="path",
                    get_color="color",
                    get_width=5,
                    width_min_pixels=3,
                ),
            )

        if _all_coords:
            _lons = [c[0] for c in _all_coords]
            _lats = [c[1] for c in _all_coords]
        else:
            _lons, _lats = [], []
        center_lat = sum(_lats) / len(_lats) if _lats else 40.4
        center_lon = sum(_lons) / len(_lons) if _lons else -3.7

        zoom_in_btn = mo.ui.button(
            label="+",
            value=0,
            on_click=lambda v: (v or 0) + 1,
            kind="neutral",
        )
        zoom_out_btn = mo.ui.button(
            label="\u2212",
            value=0,
            on_click=lambda v: (v or 0) + 1,
            kind="neutral",
        )
        view_3d_switch = mo.ui.switch(value=False, label="3D view")
    return (
        agg_distance_m,
        agg_duration_seconds,
        agg_geo_points,
        center_lat,
        center_lon,
        layers,
        view_3d_switch,
        zoom_in_btn,
        zoom_out_btn,
    )


@app.cell
def _(
    agg_distance_m,
    agg_duration_seconds,
    agg_geo_points,
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
    if (
        sessions_table is None
        or zoom_in_btn is None
        or zoom_out_btn is None
        or view_3d_switch is None
        or center_lat is None
        or center_lon is None
        or not layers
    ):
        overview_display = None
    else:
        def _format_duration(seconds: int | None) -> str:
            if seconds is None:
                return "\u2014"
            h, r = divmod(seconds, 3600)
            m, s = divmod(r, 60)
            if h:
                return f"{h}h {m}m"
            if m:
                return f"{m}m {s}s"
            return f"{s}s"

        def _format_distance(m: float | None) -> str:
            if m is None:
                return "\u2014"
            if m >= 1000:
                return f"{m / 1000:.1f} km"
            return f"{int(m)} m"

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
                    [zoom_controls, mo.md("_Scroll to zoom \u00b7 Drag to pan_")],
                    justify="start",
                    gap=1,
                ),
                deck,
            ],
            align="stretch",
        )

        stats_display = None
        if agg_geo_points is not None:
            stats_display = mo.hstack(
                [
                    mo.stat(agg_geo_points, label="Geopoints", bordered=False),
                    mo.stat(_format_duration(agg_duration_seconds or 0), label="Time", bordered=False),
                    mo.stat(
                        _format_distance(agg_distance_m) if agg_distance_m else "\u2014",
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
        table_content.extend([mo.md("**Trip sessions**"), sessions_table])
        table_section = mo.vstack(table_content).style(
            style={"max-width": "45vw"},
            overflow_x="auto",
        )

        overview_display = mo.hstack(
            [map_section, table_section],
            widths=[1, 1],
            gap=1,
            justify="center",
            align="stretch"
        )

    overview_display
    return


@app.cell
def _(sessions, sessions_table):
    _sel = sessions_table.value if sessions_table is not None else None
    selected_session = None
    if _sel is not None and not _sel.empty and "id" in _sel.columns:
        _sid = _sel["id"].iloc[0]
        selected_session = next((s for s in sessions if s.id == _sid), None)
    return (selected_session,)


@app.cell
def _(Trip, db, mo, select, selected_session):
    db.rollback()
    existing_trip = None
    clean_btn = None
    if selected_session is not None:
        existing_trip = db.execute(
            select(Trip).where(Trip.session_id == selected_session.id)
        ).scalars().first()
        if existing_trip is None:
            clean_btn = mo.ui.button(
                label="Clean / Map-match",
                value=0,
                on_click=lambda v: (v or 0) + 1,
            )
    return clean_btn, existing_trip


@app.cell
def _(clean_btn, mo, selected_session):
    cleaned_trip = None
    clean_result_output = None
    if clean_btn is not None and (clean_btn.value or 0) > 0 and selected_session is not None:
        from database.connection import SessionLocal as _SessionLocal
        from geodata.match import match_session

        _db = _SessionLocal(expire_on_commit=False)
        try:
            _result = match_session(_db, selected_session.id)
            cleaned_trip = _result.trip
            clean_result_output = mo.callout(
                mo.md(
                    f"Matched **{_result.points_before}** \u2192 **{_result.points_after}** points "
                    f"(confidence: **{_result.confidence:.1%}**)"
                ),
                kind="success",
            )
        except Exception as _e:
            _db.rollback()
            clean_result_output = mo.callout(mo.md(f"Error: {_e}"), kind="danger")
        finally:
            _db.close()

    clean_result_output
    return (cleaned_trip,)


@app.cell
def _(
    TripPoint,
    TripSessionPoint,
    clean_btn,
    cleaned_trip,
    db,
    existing_trip,
    math,
    mo,
    pd,
    pdk,
    select,
    selected_session,
    to_shape,
):
    db.rollback()
    if selected_session is None:
        detail_section = None
    else:
        _trip_to_show = cleaned_trip or existing_trip

        def _haversine_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
            R = 6_371_000
            phi1, phi2 = math.radians(lat1), math.radians(lat2)
            dphi = math.radians(lat2 - lat1)
            dlambda = math.radians(lon2 - lon1)
            a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
            return R * c

        def _format_duration(seconds: int | None) -> str:
            if seconds is None:
                return "\u2014"
            h, r = divmod(seconds, 3600)
            m, s = divmod(r, 60)
            if h:
                return f"{h}h {m}m"
            if m:
                return f"{m}m {s}s"
            return f"{s}s"

        def _format_distance(m: float | None) -> str:
            if m is None:
                return "\u2014"
            if m >= 1000:
                return f"{m / 1000:.1f} km"
            return f"{int(m)} m"

        # -- Load raw session path + points --
        _detail_layers = []
        _all_coords = []

        _raw_path_coords = None
        if selected_session.computed_path is not None:
            try:
                _geom = to_shape(selected_session.computed_path)
                _raw_path_coords = [[c[0], c[1], 0] for c in _geom.coords]
            except Exception:
                pass

        _loc_pts = list(
            db.execute(
                select(TripSessionPoint)
                .where(TripSessionPoint.session_id == selected_session.id)
                .order_by(TripSessionPoint.timestamp)
            ).scalars().all()
        )

        if _raw_path_coords:
            _all_coords.extend(_raw_path_coords)
            # Raw path as TripsLayer
            if _loc_pts and len(_loc_pts) >= 2:
                _t0 = _loc_pts[0].timestamp
                _timestamps = [(p.timestamp - _t0).total_seconds() for p in _loc_pts]
                _path = [
                    [p.longitude, p.latitude, p.altitude if p.altitude else 0]
                    for p in _loc_pts
                ]
            else:
                _timestamps = list(range(len(_raw_path_coords)))
                _path = [[c[0], c[1], 0] for c in _raw_path_coords]
            _max_time = max(_timestamps) if _timestamps else 0
            _detail_layers.append(
                pdk.Layer(
                    "TripsLayer",
                    [{"path": _path, "timestamps": _timestamps}],
                    get_path="path",
                    get_timestamps="timestamps",
                    get_color=[239, 68, 68],  # red
                    opacity=0.9,
                    width_min_pixels=10 if not _trip_to_show else 6,
                    rounded=True,
                    trail_length=_max_time + 1,
                    current_time=_max_time,
                ),
            )
            # Raw scatter
            if _loc_pts:
                _detail_layers.append(
                    pdk.Layer(
                        "ScatterplotLayer",
                        data=[
                            {"coordinates": [p.longitude, p.latitude, p.altitude or 0]}
                            for p in _loc_pts
                        ],
                        get_position="coordinates",
                        get_color=[239, 68, 68],
                        get_radius=4,
                        radius_min_pixels=4,
                        stroked=True,
                        get_line_color=[255, 255, 255],
                        line_width_min_pixels=1,
                    ),
                )

        # -- Load clean trip path + points --
        _clean_pts = []
        if _trip_to_show and _trip_to_show.computed_path is not None:
            try:
                _trip_geom = to_shape(_trip_to_show.computed_path)
                _trip_coords = [[c[0], c[1], 0] for c in _trip_geom.coords]
                _detail_layers.append(
                    pdk.Layer(
                        "PathLayer",
                        [{"path": _trip_coords, "color": [34, 197, 94]}],
                        get_path="path",
                        get_color="color",
                        get_width=5,
                        width_min_pixels=3,
                    ),
                )
                _all_coords.extend(_trip_coords)
            except Exception:
                pass
            _clean_pts = list(
                db.execute(
                    select(TripPoint)
                    .where(TripPoint.trip_id == _trip_to_show.id)
                    .order_by(TripPoint.point_index)
                ).scalars().all()
            )
            if _clean_pts:
                _detail_layers.append(
                    pdk.Layer(
                        "ScatterplotLayer",
                        data=[
                            {"coordinates": [p.longitude, p.latitude, 0]}
                            for p in _clean_pts
                        ],
                        get_position="coordinates",
                        get_color=[34, 197, 94],
                        get_radius=4,
                        radius_min_pixels=4,
                        stroked=True,
                        get_line_color=[255, 255, 255],
                        line_width_min_pixels=1,
                    ),
                )

        # -- Stats --
        _geo_points_count = len(_loc_pts)
        _end_time = selected_session.ended_at or selected_session.last_activity_at
        _duration_seconds = (
            int((_end_time - selected_session.started_at).total_seconds())
            if _end_time else None
        )
        _distance_m = 0.0
        if _raw_path_coords:
            for _j in range(len(_raw_path_coords) - 1):
                _lon1, _lat1 = _raw_path_coords[_j][0], _raw_path_coords[_j][1]
                _lon2, _lat2 = _raw_path_coords[_j + 1][0], _raw_path_coords[_j + 1][1]
                _distance_m += _haversine_m(_lon1, _lat1, _lon2, _lat2)

        # -- Build detail map --
        if _all_coords:
            _lons = [c[0] for c in _all_coords]
            _lats = [c[1] for c in _all_coords]
            _center_lat = sum(_lats) / len(_lats)
            _center_lon = sum(_lons) / len(_lons)
        else:
            _center_lat, _center_lon = 40.4, -3.7

        _legend_parts = ['<span style="color:#ef4444">\u25cf</span> Raw']
        if _trip_to_show:
            _legend_parts.append('<span style="color:#22c55e">\u25cf</span> Clean')

        _detail_deck = pdk.Deck(
            map_style="light",
            map_provider="carto",
            initial_view_state=pdk.ViewState(
                latitude=_center_lat,
                longitude=_center_lon,
                zoom=14,
                pitch=0,
                bearing=0,
            ),
            layers=_detail_layers,
        )

        _stat_items = [
            mo.stat(_geo_points_count, label="Geopoints", bordered=False),
            mo.stat(_format_duration(_duration_seconds), label="Time", bordered=False),
            mo.stat(_format_distance(_distance_m), label="Distance", bordered=False),
        ]
        if _trip_to_show is not None:
            if _trip_to_show.match_score is not None:
                _stat_items.append(
                    mo.stat(f"{_trip_to_show.match_score:.1%}", label="Direct match", bordered=False)
                )
            if _trip_to_show.frechet_distance is not None:
                _stat_items.append(
                    mo.stat(f"{_trip_to_show.frechet_distance:.1f} m", label="Snap dist", bordered=False)
                )
        _detail_stats = mo.hstack(_stat_items, gap=1, justify="end")

        # -- Full-width header: title + stats --
        _header_row = mo.hstack(
            [mo.md("## Trip details"), _detail_stats],
            justify="space-between",
            align="center",
            gap=0,
        )

        # -- Detail map --
        _detail_map = mo.vstack(
            [
                mo.hstack(
                    [
                        mo.md(" &nbsp; ".join(_legend_parts)),
                        mo.md("_Scroll to zoom \u00b7 Drag to pan_"),
                    ],
                    justify="start",
                    gap=1,
                ).style(style={"margin": 0}),
                _detail_deck,
            ],
            justify="start"
        ).style(style={"margin": 0})

        # -- Right side: clean button / trip table + trip points table --
        _right_content = []


        if _trip_to_show:
            _trip_df = pd.DataFrame([{
                "id": str(_trip_to_show.id),
                "status": _trip_to_show.status.value,
                "match_score": f"{_trip_to_show.match_score:.1%}" if _trip_to_show.match_score is not None else "\u2014",
                "snap_distance_m": f"{_trip_to_show.frechet_distance:.1f} m" if _trip_to_show.frechet_distance is not None else "\u2014",
                "processed_at": _trip_to_show.processed_at,
            }])
            _trip_header_items = [mo.md("**Cleaned Trip**")]

            if clean_btn is not None:
                _trip_header_items.append(clean_btn)

            _right_content.append(
                mo.hstack(_trip_header_items, justify="space-between", align="center")
            )
            _right_content.append(mo.ui.table(data=_trip_df, label="", pagination=False, selection=None))

            if _clean_pts:
                _pts_df = pd.DataFrame([
                    {
                        "index": p.point_index,
                        "latitude": round(p.latitude, 6),
                        "longitude": round(p.longitude, 6),
                        "timestamp": p.timestamp,
                    }
                    for p in _clean_pts
                ])
                _right_content.append(mo.md(f"**Trip points** ({len(_clean_pts)})"))
                _right_content.append(
                    mo.ui.table(data=_pts_df, label="", pagination=True, selection=None)
                )
        else:
            _no_trip_items = [mo.md("**Cleaned Trip**")]
            if clean_btn is not None:
                _no_trip_items.append(clean_btn)

            _right_content.append(
                mo.hstack(_no_trip_items, justify="space-between", align="center")
            )
            _right_content.append(mo.md("_No cleaned trip yet._"))

        _right_section = mo.vstack(_right_content, gap=0, justify="start").style(style={"max-width": "45vw", "margin": 0})

        detail_section = mo.vstack([
            _header_row,
            mo.hstack(
                [_detail_map, _right_section],
                widths=[1, 1],
                gap=1,
                justify="start",
            ).style(style={"margin": 0}),
        ])

    detail_section
    return


@app.cell
def _(cleaned_trip, existing_trip, mo):
    _active_trip = cleaned_trip or existing_trip
    if _active_trip is None:
        resample_interval_input = None
        resample_btn = None
    else:
        resample_interval_input = mo.ui.number(
            value=20, start=1, stop=500, step=1, label="Interval (m)"
        )
        resample_btn = mo.ui.button(
            label="Resample",
            value=0,
            on_click=lambda v: (v or 0) + 1,
        )
    return resample_btn, resample_interval_input


@app.cell
def _(
    cleaned_trip,
    db,
    existing_trip,
    mo,
    resample_btn,
    resample_interval_input,
    select,
):
    db.rollback()
    from database.models.route import ResampledTrip as _ResampledTrip

    _active_trip = cleaned_trip or existing_trip
    resampled_trips_list = []
    selected_resampled_id = None
    _resample_callout = None

    if _active_trip is not None:
        if resample_btn is not None and (resample_btn.value or 0) > 0 and resample_interval_input is not None:
            from database.connection import SessionLocal as _SessionLocal
            from geodata.resample import resample_trip as _resample_trip

            _db = _SessionLocal(expire_on_commit=False)
            try:
                _result = _resample_trip(_db, _active_trip.id, float(resample_interval_input.value))
                selected_resampled_id = str(_result.resampled_trip.id)
                _verb = "Already resampled" if _result.was_existing else "Resampled"
                _kind = "info" if _result.was_existing else "success"
                _resample_callout = mo.callout(
                    mo.md(
                        f"{_verb} at **{_result.interval_meters:.0f} m** — "
                        f"**{_result.point_count}** points"
                    ),
                    kind=_kind,
                )
            except Exception as _e:
                _db.rollback()
                _resample_callout = mo.callout(mo.md(f"Error: {_e}"), kind="danger")
            finally:
                _db.close()

        resampled_trips_list = (
            db.execute(
                select(_ResampledTrip)
                .where(_ResampledTrip.trip_id == _active_trip.id)
                .order_by(_ResampledTrip.interval_meters)
            )
            .scalars()
            .all()
        )

    _resample_callout
    return resampled_trips_list, selected_resampled_id


@app.cell
def _(mo, resampled_trips_list, selected_resampled_id):
    if not resampled_trips_list:
        resample_dropdown = None
    else:
        _options = {
            f"{rt.interval_meters:.0f} m  ({rt.point_count} pts)": str(rt.id)
            for rt in resampled_trips_list
        }
        _default_key = next(
            (k for k, v in _options.items() if v == selected_resampled_id),
            next(iter(_options)),
        )
        resample_dropdown = mo.ui.dropdown(
            options=_options,
            value=_default_key,
            label="Show resampled",
        )
    return (resample_dropdown,)


@app.cell
def _(
    cleaned_trip,
    db,
    existing_trip,
    mo,
    pdk,
    resample_btn,
    resample_dropdown,
    resample_interval_input,
    resampled_trips_list,
    select,
):
    db.rollback()
    from database.models.route import ResampledTripPoint as _ResampledTripPoint

    _active_trip = cleaned_trip or existing_trip

    if _active_trip is None or resample_interval_input is None:
        resample_section = None
    else:
        _controls = mo.hstack(
            [resample_interval_input, resample_btn]
            + ([resample_dropdown] if resample_dropdown is not None else []),
            gap=1,
            align="end",
        )

        _rt = None
        if resample_dropdown is not None and resample_dropdown.value is not None:
            _rt = next(
                (rt for rt in resampled_trips_list if str(rt.id) == resample_dropdown.value),
                None,
            )
        elif resampled_trips_list:
            _rt = resampled_trips_list[0]

        if _rt is not None:
            _pts = (
                db.execute(
                    select(_ResampledTripPoint)
                    .where(_ResampledTripPoint.resampled_trip_id == _rt.id)
                    .order_by(_ResampledTripPoint.point_index)
                )
                .scalars()
                .all()
            )

            if _pts:
                _coords = [[p.longitude, p.latitude, 0] for p in _pts]
                _lons = [c[0] for c in _coords]
                _lats = [c[1] for c in _coords]
                _center_lat = sum(_lats) / len(_lats)
                _center_lon = sum(_lons) / len(_lons)

                _layers = [
                    pdk.Layer(
                        "PathLayer",
                        [{"path": _coords, "color": [99, 102, 241]}],
                        get_path="path",
                        get_color="color",
                        get_width=5,
                        width_min_pixels=3,
                    ),
                    pdk.Layer(
                        "ScatterplotLayer",
                        data=[{"coordinates": c} for c in _coords],
                        get_position="coordinates",
                        get_color=[99, 102, 241],
                        get_radius=2,
                        radius_min_pixels=4,
                        stroked=True,
                        get_line_color=[255, 255, 255],
                        line_width_min_pixels=1,
                    ),
                ]

                _deck = pdk.Deck(
                    map_style="light",
                    map_provider="carto",
                    initial_view_state=pdk.ViewState(
                        latitude=_center_lat,
                        longitude=_center_lon,
                        zoom=14,
                        pitch=0,
                        bearing=0,
                    ),
                    layers=_layers,
                    height=450,
                )

                _stats = mo.hstack(
                    [
                        mo.stat(len(_pts), label="Points", bordered=False),
                        mo.stat(f"{_rt.interval_meters:.0f} m", label="Interval", bordered=False),
                        mo.stat(
                            f"{_rt.match_score:.1%}" if _rt.match_score else "—",
                            label="Match score",
                            bordered=False,
                        ),
                    ],
                    gap=1,
                    justify="start",
                )

                _map_area = mo.vstack(
                    [
                        mo.hstack(
                            [
                                mo.md('<span style="color:#6366f1">●</span> Resampled'),
                                mo.md("_Scroll to zoom · Drag to pan_"),
                            ],
                            gap=1,
                            justify="start",
                        ),
                        _deck,
                        _stats,
                    ]
                )
            else:
                _map_area = mo.md("_No points found for this resampled trip._")
        else:
            _map_area = mo.md(
                "_No resampled trip yet. Set an interval and click **Resample**._"
            )

        resample_section = mo.vstack(
            [mo.md("## Resampled trip"), _controls, _map_area],
            gap=1,
        )

    resample_section
    return


if __name__ == "__main__":
    app.run()
