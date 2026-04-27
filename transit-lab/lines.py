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

        form = mo.ui.dictionary(
            {
                "name": mo.ui.text(value=_line.name, label="Name"),
                "description": mo.ui.text(value=_line.description or "", label="Description"),
                "line_type": mo.ui.dropdown(
                    options={"—": "", "Micro": "micro", "Trufi": "trufi", "Taxi-trufi": "taxi_trufi"},
                    value=_line.line_type.value if _line.line_type else "",
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
                value="",
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
