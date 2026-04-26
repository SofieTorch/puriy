import marimo

__generated_with = "0.20.4"
app = marimo.App(width="full")


@app.cell
def _():
    import marimo as mo
    from components.navbar import navbar

    return mo, navbar


@app.cell
def _(navbar):
    navbar()
    return


@app.cell
def _():
    from database.connection import SessionLocal
    from components.tracing import init_tracing

    db = SessionLocal()
    init_tracing()
    return (db,)


@app.cell
def _(db, mo):
    from components.data import load_lines

    _lines = load_lines(db)
    _options = {row["name"]: row["id"] for row in _lines}
    line_selector = mo.ui.dropdown(options=_options, label="Line")
    line_selector
    return (line_selector,)


@app.cell
def _(mo):
    from geodata.reconstruction import get_reconstruction_strategies as _get_reconstruction_strategies

    _strategies = _get_reconstruction_strategies()
    _options = {s.label: key for key, s in _strategies.items()}

    strategy_selector = mo.ui.dropdown(options=_options, label="Strategy")
    strategy_selector
    return (strategy_selector,)


@app.cell
def _(strategy_selector, mo):
    from geodata.reconstruction import get_reconstruction_strategies as _get_reconstruction_strategies

    mo.stop(not strategy_selector.value)

    _strategies = _get_reconstruction_strategies()
    _strategy = _strategies[strategy_selector.value]
    _defaults = _strategy.default_params()

    # Auto-generate parameter UI from strategy defaults
    _widgets = {}
    for key, value in _defaults.items():
        if isinstance(value, bool):
            _widgets[key] = mo.ui.switch(value=value, label=key)
        elif isinstance(value, int):
            _widgets[key] = mo.ui.number(value=value, label=key, step=1)
        elif isinstance(value, float):
            _step = 0.01 if value < 1 else 0.1 if value < 10 else 1.0
            _widgets[key] = mo.ui.number(value=value, label=key, step=_step)
        elif isinstance(value, str):
            _widgets[key] = mo.ui.text(value=value, label=key)

    params_form = mo.ui.dictionary(_widgets)
    mo.vstack([mo.md("### Parameters"), params_form])
    return (params_form,)


@app.cell
def _(mo):
    run_button = mo.ui.run_button(label="Run reconstruction")
    show_traces = mo.ui.switch(value=True, label="Show input traces")
    mo.hstack([run_button, show_traces], gap=2, align="end")
    return run_button, show_traces


@app.cell
def _(line_selector, db):
    from uuid import UUID as _UUID
    from geodata.evaluate import load_reconstruction_traces_from_db

    _line_id = line_selector.value
    traces = (
        load_reconstruction_traces_from_db(line_id=_UUID(_line_id), trace_source="cleaned")
        if _line_id
        else []
    )
    return (traces,)


@app.cell
def _(run_button, strategy_selector, line_selector, params_form, traces, mo):
    from uuid import UUID as _UUID
    from geodata.reconstruction import get_reconstruction_strategies as _get_reconstruction_strategies

    mo.stop(not run_button.value)
    mo.stop(not strategy_selector.value)
    mo.stop(not line_selector.value)
    mo.stop(not traces, mo.md("**No cleaned traces available for this line.**"))

    _strategies = _get_reconstruction_strategies()
    _strategy = _strategies[strategy_selector.value]

    _params = {k: w.value for k, w in params_form.items()} if params_form else {}

    reconstruction_result = _strategy.reconstruct(
        _UUID(line_selector.value),
        traces,
        _params,
    )
    reconstruction_result
    return (reconstruction_result,)


