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
def _(line_selector, db, mo):
    from uuid import UUID as _UUID
    from components.data import load_route_edges
    from components.maps import path_layer, deck, default_view_state
    from components.style import confidence_color, vote_ratio_color

    mo.stop(not line_selector.value)

    edges = load_route_edges(db, _UUID(line_selector.value))
    mo.stop(not edges, mo.md("*No active route edges.*"))

    edge_paths = []
    for edge in edges:
        if not edge["path"] or len(edge["path"]) < 2:
            continue
        color = confidence_color(edge["confidence"])
        edge_paths.append({
            "path": edge["path"],
            "color": color,
            "name": f"Edge {edge['sequence']} (conf: {edge['confidence']:.2f}, +{edge['votes_for']}/-{edge['votes_against']})",
        })

    _view = default_view_state()
    if edge_paths and edge_paths[0]["path"]:
        mid = len(edge_paths[0]["path"]) // 2
        _view = default_view_state(
            lat=edge_paths[0]["path"][mid][1],
            lon=edge_paths[0]["path"][mid][0],
            zoom=14,
        )

    route_map = deck(
        [path_layer(edge_paths, id="edges", width=5)] if edge_paths else [],
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
