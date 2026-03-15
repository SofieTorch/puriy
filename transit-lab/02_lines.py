import marimo

__generated_with = "0.20.4"
app = marimo.App(width="medium")


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
    from sqlalchemy import select

    from components.tracing import init_tracing
    from database.connection import SessionLocal
    from database.models.line import Line, LineStatus
    from database.models.trip import TripSession
    from database.models.route import Trip, ResampledTrip, ResampledTripPoint
    from geodata.match import match_line
    from geodata.merge import merge_lines
    from geodata.resample import resample_line

    return (
        Line,
        LineStatus,
        ResampledTrip,
        ResampledTripPoint,
        SessionLocal,
        Trip,
        TripSession,
        init_tracing,
        match_line,
        math,
        merge_lines,
        mo,
        pd,
        pdk,
        resample_line,
        select,
        to_shape,
    )


@app.cell
def _(SessionLocal, init_tracing, mo):
    db = SessionLocal()
    init_tracing()
    get_refresh, set_refresh = mo.state(0)
    get_preserved_line_ids, set_preserved_line_ids = mo.state([])
    get_last_resampled_interval, set_last_resampled_interval = mo.state(None)
    get_last_resampled_min_score, set_last_resampled_min_score = mo.state(None)
    return (
        db,
        get_last_resampled_interval,
        get_last_resampled_min_score,
        get_preserved_line_ids,
        get_refresh,
        set_last_resampled_interval,
        set_last_resampled_min_score,
        set_preserved_line_ids,
        set_refresh,
    )


@app.cell
def _(Line, db, get_preserved_line_ids, get_refresh, mo, pd, select):
    _ = get_refresh()
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
    preserved = get_preserved_line_ids()
    initial_selection = (
        lines_df.index[lines_df["id"].isin(preserved)].tolist()
        if preserved
        else None
    )
    lines_table = mo.ui.table(
        data=lines_df,
        label="Lines",
        pagination=True,
        initial_selection=initial_selection,
    )
    return (lines_table,)


@app.cell
def _(lines_table, mo):
    selected = lines_table.value
    selected_line_ids = (
        selected["id"].tolist()
        if selected is not None and not selected.empty and "id" in selected.columns
        else []
    )

    merge_btn = mo.ui.button(
        label="Merge selected lines",
        value=0,
        on_click=lambda v: (v or 0) + 1,
        kind="neutral",
        disabled=len(selected_line_ids) < 2,
    )
    return merge_btn, selected_line_ids


@app.cell
def _(
    db,
    merge_btn,
    merge_lines,
    selected_line_ids,
    set_preserved_line_ids,
    set_refresh,
):
    if (merge_btn.value or 0) > 0 and len(selected_line_ids) >= 2:
        try:
            merge_lines(db, selected_line_ids)
            db.commit()
            set_preserved_line_ids(selected_line_ids)
            set_refresh(lambda v: v + 1)
        except Exception:
            db.rollback()
    return


@app.cell
def _(merge_btn, mo, selected_line_ids):
    table_header = mo.hstack(
        [mo.md("**Lines**"), merge_btn],
        justify="space-between",
        align="center",
    )
    view_3d_switch = mo.ui.switch(value=False, label="3D view")
    color_switch = mo.ui.switch(value=True, label="Colors")
    confidence_slider = mo.ui.number(
        value=0.0, start=0.0, stop=1.0, step=0.05, label="Min confidence",
    )
    clean_btn = mo.ui.button(
        label="Batch clean sessions",
        value=0,
        on_click=lambda v: (v or 0) + 1,
        kind="neutral",
        disabled=len(selected_line_ids) != 1,
    )
    resample_interval_input = mo.ui.number(
        value=20, start=1, stop=500, step=1, label="Interval (m)",
    )
    resample_min_score_slider = mo.ui.number(
        value=0.0, start=0.0, stop=1.0, step=0.05, label="Min score",
    )
    resample_btn = mo.ui.button(
        label="Batch resample",
        value=0,
        on_click=lambda v: (v or 0) + 1,
        kind="neutral",
        disabled=len(selected_line_ids) != 1,
    )
    return (
        clean_btn,
        color_switch,
        confidence_slider,
        resample_btn,
        resample_interval_input,
        resample_min_score_slider,
        table_header,
        view_3d_switch,
    )


