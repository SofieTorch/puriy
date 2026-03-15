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

    from database.connection import SessionLocal
    from database.models.line import Line, LineStatus
    from database.models.trip import TripSession
    from database.models.route import Trip
    from geodata.match import match_line
    from geodata.merge import merge_lines

    return (
        Line,
        LineStatus,
        SessionLocal,
        Trip,
        TripSession,
        match_line,
        math,
        merge_lines,
        mo,
        pd,
        pdk,
        select,
        to_shape,
    )


@app.cell
def _(SessionLocal, mo):
    db = SessionLocal()
    get_refresh, set_refresh = mo.state(0)
    get_preserved_line_ids, set_preserved_line_ids = mo.state([])
    return (
        db,
        get_preserved_line_ids,
        get_refresh,
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
    confidence_slider = mo.ui.slider(
        start=0, stop=100, step=5, value=0, label="Min confidence %",
    )
    clean_btn = mo.ui.button(
        label="Batch clean sessions",
        value=0,
        on_click=lambda v: (v or 0) + 1,
        kind="neutral",
        disabled=len(selected_line_ids) != 1,
    )
    return (
        clean_btn,
        color_switch,
        confidence_slider,
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
    return create_btn, create_section, new_line_description, new_line_name, new_line_status


@app.cell
def _(Line, LineStatus, create_btn, db, mo, new_line_description, new_line_name, new_line_status, set_refresh):
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
    _min_confidence = confidence_slider.value / 100
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
        latitude=40.4, longitude=-3.7, zoom=10, pitch=pitch, bearing=0,
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
            zoom=12, pitch=pitch, bearing=0,
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
    sessions_map,
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
        mo.hstack(
            [mo.md("**Maps**"), clean_btn, confidence_slider, color_switch, view_3d_switch],
            justify="space-between",
            align="center",
        ),
    ]
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
    (
        mo.vstack(_items, gap=1, align="stretch")
        .style(style={"max-width": "100%"}, overflow_x="auto")
    )
    return


if __name__ == "__main__":
    app.run()
