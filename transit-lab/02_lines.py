import marimo

__generated_with = "0.20.4"
app = marimo.App(width="medium")


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

    from components.tracing import init_tracing
    from database.connection import SessionLocal
    from database.models.line import Line, LineStatus
    from database.models.trip import TripSession
    from database.models.route import Trip, EstimationStatus, RouteEstimation, RouteSegment
    from geodata.cluster import filter_cluster_route
    from geodata.match import match_line
    from geodata.merge import merge_lines
    from geodata.validate import validate_trip_directions

    return (
        Line,
        LineStatus,
        RouteSegment,
        SessionLocal,
        Trip,
        TripSession,
        filter_cluster_route,
        init_tracing,
        match_line,
        math,
        merge_lines,
        mo,
        pd,
        pdk,
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
    get_filter_result, set_filter_result = mo.state(None)
    return (
        db,
        get_direction_result,
        get_filter_result,
        get_preserved_line_ids,
        get_refresh,
        set_direction_result,
        set_filter_result,
        set_preserved_line_ids,
        set_refresh,
    )


@app.cell
def _(merge_btn, mo):
    table_header = mo.hstack(
        [mo.md("**Lines**"), merge_btn],
        justify="space-between",
        align="center",
    )

    table_header
    return


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

    lines_table
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
def _(mo):
    view_3d_switch = mo.ui.switch(value=False, label="3D view")
    color_switch = mo.ui.switch(value=True, label="Colors")
    confidence_slider = mo.ui.number(
        value=0.0, start=0.0, stop=1.0, step=0.05, label="Min confidence",
    )
    return color_switch, confidence_slider, view_3d_switch


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

    create_section
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

    mo.plain(create_result_output)
    return


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
def _(mo, sessions_map, trips_map):
    mo.hstack(
        [
            mo.vstack([mo.md("**Raw sessions**"), sessions_map], gap=0.5),
            mo.vstack([mo.md("**Cleaned trips**"), trips_map], gap=0.5),
        ],
        widths=[1, 1],
        gap=1,
    )
    return


@app.cell
def _(clean_btn, color_switch, confidence_slider, mo, view_3d_switch):
    mo.hstack(
        [mo.md("**Maps**"), clean_btn, confidence_slider, color_switch, view_3d_switch],
        justify="space-between",
        align="center",
    )
    return


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

    if clean_result_output is not None:
        mo.plain(clean_result_output)
    return


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
    eps_input = mo.ui.number(value=30, start=5, stop=200, step=5, label="ε (m)")
    min_samples_input = mo.ui.number(value=0, start=0, stop=50, step=1, label="Min samples (0=auto)")
    direction_filter_dropdown = mo.ui.dropdown(
        options={"All trips": "all", "Forward only": "forward", "Reverse only": "reverse"},
        value="All trips",
        label="Direction filter",
    )
    min_cluster_segs_input = mo.ui.number(
        value=0, start=0, stop=200, step=1, label="Min cluster segs",
    )
    filter_btn = mo.ui.button(
        label="Cluster & filter",
        value=0,
        on_click=lambda v: (v or 0) + 1,
        kind="neutral",
        disabled=not _has_line,
    )
    return (
        direction_filter_dropdown,
        eps_input,
        filter_btn,
        min_cluster_segs_input,
        min_samples_input,
        validate_direction_btn,
    )


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
                _msg += " — ⚠️ mixed directions detected, use direction filter below"
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
                mo.stat("Yes ⚠️" if _dir_result.is_mixed else "No", label="Mixed", bordered=False),
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
def _(
    confidence_slider,
    db,
    direction_filter_dropdown,
    eps_input,
    filter_btn,
    filter_cluster_route,
    get_direction_result,
    min_cluster_segs_input,
    min_samples_input,
    mo,
    selected_line_ids,
    set_filter_result,
    set_preserved_line_ids,
    set_refresh,
):
    filter_result_output = None
    if (filter_btn.value or 0) > 0 and len(selected_line_ids) == 1:
        try:
            _eps = float(eps_input.value)
            _min_s = int(min_samples_input.value) or None
            _min_cs = int(min_cluster_segs_input.value)
            _min_score = confidence_slider.value if confidence_slider.value > 0 else None
            _trip_ids = None
            _dir_result = get_direction_result()
            if direction_filter_dropdown.value == "forward" and _dir_result is not None:
                _trip_ids = [t.trip_id for t in _dir_result.forward_trips]
            elif direction_filter_dropdown.value == "reverse" and _dir_result is not None:
                _trip_ids = [t.trip_id for t in _dir_result.reverse_trips]
            _result = filter_cluster_route(
                db,
                selected_line_ids[0],
                min_match_score=_min_score,
                trip_ids=_trip_ids,
                eps_meters=_eps,
                min_samples=_min_s,
                min_cluster_segments=_min_cs,
            )
            set_filter_result(_result)
            set_preserved_line_ids(selected_line_ids)
            set_refresh(lambda v: v + 1)
            _msg = (
                f"**{_result.n_kept_segments}** segments kept"
                f" from **{_result.n_clusters}** clusters"
                f" → **{_result.n_route_segments}** route segments"
                f" · {_result.n_noise_segments} noise + {_result.n_small_clusters} small clusters removed"
            )
            filter_result_output = mo.callout(mo.md(_msg), kind="success")
        except Exception as _e:
            db.rollback()
            filter_result_output = mo.callout(mo.md(f"Error: {_e}"), kind="danger")
    return (filter_result_output,)


@app.cell
def _(get_filter_result, mo, pdk):
    _fr = get_filter_result()
    if _fr is None or not _fr.cluster_segments:
        filter_clusters_map = mo.md("_Run **Cluster & filter** to see segment cluster assignments._")
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
        for _seg in _fr.cluster_segments:
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
                mo.stat(_fr.n_kept_segments, label="Kept segs", bordered=False),
                mo.stat(_fr.n_noise_segments, label="Noise segs", bordered=False),
                mo.stat(_fr.n_clusters, label="Clusters", bordered=False),
                mo.stat(_fr.n_small_clusters, label="Small clusters", bordered=False),
                mo.stat(_fr.n_segments_total, label="Total segs", bordered=False),
            ],
            gap=1, justify="start",
        )
        filter_clusters_map = mo.vstack(
            [
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
    return (filter_clusters_map,)


@app.cell
def _(RouteSegment, db, get_filter_result, mo, pdk, select, to_shape):
    _fr = get_filter_result()
    if _fr is None:
        filtered_route_map = mo.md("_Run **Filter route** to see the filtered route._")
    else:
        _segments = db.execute(
            select(RouteSegment)
            .where(RouteSegment.estimation_id == _fr.estimation.id)
            .order_by(RouteSegment.sequence)
        ).scalars().all()

        if not _segments:
            filtered_route_map = mo.md("_No segments found for this estimation._")
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
                    mo.stat(f"v{_fr.estimation.version}", label="Version", bordered=False),
                    mo.stat(_fr.n_kept_segments, label="Kept segs", bordered=False),
                    mo.stat(len(_segments), label="Segments", bordered=False),
                    mo.stat(_fr.n_trips, label="Trips", bordered=False),
                ],
                gap=1, justify="start",
            )
            filtered_route_map = mo.vstack(
                [
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
    return (filtered_route_map,)


@app.cell
def _(
    direction_filter_dropdown,
    direction_map,
    eps_input,
    filter_btn,
    filter_clusters_map,
    filter_result_output,
    filtered_route_map,
    min_cluster_segs_input,
    min_samples_input,
    mo,
    selected_line_ids,
    validate_direction_btn,
    validate_direction_output,
):
    _items = []

    if not selected_line_ids:
        _items.append(mo.callout(mo.md("Select a line to see its trips."), kind="info"))
    else:
        # ---- Direction + clustering ----
        _items.append(mo.md("---"))
        _items.append(
            mo.hstack(
                [
                    mo.md("**Direction & Clustering**"),
                    validate_direction_btn,
                    eps_input,
                    min_samples_input,
                    direction_filter_dropdown,
                    min_cluster_segs_input,
                    filter_btn,
                ],
                gap=1,
                align="end",
            )
        )
        if validate_direction_output is not None:
            _items.append(validate_direction_output)
        _items.append(mo.vstack([mo.md("**Direction classification**"), direction_map], gap=0.5))
        if filter_result_output is not None:
            _items.append(filter_result_output)
        _items.append(mo.vstack([mo.md("**Clustered segments**"), filter_clusters_map], gap=0.5))
        _items.append(mo.vstack([mo.md("**Reconstructed route**"), filtered_route_map], gap=0.5))

    (
        mo.vstack(_items, gap=1, align="stretch")
        .style(style={"max-width": "100%"}, overflow_x="auto")
    )
    return


if __name__ == "__main__":
    app.run()
