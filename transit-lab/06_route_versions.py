import marimo

__generated_with = "0.20.4"
app = marimo.App(width="medium")


@app.cell
def _():
    from components.navbar import navbar

    return


@app.cell
def _():
    import marimo as mo
    import pydeck as pdk
    from geoalchemy2.shape import to_shape
    from sqlalchemy import select

    from database.connection import SessionLocal
    from database.models.line import Line
    from database.models.route import RouteEstimation, RouteSegment

    return Line, RouteEstimation, RouteSegment, SessionLocal, mo, pdk, select, to_shape


@app.cell
def _(SessionLocal):
    db = SessionLocal()
    return (db,)


@app.cell
def _(Line, db, mo, select):
    all_lines = db.execute(select(Line).order_by(Line.name)).scalars().all()
    line_options = {f"{line.name} ({line.status.value})": line.id for line in all_lines}

    line_selector = mo.ui.dropdown(
        options=line_options,
        label="Line",
    )
    line_selector
    return line_options, line_selector


@app.cell
def _(RouteEstimation, db, line_selector, mo, select):
    if not line_selector.value:
        estimations = []
        estimations_info = mo.md("Select a line to see its route versions.")
    else:
        estimations = (
            db.execute(
                select(RouteEstimation)
                .where(RouteEstimation.line_id == line_selector.value)
                .order_by(RouteEstimation.version)
            )
            .scalars()
            .all()
        )
        if not estimations:
            estimations_info = mo.callout(
                mo.md("No route estimations found for this line."), kind="warn"
            )
        else:
            estimations_info = mo.md(f"Found **{len(estimations)}** version(s).")

    estimations_info
    return (estimations,)


@app.cell
def _(RouteSegment, db, estimations, mo, pdk, select, to_shape):
    def _confidence_color(confidence: float) -> list:
        c = max(0.0, min(1.0, confidence))
        r = int(220 * (1 - c) + 50 * c)
        g = int(50 * (1 - c) + 200 * c)
        return [r, g, 50, 200]

    version_maps = []

    for _estimation in estimations:
        _segments = (
            db.execute(
                select(RouteSegment)
                .where(RouteSegment.estimation_id == _estimation.id)
                .order_by(RouteSegment.sequence)
            )
            .scalars()
            .all()
        )

        _layer_data = []
        _all_coords = []

        for _seg in _segments:
            if _seg.path is not None:
                try:
                    _geom = to_shape(_seg.path)
                    _coords = [[c[0], c[1]] for c in _geom.coords]
                    _conf = _seg.confidence or 0.0
                    _layer_data.append({
                        "path": _coords,
                        "color": _confidence_color(_conf),
                        "confidence": f"{_conf:.2f}",
                        "sequence": _seg.sequence,
                        "votes_for": _seg.votes_for or 0,
                        "votes_against": _seg.votes_against or 0,
                        "status": _seg.status.value,
                    })
                    _all_coords.extend(_coords)
                except Exception:
                    pass

        if _all_coords:
            _center_lat = sum(c[1] for c in _all_coords) / len(_all_coords)
            _center_lon = sum(c[0] for c in _all_coords) / len(_all_coords)
        else:
            _center_lat, _center_lon = -17.4, -66.2

        _view = pdk.ViewState(latitude=_center_lat, longitude=_center_lon, zoom=13)

        _layers = []
        if _layer_data:
            _layers.append(
                pdk.Layer(
                    "PathLayer",
                    _layer_data,
                    get_path="path",
                    get_color="color",
                    get_width=6,
                    width_min_pixels=3,
                    pickable=True,
                    auto_highlight=True,
                    highlight_color=[255, 255, 100, 255],
                )
            )

        _deck = pdk.Deck(
            map_style="light",
            map_provider="carto",
            initial_view_state=_view,
            layers=_layers,
            height=450,
            tooltip={
                "html": "<b>Segment #{sequence}</b><br/>Confidence: {confidence}<br/>Votes: +{votes_for} / -{votes_against}<br/>Status: {status}",
                "style": {
                    "backgroundColor": "white",
                    "color": "black",
                    "fontFamily": "ui-monospace, monospace",
                    "border": "1px solid grey",
                    "fontSize": "12px",
                },
            },
        )

        _created = (
            _estimation.created_at.strftime("%Y-%m-%d %H:%M")
            if _estimation.created_at
            else "—"
        )
        _label = mo.md(
            f"### Version {_estimation.version} &nbsp; `{_estimation.status.value}` &nbsp;·&nbsp; "
            f"{len(_segments)} segments &nbsp;·&nbsp; {_estimation.trip_count or 0} trips &nbsp;·&nbsp; {_created}"
        )
        version_maps.append(mo.vstack([_label, _deck], gap=0.5))

    mo.vstack(version_maps, gap=2) if version_maps else mo.md("")
    return