@app.cell
def _(reconstruction_result, show_traces, traces, mo):
    from components.maps import path_layer, scatter_layer, deck, default_view_state

    _features = reconstruction_result.geojson.get("features", [])
    mo.stop(not _features, mo.md("*No features in reconstruction result.*"))

    def _gradient_color(_t: float) -> list[int]:
        """Blue (0.0) → Cyan → Green → Yellow → Red (1.0)."""
        if _t < 0.25:
            _f = _t / 0.25
            return [0, int(255 * _f), 255, 220]
        elif _t < 0.5:
            _f = (_t - 0.25) / 0.25
            return [0, 255, int(255 * (1 - _f)), 220]
        elif _t < 0.75:
            _f = (_t - 0.5) / 0.25
            return [int(255 * _f), 255, 0, 220]
        else:
            _f = (_t - 0.75) / 0.25
            return [255, int(255 * (1 - _f)), 0, 220]

    layers = []

    # Input traces first (behind the route)
    if show_traces.value and traces:
        _trace_paths = []
        for _trace in traces:
            _pts = [[p.longitude, p.latitude] for p in _trace.points]
            if len(_pts) >= 2:
                _trace_paths.append({"path": _pts, "color": [160, 160, 160, 70], "name": "trace"})
        if _trace_paths:
            layers.append(path_layer(_trace_paths, id="traces", width=2, opacity=0.3))

    # Route segments with gradient coloring + junction dots
    _segment_size = 5
    _all_junctions = []

    for _frag_idx, _feature in enumerate(_features):
        _coords = _feature.get("geometry", {}).get("coordinates", [])
        if len(_coords) < 2:
            continue

        _n_segments = max(1, (len(_coords) - 1) // _segment_size)
        _segment_paths = []

        for _s in range(_n_segments):
            _start = _s * _segment_size
            _end = min(_start + _segment_size + 1, len(_coords))
            _seg_coords = _coords[_start:_end]
            if len(_seg_coords) < 2:
                continue

            _t = _s / max(_n_segments - 1, 1)
            _color = _gradient_color(_t)
            _segment_paths.append({
                "path": _seg_coords,
                "color": _color,
                "name": f"Segment {_s + 1}/{_n_segments}",
            })

            # Junction point at the start of each segment (except first)
            if _s > 0:
                _all_junctions.append({
                    "position": _seg_coords[0],
                    "color": [40, 40, 40, 200],
                })

        if _segment_paths:
            layers.append(path_layer(_segment_paths, id=f"route-{_frag_idx}", width=5))

    if _all_junctions:
        layers.append(scatter_layer(_all_junctions, id="junctions", radius=20))

    _first_coords = _features[0]["geometry"]["coordinates"]
    _mid = len(_first_coords) // 2
    _view = default_view_state(lat=_first_coords[_mid][1], lon=_first_coords[_mid][0], zoom=14)

    result_map = deck(
        layers,
        view_state=_view,
        height=500,
        tooltip_html="<b>{name}</b>",
    )
    result_map
    return


@app.cell
def _(reconstruction_result, mo):
    diag = reconstruction_result.diagnostics
    rows = [{"metric": k, "value": str(v)} for k, v in diag.items()]
    table = mo.ui.table(rows, selection=None, label="Diagnostics")
    mo.vstack([
        mo.md(f"### Diagnostics — {reconstruction_result.strategy_name}"),
        table,
    ])
    return


@app.cell
def _(line_selector, reconstruction_result, strategy_selector, db, mo):
    save_button = mo.ui.run_button(label="Save to database")
    save_button
    return (save_button,)


@app.cell
def _(save_button, reconstruction_result, line_selector, strategy_selector, db, traces, mo):
    from uuid import UUID as _UUID
    from sqlalchemy import select as _select
    from database.models import Route as _Route, RouteSource as _RouteSource, RouteStatus as _RouteStatus, RouteEdge as _RouteEdge
    from geodata.match import trace_match as _trace_match
    from geoalchemy2.shape import from_shape as _from_shape
    from shapely.geometry import LineString as _LineString

    mo.stop(not save_button.value)

    _line_id = _UUID(line_selector.value)
    _features = reconstruction_result.geojson.get("features", [])
    mo.stop(not _features, mo.md("**Nothing to save.**"))

    max_version = db.execute(
        _select(_Route.version)
        .where(_Route.line_id == _line_id)
        .order_by(_Route.version.desc())
    ).scalars().first()
    next_version = (max_version or 0) + 1
    fragment_count = len(_features)
    saved_routes = []

    for _frag_idx, _feature in enumerate(_features):
        _coords = _feature.get("geometry", {}).get("coordinates", [])
        if len(_coords) < 2:
            continue

        shape = [{"lat": lat, "lon": lon} for lon, lat in _coords]
        matched = _trace_match(shape, costing="bus", search_radius=60, gps_accuracy=20)
        if not matched.edges:
            continue

        route = _Route(
            line_id=_line_id,
            version=next_version,
            source=_RouteSource.COMPUTED,
            strategy_key=strategy_selector.value,
            status=_RouteStatus.PENDING,
            trip_count=len(traces),
            fragment_index=_frag_idx,
            fragment_count=fragment_count,
        )
        db.add(route)
        db.flush()

        for seq, edge in enumerate(matched.edges):
            begin_idx = edge.get("begin_shape_index", 0)
            end_idx = edge.get("end_shape_index", begin_idx)
            edge_coords = matched.shape_coords[begin_idx : end_idx + 1]
            if len(edge_coords) < 2:
                continue
            edge_ls = _LineString([(lon, lat) for lat, lon in edge_coords])
            db.add(
                _RouteEdge(
                    route_id=route.id,
                    sequence=seq,
                    valhalla_edge_id=edge.get("id"),
                    forward=edge.get("forward", True),
                    path=_from_shape(edge_ls, srid=4326),
                    confidence=1.0,
                )
            )
        saved_routes.append(route)

    db.commit()
    mo.md(f"Saved **{len(saved_routes)}** route fragment(s) as version **{next_version}** with strategy `{strategy_selector.value}`.")
    return


if __name__ == "__main__":
    app.run()
