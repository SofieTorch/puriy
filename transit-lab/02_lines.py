import marimo

__generated_with = "0.20.4"
app = marimo.App(width="full")


@app.cell
def _():
    from components.navbar import navbar

    return


@app.cell
def _():
    import math

    import marimo as mo
    import pandas as pd
    import pydeck as pdk
    from geoalchemy2.shape import to_shape
    from sqlalchemy import select

    from components.reconstruction_ui import build_approach_selector, build_param_panel
    from components.tracing import init_tracing
    from database.connection import SessionLocal
    from database.models.line import Line, LineStatus
    from database.models.trip import TripSession
    from database.models.route import Trip, EstimationStatus, RouteEstimation, RouteSegment
    from geodata.reconstruction import get_approach, get_approaches, resolve_params
    from geodata.reconstruction.dbscan import FilteredRouteResult
    from geodata.reconstruction.arman_tampere import ArmanTampereResult
    from geodata.match import match_line
    from geodata.merge import merge_lines
    from geodata.validate import validate_trip_directions

    return (
        ArmanTampereResult,
        FilteredRouteResult,
        Line,
        LineStatus,
        RouteSegment,
        SessionLocal,
        Trip,
        TripSession,
        build_approach_selector,
        build_param_panel,
        get_approach,
        get_approaches,
        init_tracing,
        match_line,
        math,
        merge_lines,
        mo,
        pd,
        pdk,
        resolve_params,
        select,
        to_shape,
        validate_trip_directions,
    )


@app.cell
def _(SessionLocal, init_tracing, mo):
    db = SessionLocal()
    init_tracing()
    get_refresh, set_refresh = mo.state(0)
    get_preserved_line_ids, set_preserved_line_ids = mo.state([])
    get_direction_result, set_direction_result = mo.state(None)
    get_reconstruction_result, set_reconstruction_result = mo.state(None)
    return (
        db,
        get_direction_result,
        get_preserved_line_ids,
        get_reconstruction_result,
        get_refresh,
        set_direction_result,
        set_preserved_line_ids,
        set_reconstruction_result,
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
    return create_btn, new_line_description, new_line_name, new_line_status


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

    edit_section
    return description_input, name_input, save_btn, status_dropdown


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
    create_btn,
    create_result_output,
    lines_table,
    merge_btn,
    mo,
    new_line_description,
    new_line_name,
    new_line_status,
):
    lines_tab_content = mo.vstack(
        [
            mo.hstack(
                [mo.md("**Lines**"), merge_btn],
                justify="space-between",
                align="center",
            ),
            lines_table,
            mo.hstack(
                [mo.md("### New line:"), new_line_name, new_line_status, new_line_description, create_btn],
                gap=1,
                align="center",
                justify="start",
            ),
            mo.plain(create_result_output) if create_result_output else mo.md(""),
        ],
        gap=1,
        align="stretch",
    )
    return (lines_tab_content,)


@app.cell
def _(mo):
    view_3d_switch = mo.ui.switch(value=False, label="3D view")
    color_switch = mo.ui.switch(value=True, label="Colors")
    confidence_slider = mo.ui.number(
        value=0.0, start=0.0, stop=1.0, step=0.05, label="Min confidence",
    )
    return color_switch, confidence_slider, view_3d_switch


@app.cell
def _(mo, selected_line_ids):
    clean_btn = mo.ui.button(
        label="Batch clean sessions",
        value=0,
        on_click=lambda v: (v or 0) + 1,
        kind="neutral",
        disabled=len(selected_line_ids) != 1,
    )
    return (clean_btn,)


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
    mo,
    selected_line_ids,
    sessions_map,
    trips_map,
    view_3d_switch,
):
    if not selected_line_ids:
        trips_tab_content = mo.callout(
            mo.md("Select a line in the **Lines** tab to see its trips."),
            kind="info",
        )
    else:
        _controls = mo.hstack(
            [clean_btn, confidence_slider, color_switch, view_3d_switch],
            gap=1,
            align="center",
        )
        _maps = mo.hstack(
            [
                mo.vstack([mo.md("**Raw sessions**"), sessions_map], gap=0.5),
                mo.vstack([mo.md("**Cleaned trips**"), trips_map], gap=0.5),
            ],
            widths=[1, 1],
            gap=1,
        )
        _items = [_controls]
        if clean_result_output is not None:
            _items.append(clean_result_output)
        _items.append(_maps)

        trips_tab_content = mo.vstack(_items, gap=1, align="stretch")
    return (trips_tab_content,)


