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
    line_selector = mo.ui.dropdown(
        options=_options,
        label="Line",
    )
    line_selector
    return (line_selector,)


@app.cell
def _(line_selector, db, mo):
    from uuid import UUID as _UUID
    from components.data import load_sessions

    mo.stop(not line_selector.value)

    sessions_data = load_sessions(db, _UUID(line_selector.value))
    raw_count = sum(1 for s in sessions_data if s["processing_status"] == "raw")
    cleaned_count = sum(1 for s in sessions_data if s["has_trip"])

    status_summary = mo.hstack(
        [
            mo.stat(label="Total sessions", value=str(len(sessions_data))),
            mo.stat(label="RAW (unmatched)", value=str(raw_count)),
            mo.stat(label="Cleaned (matched)", value=str(cleaned_count)),
        ],
        gap=1,
        justify="start",
    )
    status_summary
    return sessions_data, raw_count, cleaned_count


@app.cell
def _(sessions_data, mo):
    display_rows = [
        {
            "id": s["id"][:8] + "\u2026",
            "status": s["status"],
            "processing": s["processing_status"],
            "device": s["device_id"] or "\u2014",
            "points": s["point_count"],
            "matched": "\u2713" if s["has_trip"] else "",
            "score": s["match_score"],
        }
        for s in sessions_data
    ]
    sessions_table = mo.ui.table(
        display_rows,
        selection="multi",
        label="Sessions",
    )
    sessions_table
    return (sessions_table,)


@app.cell
def _(sessions_table, sessions_data, mo):
    from components.maps import path_layer as _path_layer, deck as _deck, default_view_state as _default_view_state
    from components.style import cycle_color as _cycle_color

    selected_indices = [i for i, _ in enumerate(sessions_table.value)] if sessions_table.value else []
    selected_ids = {sessions_table.value[i]["id"].split("\u2026")[0] for i in range(len(sessions_table.value))} if sessions_table.value else set()

    paths = []
    for _idx, session in enumerate(sessions_data):
        short_id = session["id"][:8]
        if selected_ids and short_id not in selected_ids:
            continue
        if not session["path"] or len(session["path"]) < 2:
            continue
        paths.append({
            "path": session["path"],
            "color": _cycle_color(_idx),
            "name": f"Session {short_id}\u2026",
        })

    _view = _default_view_state()
    if paths and paths[0]["path"]:
        _mid = len(paths[0]["path"]) // 2
        _view = _default_view_state(
            lat=paths[0]["path"][_mid][1],
            lon=paths[0]["path"][_mid][0],
        )

    raw_map = _deck(
        [_path_layer(paths, id="raw-paths")] if paths else [],
        view_state=_view,
        height=450,
        tooltip_html="<b>{name}</b>",
    )

    label = f"Raw traces ({len(paths)} shown)" if paths else "No traces to show"
    mo.vstack([mo.md(f"### {label}"), raw_map])
    return


@app.cell
def _(line_selector, mo):
    mo.stop(not line_selector.value)

    clean_all_button = mo.ui.run_button(label="Clean all RAW sessions")
    mo.vstack([mo.md("### Map-matching"), clean_all_button])
    return (clean_all_button,)


@app.cell
def _(clean_all_button, line_selector, db, mo):
    from uuid import UUID as _UUID
    from geodata.match import match_line

    mo.stop(not clean_all_button.value)

    result = match_line(
        db,
        _UUID(line_selector.value),
        costing="bus",
        search_radius=60,
        gps_accuracy=20,
    )

    summary_items = [
        mo.stat(label="Matched", value=str(len(result.matched))),
        mo.stat(label="Failed", value=str(len(result.failed))),
    ]
    if result.matched:
        avg_score = sum(m.confidence for m in result.matched) / len(result.matched)
        summary_items.append(mo.stat(label="Avg confidence", value=f"{avg_score:.2f}"))

    mo.hstack(summary_items, gap=1, justify="start")
    return


@app.cell
def _(line_selector, db, mo):
    from uuid import UUID as _UUID
    from components.data import load_trips
    from components.maps import path_layer as _path_layer, deck as _deck, default_view_state as _default_view_state
    from components.style import cycle_color as _cycle_color, COLORS as _COLORS
    from components.formatting import format_distance, path_length_m

    mo.stop(not line_selector.value)

    trips = load_trips(db, _UUID(line_selector.value))
    mo.stop(not trips, mo.md("*No cleaned trips yet. Use the map-matching button above.*"))

    trip_paths = []
    for _idx, trip in enumerate(trips):
        if not trip["path"] or len(trip["path"]) < 2:
            continue
        trip_paths.append({
            "path": trip["path"],
            "color": _cycle_color(_idx),
            "name": f"Trip (score: {trip['match_score']:.2f})" if trip["match_score"] else "Trip",
        })

    _view = _default_view_state()
    if trip_paths and trip_paths[0]["path"]:
        _mid = len(trip_paths[0]["path"]) // 2
        _view = _default_view_state(
            lat=trip_paths[0]["path"][_mid][1],
            lon=trip_paths[0]["path"][_mid][0],
        )

    cleaned_map = _deck(
        [_path_layer(trip_paths, id="cleaned-trips")] if trip_paths else [],
        view_state=_view,
        height=450,
        tooltip_html="<b>{name}</b>",
    )

    stats = mo.hstack(
        [
            mo.stat(label="Cleaned trips", value=str(len(trips))),
            mo.stat(
                label="Avg match score",
                value=f"{sum(t['match_score'] or 0 for t in trips) / len(trips):.2f}" if trips else "\u2014",
            ),
        ],
        gap=1,
        justify="start",
    )

    mo.vstack([mo.md(f"### Cleaned trips ({len(trip_paths)} shown)"), stats, cleaned_map])
    return


if __name__ == "__main__":
    app.run()
