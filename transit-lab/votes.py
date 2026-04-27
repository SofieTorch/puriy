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


@app.cell(hide_code=True)
def _(line_selector, mo):
    if not line_selector.value:
        _hdr = mo.md("")
    else:
        _hdr = mo.md(
            "### Simulate votes\n"
            "Closes the loop: existing **simulator-tagged** trips on this line → "
            "active route → synthetic votes. Each round-robin bucket of sessions "
            "becomes one synthetic voter; they vote **approve** if their segment "
            "tightly fits their actual path, **reject** otherwise."
        )
    _hdr
    return


@app.cell
def _(line_selector, mo):
    if not line_selector.value:
        n_voters = None
        fit_threshold = None
        tight_tolerance = None
        reset_synthetic = None
        sim_votes_button = None
        _block = mo.md("")
    else:
        n_voters = mo.ui.number(value=10, start=1, stop=200, step=1, label="Number of voters")
        fit_threshold = mo.ui.number(
            value=0.7, start=0.0, stop=1.0, step=0.05,
            label="Approve if fit ratio ≥",
        )
        tight_tolerance = mo.ui.number(
            value=15.0, start=1.0, stop=100.0, step=1.0,
            label="Tight overlap tolerance (m)",
        )
        reset_synthetic = mo.ui.switch(
            value=False,
            label="Reset synthetic votes (wipe & regenerate; real-user votes untouched)",
        )
        sim_votes_button = mo.ui.run_button(label="Simulate votes", kind="success")
        _block = mo.vstack(
            [
                mo.hstack([n_voters, fit_threshold, tight_tolerance], gap=1, align="end"),
                mo.hstack([reset_synthetic, sim_votes_button], gap=2, align="end"),
            ],
            gap=0.5,
        )
    _block
    return (
        fit_threshold,
        n_voters,
        reset_synthetic,
        sim_votes_button,
        tight_tolerance,
    )


@app.cell
def _(
    db,
    fit_threshold,
    line_selector,
    mo,
    n_voters,
    reset_synthetic,
    sim_votes_button,
    tight_tolerance,
):
    from uuid import UUID as _UUID
    from components.vote_simulator import simulate_votes_for_line

    if not line_selector.value or sim_votes_button is None or not sim_votes_button.value:
        vote_sim_result = None
    else:
        vote_sim_result = simulate_votes_for_line(
            db,
            _UUID(line_selector.value),
            n_voters=int(n_voters.value),
            fit_threshold=float(fit_threshold.value),
            tight_tolerance_m=float(tight_tolerance.value),
            reset_synthetic=bool(reset_synthetic.value),
        )
    return (vote_sim_result,)


@app.cell
def _(mo, vote_sim_result):
    if vote_sim_result is None:
        _view = mo.md("")
    elif vote_sim_result.error:
        _view = mo.md(f"**{vote_sim_result.error}**")
    else:
        _stats = mo.hstack(
            [
                mo.stat(label="Sessions", value=str(vote_sim_result.sessions_considered)),
                mo.stat(label="Voters", value=str(vote_sim_result.voters_total)),
                mo.stat(label="Eligible", value=str(vote_sim_result.voters_eligible)),
                mo.stat(label="Events", value=str(vote_sim_result.events_created)),
                mo.stat(label="Approve", value=str(vote_sim_result.approve)),
                mo.stat(label="Reject", value=str(vote_sim_result.reject)),
                mo.stat(label="Edges affected", value=str(vote_sim_result.edges_affected)),
                mo.stat(label="Synthetic wiped", value=str(vote_sim_result.synthetic_votes_wiped)),
            ],
            gap=1,
            justify="start",
        )
        _table = mo.ui.table(
            vote_sim_result.voter_breakdown or [],
            selection=None,
            label="Per-voter breakdown",
        )
        _view = mo.vstack([_stats, _table], gap=1, align="stretch")
    _view
    return


@app.cell
def _(line_selector, db, mo, vote_sim_result):
    from uuid import UUID as _UUID
    from components.data import load_route_edges, load_edge_voter_counts
    from geodata.edge_overlap import get_active_route

    _ = vote_sim_result  # re-load after a sim run so the rest of the page refreshes

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


@app.cell
def _(mo):
    minimap_mode = mo.ui.radio(
        options=["synthetic", "real"],
        value="synthetic",
        label="Show minimaps for",
        inline=True,
    )
    return (minimap_mode,)


