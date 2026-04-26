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
    from geodata.match import trace_match as _trace_match
    from components.maps import path_layer, scatter_layer, deck, default_view_state

    _BLUE = [59, 130, 246, 220]
    _LIGHT_BLUE = [147, 197, 253, 220]

    _features = reconstruction_result.geojson.get("features", [])
    mo.stop(not _features, mo.md("*No features in reconstruction result.*"))

    layers = []

    # Input traces (gray) + edge intersection dots from traces
    _edge_junction_points = []
    if show_traces.value and traces:
        _trace_paths = []
        for _trace in traces:
            _pts = [[p.longitude, p.latitude] for p in _trace.points]
            if len(_pts) < 2:
                continue
            _trace_paths.append({"path": _pts, "color": [140, 140, 140, 140], "name": f"trace {_trace.trace_id[:8]}"})

            # Edge intersection dots: where matched edges meet along this trace
            if _trace.matched_edges and len(_trace.matched_edges) > 1:
                _sorted_edges = sorted(_trace.matched_edges, key=lambda e: e.sequence)
                _n_edges = len(_sorted_edges)
                _n_pts = len(_pts)
                # Approximate edge boundary positions along the trace points
                for _ei in range(1, _n_edges):
                    _pt_idx = min(int(_ei / _n_edges * _n_pts), _n_pts - 1)
                    _edge_junction_points.append({
                        "position": _pts[_pt_idx],
                        "color": [255, 140, 0, 180],
                    })

        if _trace_paths:
            layers.append(path_layer(_trace_paths, id="traces", width=2, opacity=0.5))

    if _edge_junction_points:
        layers.append(scatter_layer(_edge_junction_points, id="trace-junctions", radius=15))

    # Reconstructed route: trace_match to get per-edge geometry, alternating blue/light blue
    _all_coords = []
    for _feature in _features:
        _coords = _feature.get("geometry", {}).get("coordinates", [])
        if _all_coords and _coords:
            _all_coords.extend(_coords[1:])
        else:
            _all_coords.extend(_coords)

    if len(_all_coords) >= 2:
        _shape = [{"lat": _c[1], "lon": _c[0]} for _c in _all_coords]
        _matched = _trace_match(_shape, costing="bus", search_radius=60, gps_accuracy=20)

        if _matched.edges:
            _edge_paths = []
            _route_junctions = []
            for _ei, _edge in enumerate(_matched.edges):
                _begin = _edge.get("begin_shape_index", 0)
                _end = _edge.get("end_shape_index", _begin)
                _seg = _matched.shape_coords[_begin : _end + 1]
                if len(_seg) < 2:
                    continue
                _seg_lonlat = [[_lon, _lat] for _lat, _lon in _seg]
                _color = _BLUE if _ei % 2 == 0 else _LIGHT_BLUE
                _edge_paths.append({
                    "path": _seg_lonlat,
                    "color": _color,
                    "name": f"Edge {_ei} ({_edge.get('id', '?')})",
                })
                # Junction dot between consecutive edges
                if _ei > 0:
                    _route_junctions.append({
                        "position": _seg_lonlat[0],
                        "color": [30, 30, 30, 200],
                    })

            layers.append(path_layer(_edge_paths, id="route-edges", width=5))
            if _route_junctions:
                layers.append(scatter_layer(_route_junctions, id="route-junctions", radius=10))
        else:
            # Fallback: solid line if trace_match returned no edges
            layers.append(
                path_layer(
                    [{"path": _all_coords, "color": _BLUE, "name": "Reconstructed route"}],
                    id="route-fallback",
                    width=5,
                )
            )

    _mid = len(_all_coords) // 2
    _view = default_view_state(lat=_all_coords[_mid][1], lon=_all_coords[_mid][0], zoom=14)

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
