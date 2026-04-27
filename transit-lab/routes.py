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

    _lines = load_lines(db)
    _options = {row["name"]: row["id"] for row in _lines}
    line_selector = mo.ui.dropdown(options=_options, label="Line")
    line_selector
    return (line_selector,)


@app.cell
def _(line_selector, db, mo):
    from uuid import UUID as _UUID
    from components.data import load_route_edges, load_edge_voter_counts
    from geodata.edge_overlap import get_active_route

    if not line_selector.value:
        active_route = None
        active_edges = []
        edge_voter_counts = {}
    else:
        _line_id = _UUID(line_selector.value)
        active_route = get_active_route(db, _line_id)
        if active_route is None:
            active_edges = []
            edge_voter_counts = {}
        else:
            active_edges = load_route_edges(db, _line_id, route_id=active_route.id)
            edge_voter_counts = load_edge_voter_counts(db, active_route.id)
    return active_edges, active_route, edge_voter_counts


@app.cell
def _(mo):
    color_mode = mo.ui.radio(
        options=["approval", "coverage"],
        value="approval",
        label="Color edges by",
        inline=True,
    )
    return (color_mode,)


@app.cell
def _(line_selector, mo):
    if line_selector.value:
        voter_cap = mo.ui.number(
            value=20, start=1, stop=200, step=1,
            label="Coverage cap",
        )
    else:
        voter_cap = None
    return (voter_cap,)


@app.cell
def _(active_route, db, line_selector):
    from uuid import UUID as _UUID
    from components.data import count_eligible_voters, load_voting_events

    if not line_selector.value:
        voting_events = []
        eligible_voters = 0
    else:
        eligible_voters = count_eligible_voters(db, _UUID(line_selector.value))
        voting_events = (
            load_voting_events(db, active_route.id) if active_route else []
        )
    return eligible_voters, voting_events


@app.cell
def _(mo, voting_events):
    if not voting_events:
        events_table = None
    else:
        _rows = [
            {
                "device": (e["device_id"] or "")[:8],
                "vote": e["vote"],
                "edges": e["edge_count"],
                "when": e["created_at"].isoformat(timespec="seconds"),
            }
            for e in voting_events
        ]
        events_table = mo.ui.table(_rows, selection="single", label="Voting events (newest first)")
    return (events_table,)


@app.cell
def _(mo):
    preview_device_input = mo.ui.text(
        value="",
        placeholder="device_id",
        label="Preview pending segment for device",
    )
    preview_button = mo.ui.run_button(label="Preview segment")
    mo.hstack([preview_device_input, preview_button], gap=1, align="end")
    return preview_button, preview_device_input


@app.cell
def _(db, line_selector, preview_button, preview_device_input):
    from uuid import UUID as _UUID
    from components.data import load_segment_for_device

    if not line_selector.value or not preview_button.value:
        preview_result = None
    else:
        _device = preview_device_input.value.strip()
        if not _device:
            preview_result = {"error": "Enter a device id."}
        else:
            preview_result = load_segment_for_device(
                db, _UUID(line_selector.value), _device
            )
    return (preview_result,)


