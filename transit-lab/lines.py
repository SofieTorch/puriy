import marimo

__generated_with = "0.23.3"
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

    lines_data = load_lines(db)
    lines_table = mo.ui.table(
        lines_data,
        selection="single",
        label="Transit lines",
    )
    lines_table
    return (lines_table,)


@app.cell
def _(db, lines_table, mo):
    from database.models import Line as _Line, LineStatus as _LineStatus, LineType as _LineType
    from uuid import UUID as _UUID

    selected = lines_table.value
    _no_selection = mo.md("*Select a line from the table above to see details.*")

    def _detail():
        if not selected:
            return _no_selection
        row = selected[0]
        line = db.get(_Line, _UUID(row["id"]))
        if not line:
            return _no_selection

        info = mo.hstack(
            [
                mo.stat(label="Name", value=line.name),
                mo.stat(label="Type", value=line.line_type.value if line.line_type else "—"),
                mo.stat(label="Status", value=line.status.value),
                mo.stat(label="Sessions", value=str(row["session_count"])),
                mo.stat(label="Trips", value=str(row["trip_count"])),
                mo.stat(label="Route v.", value=str(row["route_version"] or "—")),
            ],
            gap=1,
            justify="start",
        )
        return mo.vstack([mo.md(f"### {line.name}"), info])

    _detail()
    return


@app.cell(hide_code=True)
def _(lines_table, mo):
    if not lines_table.value:
        _hist_header = mo.md("")
    else:
        _hist_header = mo.md("### Route history")
    _hist_header
    return


@app.cell
def _(db, lines_table, mo):
    from uuid import UUID as _UUID
    from components.data import load_route_info

    if not lines_table.value:
        routes_data = []
        routes_table = None
    else:
        routes_data = load_route_info(db, _UUID(lines_table.value[0]["id"]))
        if not routes_data:
            routes_table = None
        else:
            _display_rows = [
                {
                    "version": r["version"],
                    "fragment": f"{r['fragment_index'] + 1}/{r['fragment_count']}",
                    "source": r["source"],
                    "strategy": r["strategy_key"] or "—",
                    "status": r["status"],
                    "edges": r["edge_count"],
                    "trips": r["trip_count"],
                    "created": r["created_at"][:16],
                }
                for r in routes_data
            ]
            routes_table = mo.ui.table(_display_rows, selection="single", label="Route versions")

    if lines_table.value and not routes_data:
        _versions_view = mo.md("*No routes for this line yet.*")
    elif routes_table is not None:
        _versions_view = routes_table
    else:
        _versions_view = mo.md("")
    _versions_view
    return routes_data, routes_table


@app.cell
def _(mo):
    fit_view = mo.ui.switch(value=False, label="Fit to route")
    line_width = mo.ui.slider(start=0.25, stop=3.0, step=0.25, value=1.0, label="Line thickness", show_value=True)
    return fit_view, line_width