@app.cell
def _(
    clean_btn,
    db,
    match_line,
    mo,
    selected_line_ids,
    set_preserved_line_ids,
    set_refresh,
):
    clean_result_output = None
    if (clean_btn.value or 0) > 0 and len(selected_line_ids) == 1:
        try:
            _result = match_line(db, selected_line_ids[0])
            _msg = f"Matched **{len(_result.matched)}** sessions"
            if _result.failed:
                _msg += f", **{len(_result.failed)}** failed"
            if _result.skipped:
                _msg += f", **{_result.skipped}** skipped"
            clean_result_output = mo.callout(mo.md(_msg), kind="success")
            set_preserved_line_ids(selected_line_ids)
            set_refresh(lambda v: v + 1)
        except Exception as _e:
            db.rollback()
            clean_result_output = mo.callout(mo.md(f"Error: {_e}"), kind="danger")
    return (clean_result_output,)


@app.cell
def _(
    db,
    mo,
    resample_btn,
    resample_interval_input,
    resample_line,
    resample_min_score_slider,
    selected_line_ids,
    set_last_resampled_interval,
    set_last_resampled_min_score,
    set_preserved_line_ids,
    set_refresh,
):
    resample_result_output = None
    if (resample_btn.value or 0) > 0 and len(selected_line_ids) == 1:
        try:
            _interval = float(resample_interval_input.value)
            _min_score = resample_min_score_slider.value
            _result = resample_line(
                db,
                selected_line_ids[0],
                _interval,
                min_match_score=_min_score,
            )
            _new = sum(1 for r in _result.resampled if not r.was_existing)
            _existing = sum(1 for r in _result.resampled if r.was_existing)
            _msg = f"Resampled **{_new}** trips"
            if _existing:
                _msg += f", **{_existing}** already resampled"
            if _result.skipped:
                _msg += f", **{len(_result.skipped)}** skipped"
            if _result.failed:
                _msg += f", **{len(_result.failed)}** failed"
            resample_result_output = mo.callout(mo.md(_msg), kind="success")
            set_preserved_line_ids(selected_line_ids)
            set_last_resampled_interval(_interval)
            set_last_resampled_min_score(_min_score)
            set_refresh(lambda v: v + 1)
        except Exception as _e:
            db.rollback()
            resample_result_output = mo.callout(mo.md(f"Error: {_e}"), kind="danger")
    return (resample_result_output,)


@app.cell
def _(
    ResampledTrip,
    Trip,
    db,
    get_last_resampled_interval,
    get_last_resampled_min_score,
    get_refresh,
    mo,
    select,
    selected_line_ids,
):
    _ = get_refresh()
    if selected_line_ids:
        _pairs = db.execute(
            select(ResampledTrip.interval_meters, ResampledTrip.match_score)
            .join(Trip, ResampledTrip.trip_id == Trip.id)
            .where(Trip.line_id.in_(selected_line_ids))
            .distinct()
            .order_by(ResampledTrip.interval_meters, ResampledTrip.match_score)
        ).all()
    else:
        _pairs = []

    if _pairs:
        def _label(iv, fs):
            return f"{iv:.0f} m / ≥{fs:.0%}" if fs is not None else f"{iv:.0f} m"

        _options = {_label(iv, fs): (iv, fs) for iv, fs in _pairs}
        _last_iv = get_last_resampled_interval()
        _last_fs = get_last_resampled_min_score()
        _default = next(
            (k for k, v in _options.items() if v == (_last_iv, _last_fs)),
            next(iter(_options)),
        )
        resample_interval_dropdown = mo.ui.dropdown(
            options=_options,
            value=_default,
            label="Show",
        )
    else:
        resample_interval_dropdown = None

    show_points_switch = mo.ui.switch(value=True, label="Show points")
    return resample_interval_dropdown, show_points_switch


