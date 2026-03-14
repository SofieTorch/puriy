import marimo

__generated_with = "0.20.4"
app = marimo.App(width="medium")


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
    import math

    import marimo as mo
    import pandas as pd
    import pydeck as pdk
    from geoalchemy2.shape import to_shape
    from sqlalchemy import select

    from database.connection import SessionLocal
    from database.models.line import Line, LineStatus
    from database.models.trip import TripSession
    from geodata.merge import merge_lines

    return (
        Line,
        LineStatus,
        TripSession,
        SessionLocal,
        math,
        merge_lines,
        mo,
        pd,
        pdk,
        select,
        to_shape,
    )


@app.cell
def _(SessionLocal, mo):
    db = SessionLocal()
    get_refresh, set_refresh = mo.state(0)
    get_preserved_line_ids, set_preserved_line_ids = mo.state([])
    return db, get_preserved_line_ids, get_refresh, set_preserved_line_ids, set_refresh


@app.cell
def _(Line, db, get_preserved_line_ids, get_refresh, mo, pd, select):
    _ = get_refresh()
    all_lines = db.execute(select(Line).order_by(Line.name)).scalars().all()

    lines_df = pd.DataFrame(
        [
            {
                "id": line.id,
                "name": line.name,
                "status": line.status.value,
                "description": line.description or "",
                "created_at": line.created_at,
            }
            for line in all_lines
        ]
    )
    preserved = get_preserved_line_ids()
    initial_selection = (
        lines_df.index[lines_df["id"].isin(preserved)].tolist()
        if preserved
        else None
    )
    lines_table = mo.ui.table(
        data=lines_df,
        label="Lines",
        pagination=True,
        initial_selection=initial_selection,
    )
    return (lines_table,)


@app.cell
def _(lines_table, mo):
    selected = lines_table.value
    selected_line_ids = (
        selected["id"].tolist()
        if selected is not None and not selected.empty and "id" in selected.columns
        else []
    )

    merge_btn = mo.ui.button(
        label="Merge selected lines",
        value=0,
        on_click=lambda v: (v or 0) + 1,
        kind="neutral",
        disabled=len(selected_line_ids) < 2,
    )
    return merge_btn, selected_line_ids


@app.cell
def _(db, merge_btn, merge_lines, selected_line_ids, set_preserved_line_ids, set_refresh):
    if (merge_btn.value or 0) > 0 and len(selected_line_ids) >= 2:
        try:
            merge_lines(db, selected_line_ids)
            db.commit()
            set_preserved_line_ids(selected_line_ids)
            set_refresh(lambda v: v + 1)
        except Exception:
            db.rollback()
    return


@app.cell
def _(merge_btn, mo):
    table_header = mo.hstack(
        [mo.md("**Lines**"), merge_btn],
        justify="space-between",
        align="center",
    )
    view_3d_switch = mo.ui.switch(value=True, label="3D view")
    return table_header, view_3d_switch


@app.cell
def _(Line, LineStatus, db, mo, selected_line_ids):
    if len(selected_line_ids) != 1:
        edit_section = (
            mo.md("Select exactly one line to edit name, status and description.")
            if not selected_line_ids
            else mo.md("Select exactly one line to edit (or 2+ to merge).")
        )
        save_btn = name_input = status_dropdown = description_input = None
    else:
        line_id = selected_line_ids[0]
        line = db.get(Line, line_id)
        if line is None:
            edit_section = mo.md("Line not found.")
            save_btn = name_input = status_dropdown = description_input = None
        else:
            name_input = mo.ui.text(value=line.name, label="Name")
            status_dropdown = mo.ui.dropdown(
                options=[s.value for s in LineStatus],
                value=line.status.value,
                label="Status",
            )
            description_input = mo.ui.text(value=line.description or "", label="Description")
            save_btn = mo.ui.button(
                label="Save",
                value=0,
                on_click=lambda v: (v or 0) + 1,
                kind="neutral",
            )
            edit_section = mo.hstack(
                [name_input, status_dropdown, description_input, save_btn],
                gap=1,
                align="center",
                justify="start",
            )
    return (
        description_input,
        edit_section,
        name_input,
        save_btn,
        status_dropdown,
    )


@app.cell
def _(
    Line,
    LineStatus,
    db,
    description_input,
    name_input,
    save_btn,
    selected_line_ids,
    set_preserved_line_ids,
    set_refresh,
    status_dropdown,
):
    if (
        save_btn is not None
        and name_input is not None
        and status_dropdown is not None
        and description_input is not None
    ):
        if (save_btn.value or 0) > 0:
            lid = selected_line_ids[0]
            line_to_update = db.get(Line, lid)
            if line_to_update is not None:
                line_to_update.name = name_input.value
                line_to_update.status = LineStatus(status_dropdown.value)
                line_to_update.description = description_input.value or None
                db.add(line_to_update)
                db.commit()
                set_preserved_line_ids(selected_line_ids)
                set_refresh(lambda v: v + 1)
    return


