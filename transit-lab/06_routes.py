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
    import marimo as mo
    import pandas as pd
    import pydeck as pdk
    from geoalchemy2.shape import to_shape
    from sqlalchemy import select

    from components.tracing import init_tracing
    from database.connection import SessionLocal
    from database.models.line import Line
    from database.models.route import Route, RouteEdge, RouteStatus

    return (
        Line,
        Route,
        RouteEdge,
        RouteStatus,
        SessionLocal,
        init_tracing,
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
    _lines = db.execute(select(Line).order_by(Line.name)).scalars().all()
    _lines_options = {f"{ln.name} — {ln.description or ''}".strip(" —"): str(ln.id) for ln in _lines}

    line_dropdown = mo.ui.dropdown(
        options=_lines_options,
        label="Line",
    )
    return (line_dropdown,)


@app.cell
def _(Route, RouteStatus, db, line_dropdown, mo, pd, select):
    if not line_dropdown.value:
        routes_table = None
        routes_df = pd.DataFrame()
    else:
        from uuid import UUID as _UUID

        _line_id = _UUID(line_dropdown.value)
        _routes = db.execute(
            select(Route)
            .where(Route.line_id == _line_id)
            .order_by(Route.version.desc())
        ).scalars().all()

        routes_df = pd.DataFrame(
            [
                {
                    "id": str(r.id),
                    "version": r.version,
                    "source": r.source.value,
                    "status": r.status.value,
                    "edges": len(r.edges),
                    "trip_count": r.trip_count,
                    "created_at": r.created_at,
                }
                for r in _routes
            ]
        )

        if routes_df.empty:
            routes_table = None
        else:
            routes_table = mo.ui.table(
                data=routes_df,
                label="Route versions (newest first)",
                pagination=False,
                selection="single",
            )

    return routes_df, routes_table


@app.cell
def _(
    RouteEdge,
    db,
    mo,
    pdk,
    routes_df,
    routes_table,
    select,
    to_shape,
):
    if routes_table is None:
        route_map = mo.md("_Select a line to see its route versions._")
    else:
        _sel = routes_table.value
        if _sel is not None and not _sel.empty and "id" in _sel.columns:
            from uuid import UUID as _UUID

            _route_id = _UUID(_sel["id"].iloc[0])
            _version = _sel["version"].iloc[0]
            _source = _sel["source"].iloc[0]
            _status = _sel["status"].iloc[0]
        elif not routes_df.empty:
            from uuid import UUID as _UUID

            _route_id = _UUID(routes_df["id"].iloc[0])
            _version = routes_df["version"].iloc[0]
            _source = routes_df["source"].iloc[0]
            _status = routes_df["status"].iloc[0]
        else:
            _route_id = None

        if _route_id is None:
            route_map = mo.md("_No routes found for this line._")
        else:
            _edges = db.execute(
                select(RouteEdge)
                .where(RouteEdge.route_id == _route_id)
                .order_by(RouteEdge.sequence)
            ).scalars().all()

            _path_data = []
            _all_coords = []

            for _edge in _edges:
                if _edge.path is not None:
                    try:
                        _geom = to_shape(_edge.path)
                        _coords = [[c[0], c[1], 0] for c in _geom.coords]
                        _conf = _edge.confidence
                        # Color by confidence: green (high) → red (low)
                        _r = int(255 * (1 - _conf))
                        _g = int(200 * _conf)
                        _b = 60
                        _path_data.append({
                            "path": _coords,
                            "color": [_r, _g, _b, 180],
                            "edge_id": _edge.valhalla_edge_id or "—",
                            "sequence": _edge.sequence,
                            "confidence": f"{_conf:.0%}",
                            "votes": f"+{_edge.votes_for} / -{_edge.votes_against}",
                        })
                        _all_coords.extend(_coords)
                    except Exception:
                        pass

            if _all_coords:
                _lons = [c[0] for c in _all_coords]
                _lats = [c[1] for c in _all_coords]
                _center_lat = sum(_lats) / len(_lats)
                _center_lon = sum(_lons) / len(_lons)
            else:
                _center_lat, _center_lon = -17.39, -66.16

            _layers = []
            if _path_data:
                _layers.append(
                    pdk.Layer(
                        "PathLayer",
                        _path_data,
                        get_path="path",
                        get_color="color",
                        get_width=6,
                        width_min_pixels=3,
                        pickable=True,
                        auto_highlight=True,
                        highlight_color=[255, 255, 100, 255],
                    )
                )

            _deck = pdk.Deck(
                map_style="light",
                map_provider="carto",
                initial_view_state=pdk.ViewState(
                    latitude=_center_lat,
                    longitude=_center_lon,
                    zoom=13,
                    pitch=0,
                    bearing=0,
                ),
                layers=_layers,
                height=500,
                tooltip={
                    "html": (
                        "<b>Edge:</b> {edge_id}<br/>"
                        "<b>Seq:</b> {sequence}<br/>"
                        "<b>Confidence:</b> {confidence}<br/>"
                        "<b>Votes:</b> {votes}"
                    ),
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
                    mo.stat(f"v{_version}", label="Version", bordered=False),
                    mo.stat(_source, label="Source", bordered=False),
                    mo.stat(_status, label="Status", bordered=False),
                    mo.stat(len(_edges), label="Edges", bordered=False),
                ],
                gap=1,
                justify="start",
            )

            route_map = mo.vstack([_stats, _deck], gap=0.5)

    return (route_map,)


@app.cell
def _(line_dropdown, mo, route_map, routes_table):
    _items = [
        mo.md("## Routes"),
        line_dropdown,
    ]
    if routes_table is not None:
        _items.append(routes_table)
    _items.append(route_map)

    mo.vstack(_items, gap=1, align="stretch")
    return


if __name__ == "__main__":
    app.run()