@app.cell
def _(mo, selected_line_ids):
    _has_line = len(selected_line_ids) == 1
    validate_direction_btn = mo.ui.button(
        label="Validate directions",
        value=0,
        on_click=lambda v: (v or 0) + 1,
        kind="neutral",
        disabled=not _has_line,
    )
    direction_filter_dropdown = mo.ui.dropdown(
        options={"All trips": "all", "Forward only": "forward", "Reverse only": "reverse"},
        value="All trips",
        label="Direction filter",
    )
    return direction_filter_dropdown, validate_direction_btn


@app.cell
def _(
    db,
    mo,
    selected_line_ids,
    set_direction_result,
    validate_direction_btn,
    validate_trip_directions,
):
    validate_direction_output = None
    if (validate_direction_btn.value or 0) > 0 and len(selected_line_ids) == 1:
        try:
            _result = validate_trip_directions(
                db,
                selected_line_ids[0],
                20.0,
            )
            set_direction_result(_result)
            _msg = f"**{_result.n_forward}** forward · **{_result.n_reverse}** reverse · **{_result.n_unknown}** unknown"
            if _result.is_mixed:
                _msg += " — mixed directions detected, use direction filter below"
            validate_direction_output = mo.callout(
                mo.md(_msg), kind="warn" if _result.is_mixed else "success",
            )
        except Exception as _e:
            validate_direction_output = mo.callout(mo.md(f"Error: {_e}"), kind="danger")
    return (validate_direction_output,)


@app.cell
def _(Trip, db, get_direction_result, mo, pdk, select, to_shape):
    _dir_result = get_direction_result()
    if _dir_result is None or not _dir_result.trips:
        direction_map = mo.md("_Run **Validate directions** to see direction classification._")
    else:
        _COLOR_MAP = {
            "forward": [59, 130, 246, 180],
            "reverse": [239, 68, 68, 180],
            "unknown": [156, 163, 175, 140],
        }
        _layer_data = []
        _all_coords = []
        for _t in _dir_result.trips:
            _trip = db.execute(select(Trip).where(Trip.id == _t.trip_id)).scalars().first()
            if _trip is None or _trip.computed_path is None:
                continue
            try:
                _geom = to_shape(_trip.computed_path)
                _coords = [[c[0], c[1], 0] for c in _geom.coords]
                _layer_data.append({
                    "path": _coords,
                    "color": _COLOR_MAP[_t.direction.value],
                    "direction": _t.direction.value,
                    "dot_score": f"{_t.dot_score:.3f}",
                })
                _all_coords.extend(_coords)
            except Exception:
                pass
        if _all_coords:
            _lons = [c[0] for c in _all_coords]
            _lats = [c[1] for c in _all_coords]
            _center = pdk.ViewState(
                latitude=sum(_lats) / len(_lats), longitude=sum(_lons) / len(_lons),
                zoom=14, pitch=0,
            )
        else:
            _center = pdk.ViewState(latitude=-17.4, longitude=-66.1, zoom=13)
        _stats = mo.hstack(
            [
                mo.stat(_dir_result.n_forward, label="Forward", bordered=False),
                mo.stat(_dir_result.n_reverse, label="Reverse", bordered=False),
                mo.stat(_dir_result.n_unknown, label="Unknown", bordered=False),
                mo.stat("Yes" if _dir_result.is_mixed else "No", label="Mixed", bordered=False),
            ],
            gap=1, justify="start",
        )
        direction_map = mo.vstack(
            [
                _stats,
                pdk.Deck(
                    map_style="light", map_provider="carto",
                    initial_view_state=_center,
                    layers=[pdk.Layer(
                        "PathLayer", _layer_data,
                        get_path="path", get_color="color",
                        get_width=5, width_min_pixels=3,
                        pickable=True, auto_highlight=True,
                        highlight_color=[255, 255, 100, 255],
                    )],
                    height=350,
                    tooltip={
                        "html": "<b>Direction:</b> {direction}<br/><b>Dot score:</b> {dot_score}",
                        "style": {"backgroundColor": "white", "color": "black",
                                  "fontFamily": "ui-monospace, monospace",
                                  "border": "1px solid grey", "fontSize": "12px"},
                    },
                ),
            ],
            gap=0.5,
        )
    return (direction_map,)