@app.cell
def _(
    TripSession,
    db,
    math,
    mo,
    pdk,
    select,
    selected_line_ids,
    to_shape,
    view_3d_switch,
):
    pitch = 60 if view_3d_switch.value else 0

    def _haversine_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
        R = 6_371_000  # Earth radius in meters
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    def _format_distance(m: float) -> str:
        if m >= 1000:
            return f"{m / 1000:.1f} km"
        return f"{int(m)} m"

    PATH_COLORS = [
        [59, 130, 246],   # blue
        [34, 197, 94],    # green
        [234, 179, 8],    # amber
        [168, 85, 247],   # violet
        [236, 72, 153],   # pink
        [20, 184, 166],   # teal
    ]
    # RGBA: alpha 120 = ~47% opacity when not hovered; hovered path gets full highlight
    DEFAULT_ALPHA = 120

    if not selected_line_ids:
        sessions_map = mo.md("Select one or more lines to see trip sessions on the map.")
        plain_map = pdk.Deck(
            map_style="light",
            map_provider="carto",
            initial_view_state=pdk.ViewState(
                latitude=40.4,
                longitude=-3.7,
                zoom=10,
                pitch=pitch,
                bearing=0,
            ),
            layers=[],
            height=400,
        )
    else:
        sessions_list = list(
            db.execute(
                select(TripSession)
                .where(TripSession.line_id.in_(selected_line_ids))
                .order_by(TripSession.started_at.desc())
            ).scalars().all()
        )

        path_layer_data = []
        all_coords = []
        line_id_to_idx = {lid: i for i, lid in enumerate(selected_line_ids)}

        for s in sessions_list:
            if s.computed_path is not None:
                try:
                    geom = to_shape(s.computed_path)
                    path_coords = [[c[0], c[1], 0] for c in geom.coords]
                    points_count = len(path_coords)
                    distance_m = 0.0
                    for j in range(len(path_coords) - 1):
                        lon1, lat1 = path_coords[j][0], path_coords[j][1]
                        lon2, lat2 = path_coords[j + 1][0], path_coords[j + 1][1]
                        distance_m += _haversine_m(lon1, lat1, lon2, lat2)
                    rgb = PATH_COLORS[line_id_to_idx.get(s.line_id, 0) % len(PATH_COLORS)]
                    color_rgba = [*rgb, DEFAULT_ALPHA]
                    path_layer_data.append({
                        "path": path_coords,
                        "color": color_rgba,
                        "points": points_count,
                        "distance": _format_distance(distance_m),
                    })
                    all_coords.extend(path_coords)
                except Exception:
                    pass

        if path_layer_data:
            layers = [
                pdk.Layer(
                    "PathLayer",
                    path_layer_data,
                    get_path="path",
                    get_color="color",
                    get_width=5,
                    width_min_pixels=3,
                    pickable=True,
                    auto_highlight=True,
                    highlight_color=[255, 255, 100, 255],
                ),
            ]
            lons = [c[0] for c in all_coords]
            lats = [c[1] for c in all_coords]
            center_lat = sum(lats) / len(lats)
            center_lon = sum(lons) / len(lons)
        else:
            layers = []
            center_lat, center_lon = 40.4, -3.7

        sessions_map = pdk.Deck(
            map_style="light",
            map_provider="carto",
            initial_view_state=pdk.ViewState(
                latitude=center_lat,
                longitude=center_lon,
                zoom=12,
                pitch=pitch,
                bearing=0,
            ),
            layers=layers,
            height=400,
            tooltip={
                "html": "<b>Points:</b> {points}<br/><b>Distance:</b> {distance}",
                "style": {
                    "backgroundColor": "white",
                    "color": "black",
                    "fontFamily": "ui-monospace, monospace",
                    "border": "1px solid grey",
                    "fontSize": "12px",
                },
            },
        )
        plain_map = pdk.Deck(
            map_style="light",
            map_provider="carto",
            initial_view_state=pdk.ViewState(
                latitude=center_lat,
                longitude=center_lon,
                zoom=12,
                pitch=pitch,
                bearing=0,
            ),
            layers=[],
            height=400,
        )
    return plain_map, sessions_map


@app.cell
def _(
    edit_section,
    lines_table,
    mo,
    plain_map,
    sessions_map,
    table_header,
    view_3d_switch,
):
    (
        mo.vstack(
            [
                edit_section,
                table_header,
                lines_table,
                mo.hstack([mo.md("**Maps**"), view_3d_switch], justify="space-between", align="center"),
                mo.hstack(
                    [
                        mo.vstack([mo.md("**Trip sessions**"), sessions_map], gap=0.5),
                        mo.vstack([mo.md("**Plain map**"), plain_map], gap=0.5),
                    ],
                    widths=[1, 1],
                    gap=1,
                ),
            ],
            gap=1,
            align="stretch",
        )
        .style(style={"max-width": "100%"}, overflow_x="auto")
    )
    return


if __name__ == "__main__":
    app.run()