@app.cell
def _(
    ResampledTrip,
    ResampledTripPoint,
    Trip,
    db,
    mo,
    pdk,
    resample_interval_dropdown,
    select,
    selected_line_ids,
    show_points_switch,
):
    if resample_interval_dropdown is not None:
        _interval, _filter_min_score = resample_interval_dropdown.value
    else:
        _interval, _filter_min_score = None, None

    if not selected_line_ids or _interval is None:
        resampled_map = mo.md("Select a line and run **Batch resample** to see resampled paths.")
    else:
        _trip_ids = [
            t.id for t in db.execute(
                select(Trip).where(Trip.line_id.in_(selected_line_ids))
            ).scalars().all()
        ]
        _score_filter = (
            ResampledTrip.match_score.is_(None)
            if _filter_min_score is None
            else ResampledTrip.match_score == _filter_min_score
        )
        _resampled_trips = db.execute(
            select(ResampledTrip).where(
                ResampledTrip.trip_id.in_(_trip_ids),
                ResampledTrip.interval_meters == _interval,
                _score_filter,
            )
        ).scalars().all()

        if not _resampled_trips:
            resampled_map = mo.md(
                "_No resampled trips at this interval. Click **Batch resample** to generate them._"
            )
        else:
            _PATH_COLORS = [
                [59, 130, 246],   # blue
                [34, 197, 94],    # green
                [234, 179, 8],    # amber
                [168, 85, 247],   # violet
                [236, 72, 153],   # pink
                [20, 184, 166],   # teal
            ]
            _layer_data = []
            _scatter_data = []
            _all_coords = []
            _total_points = 0

            for _i, _rt in enumerate(_resampled_trips):
                _pts = db.execute(
                    select(ResampledTripPoint)
                    .where(ResampledTripPoint.resampled_trip_id == _rt.id)
                    .order_by(ResampledTripPoint.point_index)
                ).scalars().all()
                if _pts:
                    _rgb = _PATH_COLORS[_i % len(_PATH_COLORS)]
                    _coords = [[p.longitude, p.latitude, 0] for p in _pts]
                    _layer_data.append({
                        "path": _coords,
                        "color": [*_rgb, 120],
                        "points": len(_pts),
                        "score": f"{_rt.match_score:.1%}" if _rt.match_score else "—",
                    })
                    if show_points_switch.value:
                        for _c in _coords:
                            _scatter_data.append({"coordinates": _c, "color": _rgb})
                    _all_coords.extend(_coords)
                    _total_points += len(_pts)

            if _all_coords:
                _lons = [c[0] for c in _all_coords]
                _lats = [c[1] for c in _all_coords]
                _center_lat = sum(_lats) / len(_lats)
                _center_lon = sum(_lons) / len(_lons)
            else:
                _center_lat, _center_lon = 40.4, -3.7

            _layers = []
            if _layer_data:
                _layers.append(
                    pdk.Layer(
                        "PathLayer",
                        _layer_data,
                        get_path="path",
                        get_color="color",
                        get_width=5,
                        width_min_pixels=3,
                        pickable=True,
                        auto_highlight=True,
                        highlight_color=[255, 255, 100, 255],
                    )
                )
            if _scatter_data:
                _layers.append(
                    pdk.Layer(
                        "ScatterplotLayer",
                        _scatter_data,
                        get_position="coordinates",
                        get_color="color",
                        get_radius=2,
                        radius_min_pixels=2,
                        stroked=True,
                        get_line_color=[255, 255, 255],
                        line_width_min_pixels=1,
                    )
                )

            _deck = pdk.Deck(
                map_style="light",
                map_provider="carto",
                initial_view_state=pdk.ViewState(
                    latitude=_center_lat, longitude=_center_lon,
                    zoom=15, pitch=0, bearing=0,
                ),
                layers=_layers,
                height=400,
                tooltip={
                    "html": "<b>Points:</b> {points}<br/><b>Score:</b> {score}",
                    "style": {
                        "backgroundColor": "white",
                        "color": "black",
                        "fontFamily": "ui-monospace, monospace",
                        "border": "1px solid grey",
                        "fontSize": "12px",
                    },
                },
            )
            _stats = mo.hstack(
                [
                    mo.stat(len(_resampled_trips), label="Resampled trips", bordered=False),
                    mo.stat(f"{_interval:.0f} m", label="Interval", bordered=False),
                    mo.stat(_total_points, label="Total points", bordered=False),
                    mo.stat(f"≥{_filter_min_score:.0%}" if _filter_min_score is not None else "—", label="Min score", bordered=False),
                ],
                gap=1,
                justify="start",
            )
            resampled_map = mo.vstack([_stats, _deck], gap=0.5)
    return (resampled_map,)