@app.cell
def _(build_approach_selector, get_approaches):
    _approaches = get_approaches()
    approach_dropdown = build_approach_selector(_approaches)
    return (approach_dropdown,)


@app.cell
def _(approach_dropdown, build_param_panel, get_approach, mo):
    _key = approach_dropdown.value
    _info, _fn = get_approach(_key)
    param_panel = build_param_panel(_info.params)
    approach_description = mo.md(f"_{_info.description}_")
    return approach_description, param_panel


@app.cell
def _(mo, selected_line_ids):
    reconstruct_btn = mo.ui.button(
        label="Reconstruct route",
        value=0,
        on_click=lambda v: (v or 0) + 1,
        kind="neutral",
        disabled=len(selected_line_ids) != 1,
    )
    return (reconstruct_btn,)


@app.cell
def _(
    approach_dropdown,
    confidence_slider,
    db,
    direction_filter_dropdown,
    get_approach,
    get_direction_result,
    mo,
    param_panel,
    reconstruct_btn,
    resolve_params,
    selected_line_ids,
    set_preserved_line_ids,
    set_reconstruction_result,
    set_refresh,
):
    reconstruct_output = None
    if (reconstruct_btn.value or 0) > 0 and len(selected_line_ids) == 1:
        try:
            _key = approach_dropdown.value
            _info, _fn = get_approach(_key)

            # Collect approach-specific params
            _raw_params = dict(param_panel.value)
            _params = resolve_params(_info, _raw_params)

            # Direction filtering
            _trip_ids = None
            _dir_result = get_direction_result()
            if direction_filter_dropdown.value == "forward" and _dir_result is not None:
                _trip_ids = [t.trip_id for t in _dir_result.forward_trips]
            elif direction_filter_dropdown.value == "reverse" and _dir_result is not None:
                _trip_ids = [t.trip_id for t in _dir_result.reverse_trips]

            _min_score = confidence_slider.value if confidence_slider.value > 0 else None

            _result = _fn(
                db,
                selected_line_ids[0],
                min_match_score=_min_score,
                trip_ids=_trip_ids,
                **_params,
            )
            set_reconstruction_result(_result)
            set_preserved_line_ids(selected_line_ids)
            set_refresh(lambda v: v + 1)

            reconstruct_output = mo.callout(
                mo.md(f"**{_info.label}** produced **{_result.n_route_segments}** route segments (v{_result.estimation.version})"),
                kind="success",
            )
        except Exception as _e:
            db.rollback()
            reconstruct_output = mo.callout(mo.md(f"Error: {_e}"), kind="danger")
    return (reconstruct_output,)


