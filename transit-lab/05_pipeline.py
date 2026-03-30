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
    import pydeck as pdk
    from geoalchemy2.shape import to_shape
    from sqlalchemy import select

    from components.tracing import init_tracing
    from database.connection import SessionLocal
    from database.models.line import Line, LineStatus
    from database.models.route import (
        EstimationStatus,
        ResampledTrip,
        RouteEstimation,
        RouteSegment,
        Trip,
    )
    from geodata.cluster import cluster_route
    from geodata.match import match_line
    from geodata.resample import resample_line
    from geodata.validate import validate_trip_directions

    return (
        EstimationStatus,
        Line,
        LineStatus,
        ResampledTrip,
        RouteEstimation,
        RouteSegment,
        SessionLocal,
        Trip,
        cluster_route,
        init_tracing,
        match_line,
        math,
        mo,
        pdk,
        resample_line,
        select,
        to_shape,
        validate_trip_directions,
    )


@app.cell
def _(SessionLocal, init_tracing, mo):
    db = SessionLocal()
    init_tracing()
    get_refresh, set_refresh = mo.state(0)
    get_pipeline_log, set_pipeline_log = mo.state([])
    return (
        db,
        get_pipeline_log,
        get_refresh,
        set_pipeline_log,
        set_pipeline_log,
        set_refresh,
    )


# ---------------------------------------------------------------------------
# Line selection
# ---------------------------------------------------------------------------


@app.cell
def _(Line, db, get_refresh, mo, select):
    _ = get_refresh()
    _all_lines = db.execute(select(Line).order_by(Line.name)).scalars().all()
    line_multiselect = mo.ui.multiselect(
        options={line.name: str(line.id) for line in _all_lines},
        label="Lines",
    )
    return (line_multiselect,)


@app.cell
def _(line_multiselect, mo):
    selected_line_ids_str = line_multiselect.value or []
    _hint = (
        mo.callout(mo.md("Select one or more lines to run the pipeline."), kind="info")
        if not selected_line_ids_str
        else mo.md(f"**{len(selected_line_ids_str)}** line(s) selected.")
    )
    return (selected_line_ids_str,)


# ---------------------------------------------------------------------------
# Pipeline parameters
# ---------------------------------------------------------------------------


@app.cell
def _(mo):
    interval_input = mo.ui.number(value=20, start=1, stop=500, step=1, label="Interval (m)")
    min_score_input = mo.ui.number(value=0.0, start=0.0, stop=1.0, step=0.05, label="Min score")
    eps_input = mo.ui.number(value=30, start=5, stop=200, step=5, label="ε DBSCAN (m)")
    min_samples_input = mo.ui.number(value=0, start=0, stop=50, step=1, label="Min samples (0=auto)")
    direction_filter = mo.ui.dropdown(
        options={"All trips": "all", "Forward only": "forward", "Reverse only": "reverse"},
        value="All trips",
        label="Direction filter",
    )
    run_match_switch = mo.ui.switch(value=True, label="HMM match")
    run_resample_switch = mo.ui.switch(value=True, label="Resample")
    run_cluster_switch = mo.ui.switch(value=True, label="Cluster")
    run_btn = mo.ui.button(
        label="Run pipeline",
        value=0,
        on_click=lambda v: (v or 0) + 1,
        kind="success",
    )
    return (
        direction_filter,
        eps_input,
        interval_input,
        min_samples_input,
        min_score_input,
        run_btn,
        run_cluster_switch,
        run_match_switch,
        run_resample_switch,
    )


# ---------------------------------------------------------------------------
# Pipeline execution
# ---------------------------------------------------------------------------