@app.cell
def _(LineStatus, mo):
    new_line_name = mo.ui.text(value="", label="Name")
    new_line_status = mo.ui.dropdown(
        options=[s.value for s in LineStatus],
        value=LineStatus.PENDING.value,
        label="Status",
    )
    new_line_description = mo.ui.text(value="", label="Description")
    create_btn = mo.ui.button(
        label="Create",
        value=0,
        on_click=lambda v: (v or 0) + 1,
        kind="neutral",
    )
    create_section = mo.hstack(
        [mo.md("### New line:"), new_line_name, new_line_status, new_line_description, create_btn],
        gap=1,
        align="center",
        justify="start",
    )
    return (
        create_btn,
        create_section,
        new_line_description,
        new_line_name,
        new_line_status,
    )


@app.cell
def _(
    Line,
    LineStatus,
    create_btn,
    db,
    mo,
    new_line_description,
    new_line_name,
    new_line_status,
    set_refresh,
):
    create_result_output = None
    if (create_btn.value or 0) > 0 and new_line_name.value.strip():
        try:
            _new_line = Line(
                name=new_line_name.value.strip(),
                status=LineStatus(new_line_status.value),
                description=new_line_description.value.strip() or None,
            )
            db.add(_new_line)
            db.commit()
            create_result_output = mo.callout(
                mo.md(f"Created line **{_new_line.name}**"), kind="success",
            )
            set_refresh(lambda v: v + 1)
        except Exception as _e:
            db.rollback()
            create_result_output = mo.callout(mo.md(f"Error: {_e}"), kind="danger")
    return (create_result_output,)


@app.cell
def _(Line, LineStatus, db, mo, selected_line_ids):
    if len(selected_line_ids) != 1:
        _hint = (
            mo.md("Select exactly one line to edit name, status and description.")
            if not selected_line_ids
            else mo.md("Select exactly one line to edit (or 2+ to merge).")
        )
        edit_section = mo.hstack(
            [mo.md("### Update line:"), _hint],
            gap=1,
            align="center",
            justify="start",
        )
        save_btn = name_input = status_dropdown = description_input = None
    else:
        line_id = selected_line_ids[0]
        line = db.get(Line, line_id)
        if line is None:
            edit_section = mo.md("Line not found.")
            save_btn = name_input = status_dropdown = description_input = None
        else:
            name_input = mo.ui.text(value=line.name, label="Name")
            status_dropdown = mo.ui.dropdown(
                options=[s.value for s in LineStatus],
                value=line.status.value,
                label="Status",
            )
            description_input = mo.ui.text(value=line.description or "", label="Description")
            save_btn = mo.ui.button(
                label="Save",
                value=0,
                on_click=lambda v: (v or 0) + 1,
                kind="neutral",
            )
            edit_section = mo.hstack(
                [mo.md("### Update line:"), name_input, status_dropdown, description_input, save_btn],
                gap=1,
                align="center",
                justify="start",
            )
    return (
        description_input,
        edit_section,
        name_input,
        save_btn,
        status_dropdown,
    )


@app.cell
def _(
    Line,
    LineStatus,
    db,
    description_input,
    name_input,
    save_btn,
    selected_line_ids,
    set_preserved_line_ids,
    set_refresh,
    status_dropdown,
):
    if (
        save_btn is not None
        and name_input is not None
        and status_dropdown is not None
        and description_input is not None
    ):
        if (save_btn.value or 0) > 0:
            lid = selected_line_ids[0]
            line_to_update = db.get(Line, lid)
            if line_to_update is not None:
                line_to_update.name = name_input.value
                line_to_update.status = LineStatus(status_dropdown.value)
                line_to_update.description = description_input.value or None
                db.add(line_to_update)
                db.commit()
                set_preserved_line_ids(selected_line_ids)
                set_refresh(lambda v: v + 1)
    return