@app.cell
def _(FilteredRouteResult, get_reconstruction_result, mo, pdk):
    _result = get_reconstruction_result()
    if not isinstance(_result, FilteredRouteResult) or not _result.cluster_segments:
        dbscan_diagnostics = None
    else:
        _CLUSTER_COLORS = [
            [59, 130, 246],   # blue
            [34, 197, 94],    # green
            [234, 179, 8],    # amber
            [168, 85, 247],   # violet
            [236, 72, 153],   # pink
            [20, 184, 166],   # teal
            [249, 115, 22],   # orange
            [139, 92, 246],   # purple
        ]
        _NOISE_COLOR = [156, 163, 175, 100]
        _SMALL_COLOR = [251, 191, 36, 120]

        _kept_data = []
        _discarded_data = []
        _all_coords = []
        for _seg in _result.cluster_segments:
            _path = [
                [_seg.start_lon, _seg.start_lat, 0],
                [_seg.end_lon, _seg.end_lat, 0],
            ]
            _all_coords.extend(_path)
            if _seg.cluster_label == -1:
                _discarded_data.append({
                    "path": _path,
                    "color": _NOISE_COLOR,
                    "cluster": "noise",
                    "status": "discarded",
                })
            elif _seg.kept:
                _rgb = _CLUSTER_COLORS[_seg.cluster_label % len(_CLUSTER_COLORS)]
                _kept_data.append({
                    "path": _path,
                    "color": [*_rgb, 200],
                    "cluster": str(_seg.cluster_label),
                    "status": "kept",
                })
            else:
                _discarded_data.append({
                    "path": _path,
                    "color": _SMALL_COLOR,
                    "cluster": str(_seg.cluster_label),
                    "status": "small cluster",
                })

        if _all_coords:
            _lons = [c[0] for c in _all_coords]
            _lats = [c[1] for c in _all_coords]
            _center = pdk.ViewState(
                latitude=sum(_lats) / len(_lats), longitude=sum(_lons) / len(_lons),
                zoom=14, pitch=0,
            )
        else:
            _center = pdk.ViewState(latitude=-17.4, longitude=-66.1, zoom=13)

        _layers = []
        if _discarded_data:
            _layers.append(pdk.Layer(
                "PathLayer", _discarded_data,
                get_path="path", get_color="color",
                get_width=3, width_min_pixels=1,
                pickable=True,
            ))
        if _kept_data:
            _layers.append(pdk.Layer(
                "PathLayer", _kept_data,
                get_path="path", get_color="color",
                get_width=5, width_min_pixels=3,
                pickable=True, auto_highlight=True,
                highlight_color=[255, 255, 100, 255],
            ))

        _stats = mo.hstack(
            [
                mo.stat(_result.n_kept_segments, label="Kept segs", bordered=False),
                mo.stat(_result.n_noise_segments, label="Noise segs", bordered=False),
                mo.stat(_result.n_clusters, label="Clusters", bordered=False),
                mo.stat(_result.n_small_clusters, label="Small clusters", bordered=False),
                mo.stat(_result.n_segments_total, label="Total segs", bordered=False),
            ],
            gap=1, justify="start",
        )
        dbscan_diagnostics = mo.vstack(
            [
                mo.md("**Cluster assignments**"),
                _stats,
                pdk.Deck(
                    map_style="light", map_provider="carto",
                    initial_view_state=_center,
                    layers=_layers,
                    height=400,
                    tooltip={
                        "html": "<b>Cluster:</b> {cluster}<br/><b>Status:</b> {status}",
                        "style": {"backgroundColor": "white", "color": "black",
                                  "fontFamily": "ui-monospace, monospace",
                                  "border": "1px solid grey", "fontSize": "12px"},
                    },
                ),
            ],
            gap=0.5,
        )
    return (dbscan_diagnostics,)


@app.cell
def _(ArmanTampereResult, get_reconstruction_result, mo):
    _result = get_reconstruction_result()
    if not isinstance(_result, ArmanTampereResult):
        arman_diagnostics = None
    else:
        _items = [mo.md("**Centerline construction**")]

        _stats = mo.hstack(
            [
                mo.stat(_result.segmentation.n_trajectories, label="Trajectories", bordered=False),
                mo.stat(_result.segmentation.n_bundles, label="Bundles", bordered=False),
                mo.stat(len(_result.segmentation.segments), label="Segments", bordered=False),
                mo.stat(len(_result.segmentation.nodes), label="Nodes", bordered=False),
            ],
            gap=1, justify="start",
        )
        _items.append(_stats)

        # Show centerline details per segment
        for i, cl in enumerate(_result.centerlines):
            _items.append(
                mo.hstack(
                    [
                        mo.stat(cl.n_trajectories_used, label=f"Seg {i} trajectories", bordered=False),
                        mo.stat(cl.n_outliers_removed, label="Outliers removed", bordered=False),
                        mo.stat(cl.n_pairs_selected, label="Pairs selected", bordered=False),
                        mo.stat(len(cl.points), label="Centerline pts", bordered=False),
                    ],
                    gap=1, justify="start",
                )
            )

        arman_diagnostics = mo.vstack(_items, gap=0.5)
    return (arman_diagnostics,)