@app.cell
def _(active_route, db, line_selector, minimap_mode, vote_sim_result):
    from uuid import UUID as _UUID
    from components.vote_simulator import (
        load_synthetic_voter_views,
        load_real_voter_views,
    )

    _ = vote_sim_result  # re-load after a sim run

    if not line_selector.value or active_route is None:
        voter_views = []
    elif minimap_mode.value == "real":
        voter_views = load_real_voter_views(
            db, _UUID(line_selector.value), active_route.id
        )
    else:
        voter_views = load_synthetic_voter_views(
            db, _UUID(line_selector.value), active_route.id
        )
    return (voter_views,)


@app.cell
def _(minimap_mode, mo, voter_views):
    from components.maps import path_layer, deck
    from components.vote_simulator import zoom_for_extent
    import pydeck as pdk

    APPROVE_COLOR = [34, 197, 94, 230]
    REJECT_COLOR = [239, 68, 68, 230]
    RAW_COLOR = [180, 180, 180, 160]
    CLEANED_COLOR = [59, 130, 246, 200]

    def _minimap(view):
        _layers = []
        if view["raw_paths"]:
            _layers.append(path_layer(
                [{"path": p, "color": RAW_COLOR, "name": "Raw GPS"} for p in view["raw_paths"]],
                id=f"raw-{view['voter_id']}",
                width=3,
                pickable=False,
                opacity=0.6,
            ))
        if view["cleaned_paths"]:
            _layers.append(path_layer(
                [{"path": p, "color": CLEANED_COLOR, "name": "Cleaned trip"} for p in view["cleaned_paths"]],
                id=f"clean-{view['voter_id']}",
                width=3,
                pickable=False,
                opacity=0.85,
            ))
        if view["voted_edges"]:
            _layers.append(path_layer(
                [
                    {
                        "path": ve["path"],
                        "color": APPROVE_COLOR if ve["vote"] == "approve" else REJECT_COLOR,
                        "name": f"Edge {ve['sequence']} — {ve['vote'].upper()}",
                    }
                    for ve in view["voted_edges"]
                ],
                id=f"voted-{view['voter_id']}",
                width=6,
                pickable=True,
                opacity=0.9,
            ))

        b = view["bounds"]
        if b is None:
            _view_state = pdk.ViewState(latitude=-17.39, longitude=-66.16, zoom=13, pitch=0, bearing=0)
        else:
            _zoom = zoom_for_extent(b["lat_max"] - b["lat_min"], b["lon_max"] - b["lon_min"])
            _view_state = pdk.ViewState(
                latitude=b["lat_center"], longitude=b["lon_center"],
                zoom=_zoom, pitch=0, bearing=0,
            )

        return deck(
            _layers,
            view_state=_view_state,
            height=240,
            tooltip_html="<b>{name}</b>",
        )

    if not voter_views:
        if minimap_mode.value == "real":
            _grid = mo.md("*No real-user votes yet for this route. Real users with `device_id` not starting with `simulator-vote-` will appear here once they vote.*")
        else:
            _grid = mo.md("*No synthetic voters with votes yet for this route. Run the vote simulator above first.*")
    else:
        _legend = mo.md(
            "**Legend:** "
            '<span style="color:#b4b4b4">━ raw GPS</span> &nbsp; '
            '<span style="color:#3b82f6">━ cleaned trip</span> &nbsp; '
            '<span style="color:#22c55e">━ voted APPROVE</span> &nbsp; '
            '<span style="color:#ef4444">━ voted REJECT</span> &nbsp; '
            "&middot; hover an edge to see the vote"
        )
        _columns = 3
        _tiles = [
            mo.vstack(
                [
                    mo.md(
                        f"**{v['voter_id']}** — {v['session_count']} sess. / {v['trip_count']} trips · "
                        f"approve {v['approve']} / reject {v['reject']}"
                    ),
                    _minimap(v),
                ],
                gap=0.25,
                align="stretch",
            )
            for v in voter_views
        ]
        _rows = []
        for i in range(0, len(_tiles), _columns):
            _row = _tiles[i : i + _columns]
            # Pad the last row so columns stay aligned.
            while len(_row) < _columns:
                _row.append(mo.md(""))
            _rows.append(mo.hstack(_row, gap=1, align="start"))

        _grid = mo.vstack([_legend, *_rows], gap=1, align="stretch")

    _title = "### Synthetic voter timelines" if minimap_mode.value == "synthetic" else "### Real voter timelines"
    mo.vstack([mo.md(_title), minimap_mode, _grid], gap=0.5, align="stretch")
    return


if __name__ == "__main__":
    app.run()