@app.cell
def _(
    cluster_route,
    db,
    direction_filter,
    eps_input,
    interval_input,
    match_line,
    min_samples_input,
    min_score_input,
    mo,
    resample_line,
    run_btn,
    run_cluster_switch,
    run_match_switch,
    run_resample_switch,
    selected_line_ids_str,
    set_pipeline_log,
    set_refresh,
    validate_trip_directions,
):
    from uuid import UUID

    pipeline_output = None

    if (run_btn.value or 0) > 0 and selected_line_ids_str:
        _interval = float(interval_input.value)
        _min_score = float(min_score_input.value)
        _eps = float(eps_input.value)
        _min_s = int(min_samples_input.value) or None
        _dir_filter = direction_filter.value

        _log: list[str] = []

        for _lid_str in selected_line_ids_str:
            _lid = UUID(_lid_str)
            _log.append(f"### Line `{_lid_str}`")

            # -- Step 1: HMM match --
            if run_match_switch.value:
                try:
                    _match_result = match_line(db, _lid)
                    _log.append(
                        f"- **Match**: {len(_match_result.matched)} matched, "
                        f"{len(_match_result.failed)} failed, "
                        f"{_match_result.skipped} skipped"
                    )
                except Exception as _e:
                    db.rollback()
                    _log.append(f"- **Match** ERROR: {_e}")
                    continue

            # -- Step 2: Resample --
            if run_resample_switch.value:
                try:
                    _res = resample_line(db, _lid, _interval, min_match_score=_min_score)
                    _log.append(
                        f"- **Resample** ({_interval} m, score≥{_min_score:.0%}): "
                        f"{len(_res.resampled)} resampled, "
                        f"{len(_res.skipped)} skipped, "
                        f"{len(_res.failed)} failed"
                    )
                except Exception as _e:
                    db.rollback()
                    _log.append(f"- **Resample** ERROR: {_e}")
                    continue

            # -- Step 3: Direction validation (always, to feed filter) --
            _dir_result = None
            try:
                _dir_result = validate_trip_directions(
                    db, _lid, _interval, min_match_score=_min_score if _min_score > 0 else None,
                )
                _mixed = " ⚠️ mixed" if _dir_result.is_mixed else ""
                _log.append(
                    f"- **Direction**: {_dir_result.n_forward} forward, "
                    f"{_dir_result.n_reverse} reverse, "
                    f"{_dir_result.n_unknown} unknown{_mixed}"
                )
            except Exception as _e:
                _log.append(f"- **Direction** ERROR: {_e}")

            # -- Step 4: DBSCAN cluster --
            if run_cluster_switch.value:
                _trip_ids = None
                if _dir_result is not None:
                    if _dir_filter == "forward":
                        _trip_ids = [t.resampled_trip_id for t in _dir_result.forward_trips]
                    elif _dir_filter == "reverse":
                        _trip_ids = [t.resampled_trip_id for t in _dir_result.reverse_trips]
                try:
                    _cr = cluster_route(
                        db, _lid, _interval,
                        min_match_score=_min_score if _min_score > 0 else None,
                        resampled_trip_ids=_trip_ids,
                        eps_meters=_eps,
                        min_samples=_min_s,
                    )
                    _log.append(
                        f"- **Cluster** (ε={_eps} m): "
                        f"{_cr.n_clusters} clusters → {_cr.n_segments} segments "
                        f"from {_cr.n_trips} trips, "
                        f"{_cr.n_noise_points} noise pts discarded"
                    )
                except Exception as _e:
                    db.rollback()
                    _log.append(f"- **Cluster** ERROR: {_e}")

        set_pipeline_log(_log)
        set_refresh(lambda v: v + 1)
        pipeline_output = mo.callout(
            mo.md(f"Pipeline finished for **{len(selected_line_ids_str)}** line(s)."),
            kind="success",
        )
    return (pipeline_output,)


# ---------------------------------------------------------------------------
# Pipeline log
# ---------------------------------------------------------------------------


@app.cell
def _(get_pipeline_log, mo):
    _log = get_pipeline_log()
    pipeline_log_output = (
        mo.md("\n\n".join(_log))
        if _log
        else mo.md("_No pipeline run yet._")
    )
    return (pipeline_log_output,)


# ---------------------------------------------------------------------------
# Combined route map (all selected lines, latest estimation)
# ---------------------------------------------------------------------------