@app.cell
def _(
    active_edges,
    active_route,
    color_mode,
    edge_voter_counts,
    events_table,
    line_selector,
    mo,
    preview_result,
    voter_cap,
    voting_events,
):
    from components.maps import path_layer, scatter_layer, deck, default_view_state
    from components.style import confidence_color, coverage_color, darken

    if not line_selector.value:
        route_map = mo.md("*Select a line to begin.*")
    elif active_route is None:
        route_map = mo.md("*This line has no active route yet.*")
    elif not active_edges:
        route_map = mo.md("*The active route has no edges.*")
    else:
        # Resolve highlighted edges from either the activity log or the preview.
        _highlight_ids: set[str] = set()
        _highlight_color = [255, 235, 59, 230]  # default yellow
        _selected_event = None
        if events_table is not None and events_table.value:
            _sel = events_table.value[0]
            # Match selected row back to the events list (device + when + vote)
            for ev in voting_events:
                if (
                    (ev["device_id"] or "")[:8] == _sel["device"]
                    and ev["vote"] == _sel["vote"]
                    and ev["created_at"].isoformat(timespec="seconds") == _sel["when"]
                ):
                    _selected_event = ev
                    _highlight_ids = set(ev["edge_ids"])
                    _highlight_color = (
                        [34, 197, 94, 230] if ev["vote"] == "approve" else [239, 68, 68, 230]
                    )
                    break
        elif preview_result and preview_result.get("eligible") and preview_result.get("edges"):
            _highlight_ids = {e["id"] for e in preview_result["edges"]}
            _highlight_color = [99, 102, 241, 230]  # indigo for "would be voted"

        _cap = int(voter_cap.value) if voter_cap is not None and voter_cap.value else 20

        _edge_paths = []
        _junction_dots = []
        _highlight_paths = []
        for edge in active_edges:
            if not edge["path"] or len(edge["path"]) < 2:
                continue
            if color_mode.value == "coverage":
                _color = coverage_color(edge_voter_counts.get(edge["id"], 0), cap=_cap)
                _label_extra = f"voters: {edge_voter_counts.get(edge['id'], 0)}"
            else:
                _total = edge["votes_for"] + edge["votes_against"]
                if _total == 0:
                    _color = [156, 163, 175, 180]  # neutral grey when no votes
                else:
                    _color = confidence_color(edge["votes_for"] / _total)
                _label_extra = f"+{edge['votes_for']}/-{edge['votes_against']}"

            _name = f"Edge {edge['sequence']} ({_label_extra})"
            _edge_paths.append({"path": edge["path"], "color": _color, "name": _name})

            _dot_color = darken(_color)
            _dot_color[3] = 230
            _junction_dots.append({
                "position": [edge["path"][0][0], edge["path"][0][1]],
                "color": _dot_color,
                "name": f"Joint @ edge {edge['sequence']}",
            })

            if edge["id"] in _highlight_ids:
                _highlight_paths.append({
                    "path": edge["path"],
                    "color": _highlight_color,
                    "name": f"Highlighted edge {edge['sequence']}",
                })

        if active_edges and active_edges[-1]["path"] and len(active_edges[-1]["path"]) >= 2:
            _last = active_edges[-1]
            if color_mode.value == "coverage":
                _last_color = coverage_color(edge_voter_counts.get(_last["id"], 0), cap=_cap)
            else:
                _t = _last["votes_for"] + _last["votes_against"]
                _last_color = (
                    confidence_color(_last["votes_for"] / _t) if _t else [156, 163, 175, 180]
                )
            _end_color = darken(_last_color)
            _end_color[3] = 230
            _junction_dots.append({
                "position": [_last["path"][-1][0], _last["path"][-1][1]],
                "color": _end_color,
                "name": f"Route end (edge {_last['sequence']})",
            })

        _view = default_view_state()
        if _edge_paths and _edge_paths[0]["path"]:
            _mid = len(_edge_paths[0]["path"]) // 2
            _view = default_view_state(
                lat=_edge_paths[0]["path"][_mid][1],
                lon=_edge_paths[0]["path"][_mid][0],
                zoom=14,
            )

        _layers = [path_layer(_edge_paths, id="edges", width=5)]
        if _highlight_paths:
            _layers.append(path_layer(_highlight_paths, id="highlight", width=10, opacity=0.85))
        _layers.append(scatter_layer(_junction_dots, id="junctions", radius=8))

        route_map = deck(
            _layers,
            view_state=_view,
            height=500,
            tooltip_html="<b>{name}</b>",
        )
    return (route_map,)


@app.cell
def _(
    active_edges,
    active_route,
    edge_voter_counts,
    eligible_voters,
    line_selector,
    mo,
    voting_events,
):
    if not line_selector.value or active_route is None:
        stats_strip = mo.md("")
    else:
        _distinct_voters = len({d for ev in voting_events for d in [ev["device_id"]] if d})
        _no_votes = sum(
            1 for e in active_edges if e["votes_for"] + e["votes_against"] == 0
        )
        _disputed = sum(1 for e in active_edges if e["votes_against"] > 0)
        _max_voters = max(edge_voter_counts.values(), default=0)
        stats_strip = mo.hstack(
            [
                mo.stat(label="Eligible voters (≥3 trips)", value=str(eligible_voters)),
                mo.stat(label="Voters cast", value=str(_distinct_voters)),
                mo.stat(label="Vote events", value=str(len(voting_events))),
                mo.stat(label="Edges (no votes)", value=str(_no_votes)),
                mo.stat(label="Edges (disputed)", value=str(_disputed)),
                mo.stat(label="Max voters / edge", value=str(_max_voters)),
            ],
            gap=1,
            justify="start",
        )
    stats_strip
    return


@app.cell
def _(color_mode, mo, route_map, voter_cap):
    _controls = [color_mode]
    if voter_cap is not None and color_mode.value == "coverage":
        _controls.append(voter_cap)
    mo.vstack(
        [mo.md("### Active route"), mo.hstack(_controls, gap=1, align="end"), route_map],
        gap=0.5,
        align="stretch",
    )
    return


@app.cell
def _(events_table, mo):
    if events_table is None:
        _view = mo.md("*No vote events for this route yet.*")
    else:
        _view = events_table
    mo.vstack([mo.md("### Voting activity"), _view], gap=0.5, align="stretch")
    return


@app.cell
def _(mo, preview_result):
    if preview_result is None:
        _msg = mo.md("*Type a device id and click **Preview segment** to see what that user would currently be asked to vote on.*")
    elif "error" in preview_result:
        _msg = mo.md(f"**{preview_result['error']}**")
    elif not preview_result["eligible"]:
        _msg = mo.md(
            f"Device has **{preview_result['trip_count']}** cleaned trip(s) on this line — "
            "below the minimum of 3, so they cannot vote yet."
        )
    elif not preview_result["edges"]:
        _msg = mo.md(
            f"Device has **{preview_result['trip_count']}** trip(s) but no unvoted overlapping "
            "edges — they have already voted on everything they can reach."
        )
    else:
        _msg = mo.md(
            f"Device is eligible (**{preview_result['trip_count']}** trips). "
            f"Pending segment: **{len(preview_result['edges'])}** edge(s) highlighted on the map."
        )
    mo.vstack([mo.md("### Segment preview"), _msg], gap=0.5, align="stretch")
    return


if __name__ == "__main__":
    app.run()