@app.cell
def _(
    Trip,
    TripSession,
    color_switch,
    confidence_slider,
    db,
    math,
    mo,
    pdk,
    select,
    selected_line_ids,
    to_shape,
    view_3d_switch,
):
    pitch = 60 if view_3d_switch.value else 0
    _min_confidence = confidence_slider.value
    _use_colors = color_switch.value

    def _haversine_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
        R = 6_371_000
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    def _format_distance(m: float) -> str:
        if m >= 1000:
            return f"{m / 1000:.1f} km"
        return f"{int(m)} m"

    _PATH_COLORS = [
        [59, 130, 246],   # blue
        [34, 197, 94],    # green
        [234, 179, 8],    # amber
        [168, 85, 247],   # violet
        [236, 72, 153],   # pink
        [20, 184, 166],   # teal
    ]
    _SINGLE_COLOR = [59, 130, 246]  # blue
    _DEFAULT_ALPHA = 120

    _default_view = pdk.ViewState(
        latitude=40.4, longitude=-3.7, zoom=14, pitch=pitch, bearing=0,
    )

    if not selected_line_ids:
        sessions_map = mo.md("Select one or more lines to see trip sessions on the map.")
        trips_map = pdk.Deck(
            map_style="light", map_provider="carto",
            initial_view_state=_default_view, layers=[], height=400,
        )
    else:
        # -- Query trips first (needed for confidence filtering of sessions) --
        _trips_list = list(
            db.execute(
                select(Trip).where(Trip.line_id.in_(selected_line_ids))
            ).scalars().all()
        )

        # Build lookup: session_id -> best match_score
        _session_best_score = {}
        for _t in _trips_list:
            _score = _t.match_score if _t.match_score is not None else 0.0
            _prev = _session_best_score.get(_t.session_id, -1.0)
            if _score > _prev:
                _session_best_score[_t.session_id] = _score

        # -- Query sessions and filter by confidence --
        _all_sessions = list(
            db.execute(
                select(TripSession)
                .where(TripSession.line_id.in_(selected_line_ids))
                .order_by(TripSession.started_at.desc())
            ).scalars().all()
        )

        if _min_confidence > 0:
            sessions_list = [
                s for s in _all_sessions
                if _session_best_score.get(s.id, 0.0) >= _min_confidence
            ]
        else:
            sessions_list = _all_sessions

        # -- Assign a stable color index per session (shared with trips) --
        _session_color = {}
        _color_counter = 0
        for _s in sessions_list:
            _session_color[_s.id] = _color_counter
            _color_counter += 1

        # -- Raw sessions layer --
        _path_layer_data = []
        _all_coords = []

        for _s in sessions_list:
            if _s.computed_path is not None:
                try:
                    _geom = to_shape(_s.computed_path)
                    _path_coords = [[c[0], c[1], 0] for c in _geom.coords]
                    _pts_count = len(_path_coords)
                    _dist = 0.0
                    for _j in range(len(_path_coords) - 1):
                        _dist += _haversine_m(
                            _path_coords[_j][0], _path_coords[_j][1],
                            _path_coords[_j + 1][0], _path_coords[_j + 1][1],
                        )
                    if _use_colors:
                        _rgb = _PATH_COLORS[_session_color[_s.id] % len(_PATH_COLORS)]
                    else:
                        _rgb = _SINGLE_COLOR
                    _path_layer_data.append({
                        "path": _path_coords,
                        "color": [*_rgb, _DEFAULT_ALPHA],
                        "points": _pts_count,
                        "distance": _format_distance(_dist),
                    })
                    _all_coords.extend(_path_coords)
                except Exception:
                    pass

        if _all_coords:
            _lons = [c[0] for c in _all_coords]
            _lats = [c[1] for c in _all_coords]
            _center_lat = sum(_lats) / len(_lats)
            _center_lon = sum(_lons) / len(_lons)
        else:
            _center_lat, _center_lon = 40.4, -3.7

        _raw_layers = []
        if _path_layer_data:
            _raw_layers.append(
                pdk.Layer(
                    "PathLayer",
                    _path_layer_data,
                    get_path="path",
                    get_color="color",
                    get_width=5,
                    width_min_pixels=3,
                    pickable=True,
                    auto_highlight=True,
                    highlight_color=[255, 255, 100, 255],
                ),
            )

        _centered_view = pdk.ViewState(
            latitude=_center_lat, longitude=_center_lon,
            zoom=14, pitch=pitch, bearing=0,
        )
        _tooltip = {
            "html": "<b>Points:</b> {points}<br/><b>Distance:</b> {distance}",
            "style": {
                "backgroundColor": "white",
                "color": "black",
                "fontFamily": "ui-monospace, monospace",
                "border": "1px solid grey",
                "fontSize": "12px",
            },
        }

        sessions_map = pdk.Deck(
            map_style="light", map_provider="carto",
            initial_view_state=_centered_view,
            layers=_raw_layers, height=400, tooltip=_tooltip,
        )

        # -- Cleaned trips layer (filtered by confidence) --
        _filtered_trips = [
            _t for _t in _trips_list
            if (_t.match_score or 0.0) >= _min_confidence
        ]

        _trip_layer_data = []
        for _t in _filtered_trips:
            if _t.computed_path is not None:
                try:
                    _geom = to_shape(_t.computed_path)
                    _coords = [[c[0], c[1], 0] for c in _geom.coords]
                    _pts_count = len(_coords)
                    _dist = 0.0
                    for _j in range(len(_coords) - 1):
                        _dist += _haversine_m(
                            _coords[_j][0], _coords[_j][1],
                            _coords[_j + 1][0], _coords[_j + 1][1],
                        )
                    if _use_colors:
                        _cidx = _session_color.get(_t.session_id, 0)
                        _rgb = _PATH_COLORS[_cidx % len(_PATH_COLORS)]
                    else:
                        _rgb = _SINGLE_COLOR
                    _trip_layer_data.append({
                        "path": _coords,
                        "color": [*_rgb, _DEFAULT_ALPHA],
                        "points": _pts_count,
                        "distance": _format_distance(_dist),
                    })
                except Exception:
                    pass

        _trip_layers = []
        if _trip_layer_data:
            _trip_layers.append(
                pdk.Layer(
                    "PathLayer",
                    _trip_layer_data,
                    get_path="path",
                    get_color="color",
                    get_width=5,
                    width_min_pixels=3,
                    pickable=True,
                    auto_highlight=True,
                    highlight_color=[255, 255, 100, 255],
                ),
            )

        trips_map = pdk.Deck(
            map_style="light", map_provider="carto",
            initial_view_state=_centered_view,
            layers=_trip_layers, height=400, tooltip=_tooltip,
        )
    return sessions_map, trips_map


