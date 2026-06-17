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
def _(mo):
    fit_raw = mo.ui.switch(value=False, label="Fit to traces")
    line_raw = mo.ui.slider(start=0.25, stop=3.0, step=0.25, value=1.0, label="Line thickness", show_value=True)
    return fit_raw, line_raw


@app.cell
def _(sessions_data, sessions_table):
    # Shared selection + per-session colour, used by BOTH the raw and matched maps
    # so a row selected in the table filters (and colours) both consistently.
    from components.style import cycle_color as _cycle_color

    selected_ids = (
        {row["id"].split("\u2026")[0] for row in sessions_table.value}
        if sessions_table.value
        else set()
    )
    session_color = {s["id"][:8]: _cycle_color(i) for i, s in enumerate(sessions_data)}
    return selected_ids, session_color


@app.cell
def _(sessions_data, selected_ids, session_color, fit_raw, line_raw, mo):
    from components.maps import path_layer as _path_layer, deck as _deck, default_view_state as _default_view_state

    paths = []
    for session in sessions_data:
        short_id = session["id"][:8]
        if selected_ids and short_id not in selected_ids:
            continue
        if not session["path"] or len(session["path"]) < 2:
            continue
        paths.append({
            "path": session["path"],
            "color": session_color.get(short_id, [120, 120, 120]),
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
        view_state=None if fit_raw.value else _view,
        fit=fit_raw.value,
        line_scale=line_raw.value,
        height=675,
        fixed_height=True,
        tooltip_html="<b>{name}</b>",
    )

    _label = f"Raw traces ({len(paths)} shown)" if paths else "No raw traces to show"
    raw_column = mo.vstack([
        mo.md(f"### {_label}"),
        mo.hstack([fit_raw, line_raw], gap=2, align="center"),
        raw_map,
    ])
    return (raw_column,)


@app.cell
def _(mo):
    clean_all_button = mo.ui.run_button(label="Clean all RAW sessions")
    return (clean_all_button,)


@app.cell
def _(line_selector, clean_all_button, matched_stats, mo):
    mo.stop(not line_selector.value)
    # Matched-traces stats sit on the same row as the title so both maps below
    # start at the same height and line up.
    mo.hstack(
        [
            mo.vstack([mo.md("### Map-matching"), clean_all_button]),
            matched_stats,
        ],
        justify="space-between",
        align="center",
    )
    return


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
def _(mo):
    fit_cleaned = mo.ui.switch(value=False, label="Fit to trips")
    line_cleaned = mo.ui.slider(start=0.25, stop=3.0, step=0.25, value=1.0, label="Line thickness", show_value=True)
    return fit_cleaned, line_cleaned


@app.cell
def _(line_selector, db, selected_ids, session_color, fit_cleaned, line_cleaned, mo):
    from uuid import UUID as _UUID
    from components.data import load_trips
    from components.maps import path_layer as _path_layer, deck as _deck, default_view_state as _default_view_state

    trips = load_trips(db, _UUID(line_selector.value))

    trip_paths = []
    for trip in trips:
        _sid = trip["session_id"][:8]
        if selected_ids and _sid not in selected_ids:
            continue
        if not trip["path"] or len(trip["path"]) < 2:
            continue
        trip_paths.append({
            "path": trip["path"],
            "color": session_color.get(_sid, [120, 120, 120]),
            "name": f"Trip {_sid}\u2026 (score: {trip['match_score']:.2f})" if trip["match_score"] else f"Trip {_sid}\u2026",
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
        view_state=None if fit_cleaned.value else _view,
        fit=fit_cleaned.value,
        line_scale=line_cleaned.value,
        height=675,
        fixed_height=True,
        tooltip_html="<b>{name}</b>",
    )

    if trips:
        matched_stats = mo.hstack(
            [
                mo.stat(label="Cleaned trips", value=str(len(trips))),
                mo.stat(label="Shown", value=str(len(trip_paths))),
                mo.stat(
                    label="Avg match score",
                    value=f"{sum(t['match_score'] or 0 for t in trips) / len(trips):.2f}",
                ),
            ],
            gap=1,
            justify="end",
        )
        cleaned_column = mo.vstack([
            mo.md(f"### Matched traces ({len(trip_paths)} shown)"),
            mo.hstack([fit_cleaned, line_cleaned], gap=2, align="center"),
            cleaned_map,
        ])
    else:
        matched_stats = mo.md("")
        cleaned_column = mo.vstack([
            mo.md("### Matched traces"),
            mo.md("*No cleaned trips yet. Use the map-matching button above.*"),
        ])
    return cleaned_column, matched_stats


@app.cell
def _(raw_column, cleaned_column, mo):
    # Raw traces and matched traces side by side; both filter on the table selection.
    mo.hstack([raw_column, cleaned_column], widths="equal", gap=1, align="start")
    return


if __name__ == "__main__":
    app.run()
