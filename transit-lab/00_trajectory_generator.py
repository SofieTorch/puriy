import marimo

__generated_with = "0.20.4"
app = marimo.App(width="medium")


@app.cell
def _():
    import folium
    import marimo as mo
    from folium.plugins import Draw
    from sqlalchemy import select

    from database.connection import SessionLocal
    from database.models.line import Line, LineStatus

    return Draw, Line, LineStatus, SessionLocal, folium, mo, select


@app.cell
def _(SessionLocal, mo):
    db = SessionLocal()
    get_refresh, set_refresh = mo.state(0)
    get_last_create_click, set_last_create_click = mo.state(0)
    return (
        db,
        get_last_create_click,
        get_refresh,
        set_last_create_click,
        set_refresh,
    )


@app.cell
def _(Line, LineStatus, db, get_refresh, select):
    _ = get_refresh()
    approved_lines = (
        db.execute(
            select(Line)
            .where(Line.status == LineStatus.APPROVED)
            .order_by(Line.name)
        )
        .scalars()
        .all()
    )
    return (approved_lines,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Trajectory generator
    """)
    return


@app.cell
def _(approved_lines, mo):
    line_options = [f"{line.id} - {line.name}" for line in approved_lines]
    approved_line_selector = mo.ui.dropdown(
        options=line_options,
        value=line_options[0] if line_options else None,
        label="Approved lines",
    )
    return (approved_line_selector,)


@app.cell
def _(Line, approved_line_selector, db, mo):
    selected_line = None
    if approved_line_selector.value:
        selected_line_id = int(approved_line_selector.value.split(" - ", 1)[0])
        selected_line = db.get(Line, selected_line_id)

    selected_line_info = (
        mo.md(
            f"**Selected line:** `{selected_line.id}` - `{selected_line.name}` - `{selected_line.description or 'No description'}`"
        )
        if selected_line is not None
        else mo.md("No approved lines found.")
    )
    return (selected_line_info,)


@app.cell
def _(Draw, folium, mo):
    draw_map = folium.Map(
        location=[40.4168, -3.7038],
        zoom_start=12,
        tiles="CartoDB positron",
        control_scale=True,
    )

    Draw(
        export=True,
        filename="trajectory.geojson",
        position="topleft",
        draw_options={
            "polyline": True,
            "polygon": False,
            "rectangle": False,
            "circle": False,
            "marker": False,
            "circlemarker": False,
        },
        edit_options={"edit": False, "remove": True},
    ).add_to(draw_map)

    draw_path_section = mo.vstack(
        [
            mo.md("## Draw trajectory path"),
            mo.md(
                "Use the polyline tool (top-left) and click on the map to draw the path."
            ),
            mo.Html(draw_map._repr_html_()),
            mo.md(
                "_Tip: click **Export** on the map toolbar to download the drawn path as GeoJSON._"
            ),
        ],
        gap=1,
        align="start",
    )
    return (draw_path_section,)


@app.cell
def _(LineStatus, mo):
    new_line_name = mo.ui.text(label="New line name", placeholder="Line 42")
    new_line_description = mo.ui.text(
        label="Description (optional)",
        placeholder="Main corridor from A to B",
    )
    new_line_status = mo.ui.dropdown(
        options=[status.value for status in LineStatus],
        value=LineStatus.PENDING.value,
        label="Status",
    )
    create_line_button = mo.ui.button(
        label="Create new line",
        value=0,
        on_click=lambda v: (v or 0) + 1,
        kind="neutral",
    )
    return (
        create_line_button,
        new_line_description,
        new_line_name,
        new_line_status,
    )


@app.cell
def _(
    Line,
    LineStatus,
    create_line_button,
    db,
    get_last_create_click,
    new_line_description,
    new_line_name,
    new_line_status,
    set_last_create_click,
    set_refresh,
):
    create_line_feedback = ""
    current_click = create_line_button.value or 0
    if current_click > get_last_create_click():
        set_last_create_click(current_click)
        name = (new_line_name.value or "").strip()
        description = (new_line_description.value or "").strip() or None

        if not name:
            create_line_feedback = "Please provide a name before creating a line."
        else:
            try:
                new_line = Line(
                    name=name,
                    description=description,
                    status=LineStatus(new_line_status.value),
                )
                db.add(new_line)
                db.commit()
                set_refresh(lambda v: v + 1)
                create_line_feedback = f"Created new line: {name}"
            except Exception as exc:
                db.rollback()
                create_line_feedback = f"Could not create line: {exc}"
    return (create_line_feedback,)


@app.cell
def _(
    approved_line_selector,
    create_line_button,
    create_line_feedback,
    draw_path_section,
    mo,
    new_line_description,
    new_line_name,
    new_line_status,
    selected_line_info,
):
    form_body = mo.vstack(
        [
            mo.hstack(
                [new_line_name, new_line_description, new_line_status, create_line_button],
                gap=1,
            ),
            mo.md(create_line_feedback) if create_line_feedback else mo.md(""),
        ],
        gap=1,
        align="start",
    )

    accordion = mo.accordion({"Add a new line": form_body})

    mo.vstack([
        approved_line_selector,
        selected_line_info,
        accordion,
        draw_path_section,
    ])
    return


if __name__ == "__main__":
    app.run()