@app.cell
def _(
    EstimationStatus,
    RouteEstimation,
    RouteSegment,
    db,
    get_refresh,
    math,
    mo,
    pdk,
    select,
    selected_line_ids_str,
    to_shape,
):
    from uuid import UUID as _UUID

    _ = get_refresh()

    _LINE_COLORS = [
        [59, 130, 246],
        [34, 197, 94],
        [234, 179, 8],
        [168, 85, 247],
        [236, 72, 153],
        [20, 184, 166],
        [239, 68, 68],
        [251, 146, 60],
    ]

    def _haversine_m(lon1, lat1, lon2, lat2):
        R = 6_371_000
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    if not selected_line_ids_str:
        combined_route_map = mo.md("_Select lines and run the pipeline to see routes here._")
    else:
        _layer_data = []
        _all_coords = []
        _route_stats = []

        for _i, _lid_str in enumerate(selected_line_ids_str):
            _lid = _UUID(_lid_str)
            _color = _LINE_COLORS[_i % len(_LINE_COLORS)]

            _est = db.execute(
                select(RouteEstimation)
                .where(
                    RouteEstimation.line_id == _lid,
                    RouteEstimation.status != EstimationStatus.SUPERSEDED,
                )
                .order_by(RouteEstimation.version.desc())
            ).scalars().first()

            if _est is None:
                continue

            _segs = db.execute(
                select(RouteSegment)
                .where(RouteSegment.estimation_id == _est.id)
                .order_by(RouteSegment.sequence)
            ).scalars().all()

            _total_dist = 0.0
            for _seg in _segs:
                if _seg.path is None:
                    continue
                try:
                    _geom = to_shape(_seg.path)
                    _coords = [[c[0], c[1], 0] for c in _geom.coords]
                    _layer_data.append({
                        "path": _coords,
                        "color": [*_color, 200],
                        "line": _lid_str[:8],
                        "confidence": f"{_seg.confidence:.0%}",
                        "sequence": _seg.sequence,
                    })
                    _all_coords.extend(_coords)
                    if len(_coords) >= 2:
                        _total_dist += _haversine_m(*_coords[0][:2], *_coords[-1][:2])
                except Exception:
                    pass

            _km = _total_dist / 1000
            _route_stats.append(
                mo.stat(
                    f"{_km:.1f} km" if _km >= 0.1 else f"{int(_total_dist)} m",
                    label=f"v{_est.version} · {len(_segs)} segs",
                    bordered=True,
                )
            )

        if _all_coords:
            _lons = [c[0] for c in _all_coords]
            _lats = [c[1] for c in _all_coords]
            _center = pdk.ViewState(
                latitude=sum(_lats) / len(_lats), longitude=sum(_lons) / len(_lons),
                zoom=13, pitch=0,
            )
        else:
            _center = pdk.ViewState(latitude=-17.4, longitude=-66.1, zoom=13)

        if _layer_data:
            _deck = pdk.Deck(
                map_style="light", map_provider="carto",
                initial_view_state=_center,
                layers=[pdk.Layer(
                    "PathLayer", _layer_data,
                    get_path="path", get_color="color",
                    get_width=7, width_min_pixels=4,
                    pickable=True, auto_highlight=True,
                    highlight_color=[255, 255, 100, 255],
                )],
                height=500,
                tooltip={
                    "html": "<b>Line:</b> {line}…<br/><b>Segment:</b> {sequence}<br/><b>Confidence:</b> {confidence}",
                    "style": {"backgroundColor": "white", "color": "black",
                              "fontFamily": "ui-monospace, monospace",
                              "border": "1px solid grey", "fontSize": "12px"},
                },
            )
            _stat_row = mo.hstack(_route_stats, gap=1, justify="start") if _route_stats else None
            combined_route_map = mo.vstack(
                [x for x in [_stat_row, _deck] if x is not None],
                gap=0.5,
            )
        else:
            combined_route_map = mo.md("_No route estimations found for selected lines. Run the pipeline first._")
    return (combined_route_map,)


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------


@app.cell
def _(
    combined_route_map,
    direction_filter,
    eps_input,
    interval_input,
    line_multiselect,
    min_samples_input,
    min_score_input,
    mo,
    pipeline_log_output,
    pipeline_output,
    run_btn,
    run_cluster_switch,
    run_match_switch,
    run_resample_switch,
    selected_line_ids_str,
):
    _items = [
        mo.md("## Pipeline runner"),
        mo.hstack(
            [line_multiselect],
            gap=1, align="end",
        ),
        mo.hstack(
            [
                mo.md("**Steps:**"),
                run_match_switch,
                run_resample_switch,
                run_cluster_switch,
            ],
            gap=1, align="center",
        ),
        mo.hstack(
            [
                mo.md("**Parameters:**"),
                interval_input,
                min_score_input,
                eps_input,
                min_samples_input,
                direction_filter,
            ],
            gap=1, align="end",
        ),
        run_btn,
    ]

    if pipeline_output is not None:
        _items.append(pipeline_output)

    if selected_line_ids_str:
        _items.append(mo.md("---"))
        _items.append(mo.md("### Pipeline log"))
        _items.append(pipeline_log_output)
        _items.append(mo.md("---"))
        _items.append(mo.md("### Reconstructed routes"))
        _items.append(combined_route_map)

    (
        mo.vstack(_items, gap=1, align="stretch")
        .style(style={"max-width": "100%"}, overflow_x="auto")
    )
    return


if __name__ == "__main__":
    app.run()