@app.cell
def _(
    clean_btn,
    clean_result_output,
    color_switch,
    confidence_slider,
    create_result_output,
    create_section,
    edit_section,
    lines_table,
    mo,
    resample_btn,
    resample_interval_dropdown,
    resample_interval_input,
    resample_min_score_slider,
    resample_result_output,
    resampled_map,
    selected_line_ids,
    sessions_map,
    show_points_switch,
    table_header,
    trips_map,
    view_3d_switch,
):
    _items = [create_section]
    if create_result_output is not None:
        _items.append(create_result_output)
    _items += [
        edit_section,
        table_header,
        lines_table,
    ]

    if not selected_line_ids:
        _items.append(mo.callout(mo.md("Select a line to see its trips."), kind="info"))
    else:
        _items.append(
            mo.hstack(
                [mo.md("**Maps**"), clean_btn, confidence_slider, color_switch, view_3d_switch],
                justify="space-between",
                align="center",
            )
        )
        if clean_result_output is not None:
            _items.append(clean_result_output)
        _items.append(
            mo.hstack(
                [
                    mo.vstack([mo.md("**Raw sessions**"), sessions_map], gap=0.5),
                    mo.vstack([mo.md("**Cleaned trips**"), trips_map], gap=0.5),
                ],
                widths=[1, 1],
                gap=1,
            ),
        )
        _resample_controls = [
            mo.md("**Resample**"),
            resample_interval_input,
            resample_min_score_slider,
            resample_btn,
        ]
        if resample_interval_dropdown is not None:
            _resample_controls.append(resample_interval_dropdown)
        _resample_controls.append(show_points_switch)
        _items.append(mo.hstack(_resample_controls, gap=1, align="end"))
        if resample_result_output is not None:
            _items.append(resample_result_output)
        _items.append(mo.vstack([mo.md("**Resampled trips**"), resampled_map], gap=0.5))

    (
        mo.vstack(_items, gap=1, align="stretch")
        .style(style={"max-width": "100%"}, overflow_x="auto")
    )
    return


if __name__ == "__main__":
    app.run()