@app.cell
def _(db, fit_view, line_width, lines_table, mo, routes_data, routes_table):
    from uuid import UUID as _UUID
    from components.data import load_route_edges
    from components.maps import path_layer, scatter_layer, deck, default_view_state
    from components.style import confidence_color, darken

    if not lines_table.value or not routes_data:
        route_map = mo.md("")
    else:
        _line_id = _UUID(lines_table.value[0]["id"])

        _selected_rows = routes_table.value if routes_table is not None else None
        _selected_route_id = None
        if _selected_rows:
            _sel = _selected_rows[0]
            _matches = [
                r for r in routes_data
                if r["version"] == _sel["version"]
                and r["fragment_index"] == int(_sel["fragment"].split("/")[0]) - 1
            ]
            if _matches:
                _selected_route_id = _UUID(_matches[0]["id"])

        edges = load_route_edges(db, _line_id, route_id=_selected_route_id)
        if not edges:
            route_map = mo.md("*No edges for the selected route.*")
        else:
            _edge_paths = []
            _junction_dots = []
            for edge in edges:
                if not edge["path"] or len(edge["path"]) < 2:
                    continue
                _color = confidence_color(edge["confidence"])
                _edge_paths.append({
                    "path": edge["path"],
                    "color": _color,
                    "name": f"Edge {edge['sequence']} (conf: {edge['confidence']:.2f}, +{edge['votes_for']}/-{edge['votes_against']})",
                })
                _dot_color = darken(_color)
                _dot_color[3] = 230
                _junction_dots.append({
                    "position": [edge["path"][0][0], edge["path"][0][1]],
                    "color": _dot_color,
                    "name": f"Joint @ edge {edge['sequence']}",
                })
            if edges and edges[-1]["path"] and len(edges[-1]["path"]) >= 2:
                _last_color = confidence_color(edges[-1]["confidence"])
                _end_color = darken(_last_color)
                _end_color[3] = 230
                _junction_dots.append({
                    "position": [edges[-1]["path"][-1][0], edges[-1]["path"][-1][1]],
                    "color": _end_color,
                    "name": f"Route end (edge {edges[-1]['sequence']})",
                })

            _view = default_view_state()
            if _edge_paths and _edge_paths[0]["path"]:
                _mid = len(_edge_paths[0]["path"]) // 2
                _view = default_view_state(
                    lat=_edge_paths[0]["path"][_mid][1],
                    lon=_edge_paths[0]["path"][_mid][0],
                    zoom=14,
                )

            _layers = []
            if _edge_paths:
                _layers.append(path_layer(_edge_paths, id="edges", width=5))
            if _junction_dots:
                _layers.append(scatter_layer(_junction_dots, id="junctions", radius=8))

            route_map = deck(
                _layers,
                view_state=None if fit_view.value else _view,
                fit=fit_view.value,
                line_scale=line_width.value,
                height=500,
                tooltip_html="<b>{name}</b>",
            )
    mo.vstack([mo.hstack([fit_view, line_width], gap=2, align="center"), route_map])
    return


@app.cell
def _(db, lines_table, mo):
    from database.models import Line as _Line, LineType as _LineType
    from uuid import UUID as _UUID

    _selected = lines_table.value

    def _edit_form():
        if not _selected:
            return mo.md("")
        row = _selected[0]
        _line = db.get(_Line, _UUID(row["id"]))
        if not _line:
            return mo.md("")

        _type_options = {"—": "", "Micro": "micro", "Trufi": "trufi", "Taxi-trufi": "taxi_trufi"}
        _current = _line.line_type.value if _line.line_type else ""
        _current_label = next((k for k, v in _type_options.items() if v == _current), "—")

        form = mo.ui.dictionary(
            {
                "name": mo.ui.text(value=_line.name, label="Name"),
                "description": mo.ui.text(value=_line.description or "", label="Description"),
                "line_type": mo.ui.dropdown(
                    options=_type_options,
                    value=_current_label,
                    label="Type",
                ),
            }
        )
        return mo.vstack([mo.md("### Edit line"), form])

    _edit_form()
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ### Create new line
    """)
    return


@app.cell
def _(mo):
    new_line_form = mo.ui.dictionary(
        {
            "name": mo.ui.text(label="Name"),
            "description": mo.ui.text(label="Description"),
            "line_type": mo.ui.dropdown(
                options={"—": "", "Micro": "micro", "Trufi": "trufi", "Taxi-trufi": "taxi_trufi"},
                value="—",
                label="Type",
            ),
        }
    )
    create_button = mo.ui.run_button(label="Create line")
    mo.hstack([new_line_form, create_button], gap=2, align="end")
    return create_button, new_line_form


@app.cell
def _(create_button, db, mo, new_line_form):
    from database.models import Line, LineType

    mo.stop(not create_button.value)

    name = new_line_form["name"].value.strip()
    mo.stop(not name, mo.md("**Name is required.**"))

    line_type_val = new_line_form["line_type"].value
    new_line = Line(
        name=name,
        description=new_line_form["description"].value.strip() or None,
        line_type=LineType(line_type_val) if line_type_val else None,
    )
    db.add(new_line)
    db.commit()
    db.refresh(new_line)
    mo.md(f"Created line **{new_line.name}** (`{new_line.id}`)")
    return


if __name__ == "__main__":
    app.run()
