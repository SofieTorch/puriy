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

    db = SessionLocal()
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
def _(line_selector, db, mo):
    from uuid import UUID as _UUID
    from components.data import load_route_info

    mo.stop(not line_selector.value)

    routes_data = load_route_info(db, _UUID(line_selector.value))
    mo.stop(not routes_data, mo.md("*No routes for this line.*"))

    display_rows = [
        {
            "version": r["version"],
            "fragment": f"{r['fragment_index']}/{r['fragment_count']}",
            "source": r["source"],
            "strategy": r["strategy_key"] or "—",
            "status": r["status"],
            "edges": r["edge_count"],
            "trips": r["trip_count"],
            "created": r["created_at"][:16],
        }
        for r in routes_data
    ]
    routes_table = mo.ui.table(display_rows, selection="single", label="Route versions")
    routes_table
    return routes_data, routes_table


@app.cell
def _(line_selector, routes_data, routes_table, db, mo):
    from uuid import UUID as _UUID
    from components.data import load_route_edges
    from components.maps import path_layer, scatter_layer, deck, default_view_state
    from components.style import confidence_color, darken

    mo.stop(not line_selector.value)

    # Pick the route version selected in the table; otherwise default to the
    # newest non-superseded route (what load_route_edges returns by default).
    _selected_rows = routes_table.value if routes_table is not None else None
    _selected_route_id = None
    if _selected_rows:
        _sel = _selected_rows[0]
        _matches = [
            r for r in routes_data
            if r["version"] == _sel["version"]
            and r["fragment_index"] == int(_sel["fragment"].split("/")[0])
        ]
        if _matches:
            _selected_route_id = _UUID(_matches[0]["id"])

    edges = load_route_edges(
        db, _UUID(line_selector.value), route_id=_selected_route_id
    )
    mo.stop(not edges, mo.md("*No edges for the selected route.*"))

    edge_paths = []
    junction_dots = []
    for _i, edge in enumerate(edges):
        if not edge["path"] or len(edge["path"]) < 2:
            continue
        color = confidence_color(edge["confidence"])
        edge_paths.append({
            "path": edge["path"],
            "color": color,
            "name": f"Edge {edge['sequence']} (conf: {edge['confidence']:.2f}, +{edge['votes_for']}/-{edge['votes_against']})",
        })
        # Junction dot at the start of every edge (= joint with previous edge,
        # or the route's start). Color = darker variant of this edge's color.
        dot_color = darken(color)
        dot_color[3] = 230  # mostly opaque
        junction_dots.append({
            "position": [edge["path"][0][0], edge["path"][0][1]],
            "color": dot_color,
            "name": f"Joint @ edge {edge['sequence']} (conf: {edge['confidence']:.2f})",
        })
    # Closing dot at the very end of the route.
    if edges and edges[-1]["path"] and len(edges[-1]["path"]) >= 2:
        _last_color = confidence_color(edges[-1]["confidence"])
        _end_color = darken(_last_color)
        _end_color[3] = 230
        junction_dots.append({
            "position": [edges[-1]["path"][-1][0], edges[-1]["path"][-1][1]],
            "color": _end_color,
            "name": f"Route end (edge {edges[-1]['sequence']})",
        })

    _view = default_view_state()
    if edge_paths and edge_paths[0]["path"]:
        mid = len(edge_paths[0]["path"]) // 2
        _view = default_view_state(
            lat=edge_paths[0]["path"][mid][1],
            lon=edge_paths[0]["path"][mid][0],
            zoom=14,
        )

    _layers = []
    if edge_paths:
        _layers.append(path_layer(edge_paths, id="edges", width=5))
    if junction_dots:
        _layers.append(scatter_layer(junction_dots, id="junctions", radius=8))

    route_map = deck(
        _layers,
        view_state=_view,
        height=500,
        tooltip_html="<b>{name}</b>",
    )
    mo.vstack([mo.md("### Route edges (colored by confidence)"), route_map])
    return (edges,)


@app.cell
def _(edges, mo):
    display_edges = [
        {
            "seq": e["sequence"],
            "edge_id": e["valhalla_edge_id"] or "—",
            "fwd": "→" if e["forward"] else "←",
            "confidence": f"{e['confidence']:.2f}",
            "votes_for": e["votes_for"],
            "votes_against": e["votes_against"],
            "status": e["status"],
        }
        for e in edges
    ]
    edge_table = mo.ui.table(display_edges, selection=None, label="Edge details")
    edge_table
    return


@app.cell
def _(edges, mo):
    no_votes = [e for e in edges if e["votes_for"] + e["votes_against"] == 0]
    disputed = sorted(
        [e for e in edges if e["votes_against"] > 0],
        key=lambda e: e["votes_against"],
        reverse=True,
    )[:10]

    analysis_items = [
        mo.stat(label="Total edges", value=str(len(edges))),
        mo.stat(label="No votes", value=str(len(no_votes))),
        mo.stat(label="Disputed edges", value=str(len(disputed))),
    ]

    disputed_rows = [
        {
            "seq": e["sequence"],
            "edge_id": e["valhalla_edge_id"] or "—",
            "for": e["votes_for"],
            "against": e["votes_against"],
            "ratio": f"{e['votes_for'] / (e['votes_for'] + e['votes_against']):.0%}" if e["votes_for"] + e["votes_against"] > 0 else "—",
        }
        for e in disputed
    ]

    mo.vstack([
        mo.md("### Vote analysis"),
        mo.hstack(analysis_items, gap=1, justify="start"),
        mo.ui.table(disputed_rows, selection=None, label="Most disputed edges") if disputed_rows else mo.md("*No disputed edges.*"),
    ])
    return


if __name__ == "__main__":
    app.run()