@app.cell
def _(RouteSegment, db, get_reconstruction_result, mo, pdk, select, to_shape):
    _result = get_reconstruction_result()
    if _result is None:
        route_map = mo.md("_Run **Reconstruct route** to see the result._")
    else:
        _segments = db.execute(
            select(RouteSegment)
            .where(RouteSegment.estimation_id == _result.estimation.id)
            .order_by(RouteSegment.sequence)
        ).scalars().all()

        if not _segments:
            route_map = mo.md("_No segments found for this estimation._")
        else:
            _layer_data = []
            _all_coords = []
            for _seg in _segments:
                if _seg.path is None:
                    continue
                try:
                    _geom = to_shape(_seg.path)
                    _coords = [[c[0], c[1], 0] for c in _geom.coords]
                    _layer_data.append({
                        "path": _coords,
                        "color": [59, 130, 246, 200],
                        "sequence": _seg.sequence,
                    })
                    _all_coords.extend(_coords)
                except Exception:
                    pass

            if _all_coords:
                _lons = [c[0] for c in _all_coords]
                _lats = [c[1] for c in _all_coords]
                _center = pdk.ViewState(
                    latitude=sum(_lats) / len(_lats), longitude=sum(_lons) / len(_lons),
                    zoom=14, pitch=0,
                )
            else:
                _center = pdk.ViewState(latitude=-17.4, longitude=-66.1, zoom=13)

            _stats = mo.hstack(
                [
                    mo.stat(f"v{_result.estimation.version}", label="Version", bordered=False),
                    mo.stat(_result.n_route_segments, label="Segments", bordered=False),
                ],
                gap=1, justify="start",
            )
            route_map = mo.vstack(
                [
                    mo.md("**Reconstructed route**"),
                    _stats,
                    pdk.Deck(
                        map_style="light", map_provider="carto",
                        initial_view_state=_center,
                        layers=[pdk.Layer(
                            "PathLayer", _layer_data,
                            get_path="path", get_color="color",
                            get_width=7, width_min_pixels=4,
                            pickable=True, auto_highlight=True,
                            highlight_color=[255, 255, 100, 255],
                        )],
                        height=400,
                        tooltip={
                            "html": "<b>Segment:</b> {sequence}",
                            "style": {"backgroundColor": "white", "color": "black",
                                      "fontFamily": "ui-monospace, monospace",
                                      "border": "1px solid grey", "fontSize": "12px"},
                        },
                    ),
                ],
                gap=0.5,
            )
    return (route_map,)


@app.cell
def _(
    approach_description,
    approach_dropdown,
    arman_diagnostics,
    confidence_slider,
    dbscan_diagnostics,
    direction_filter_dropdown,
    direction_map,
    mo,
    param_panel,
    reconstruct_btn,
    reconstruct_output,
    route_map,
    selected_line_ids,
    validate_direction_btn,
    validate_direction_output,
):
    if not selected_line_ids:
        reconstruct_tab_content = mo.callout(
            mo.md("Select a line in the **Lines** tab to reconstruct its route."),
            kind="info",
        )
    elif len(selected_line_ids) != 1:
        reconstruct_tab_content = mo.callout(
            mo.md("Select exactly **one** line to reconstruct."),
            kind="info",
        )
    else:
        _items = []

        # Direction validation
        _items.append(
            mo.hstack(
                [mo.md("### Direction validation"), validate_direction_btn],
                gap=1, align="center",
            )
        )
        if validate_direction_output is not None:
            _items.append(validate_direction_output)
        _items.append(direction_map)

        # Approach selection + params
        _items.append(mo.md("---"))
        _items.append(mo.md("### Route reconstruction"))
        _items.append(
            mo.hstack(
                [approach_dropdown, direction_filter_dropdown, confidence_slider],
                gap=1, align="end",
            )
        )
        _items.append(approach_description)
        _items.append(param_panel)
        _items.append(
            mo.hstack([reconstruct_btn], justify="start")
        )

        # Results
        if reconstruct_output is not None:
            _items.append(reconstruct_output)
        if dbscan_diagnostics is not None:
            _items.append(dbscan_diagnostics)
        if arman_diagnostics is not None:
            _items.append(arman_diagnostics)
        _items.append(route_map)

        reconstruct_tab_content = mo.vstack(_items, gap=1, align="stretch")
    return (reconstruct_tab_content,)


@app.cell
def _(lines_tab_content, mo, reconstruct_tab_content, trips_tab_content):
    mo.ui.tabs(
        {
            "Lines": lines_tab_content,
            "Trips": trips_tab_content,
            "Reconstruct": reconstruct_tab_content,
        },
    )
    return


if __name__ == "__main__":
    app.run()
