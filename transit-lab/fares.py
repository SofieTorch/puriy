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
    from sqlalchemy import select as _select
    from database.models.fare import FareZone as _FareZone
    from geoalchemy2 import WKBElement
    from shapely import wkb
    from shapely.geometry import mapping
    from components.maps import polygon_layer, deck, default_view_state

    zones = db.execute(_select(_FareZone).order_by(_FareZone.name)).scalars().all()

    zone_data = []
    for zone in zones:
        if zone.boundary is None:
            continue
        if isinstance(zone.boundary, WKBElement):
            shape = wkb.loads(bytes(zone.boundary.data))
            geojson = mapping(shape)
            # PolygonLayer expects a flat list of [lon, lat] rings
            if geojson["type"] == "MultiPolygon":
                for polygon_coords in geojson["coordinates"]:
                    zone_data.append({
                        "polygon": polygon_coords[0],  # outer ring
                        "color": [59, 130, 246, 60],
                        "name": zone.name,
                    })
            elif geojson["type"] == "Polygon":
                zone_data.append({
                    "polygon": geojson["coordinates"][0],
                    "color": [59, 130, 246, 60],
                    "name": zone.name,
                })

    zone_map = deck(
        [polygon_layer(zone_data, id="fare-zones")] if zone_data else [],
        height=450,
        tooltip_html="<b>{name}</b>",
    )

    zone_names = [z.name for z in zones]
    mo.vstack([
        mo.md(f"### Fare zones ({len(zones)})"),
        mo.md(", ".join(zone_names)) if zone_names else mo.md("*No fare zones imported yet. Run `geodata import-fare-zones`.*"),
        zone_map,
    ])
    return


@app.cell
def _(db, mo):
    from components.data import load_lines

    _lines = load_lines(db)
    _options = {"All lines": "", **{row["name"]: row["id"] for row in _lines}}
    fare_line_selector = mo.ui.dropdown(options=_options, value="", label="Filter by line")
    fare_line_selector
    return (fare_line_selector,)


@app.cell
def _(fare_line_selector, db, mo):
    from sqlalchemy import func, select as _select
    from database.models.fare import FareReport as _FareReport, FareZone as _FareZone

    _query = _select(
        func.coalesce(
            _select(_FareZone.name).where(_FareZone.id == _FareReport.boarding_zone_id).correlate(_FareReport).scalar_subquery(),
            "Unknown",
        ).label("boarding_zone"),
        func.coalesce(
            _select(_FareZone.name).where(_FareZone.id == _FareReport.alighting_zone_id).correlate(_FareReport).scalar_subquery(),
            "Unknown",
        ).label("alighting_zone"),
        func.round(func.avg(_FareReport.amount_bob), 2).label("avg_fare"),
        func.count().label("reports"),
    ).where(
        _FareReport.boarding_zone_id.is_not(None),
        _FareReport.alighting_zone_id.is_not(None),
    ).group_by(
        _FareReport.boarding_zone_id,
        _FareReport.alighting_zone_id,
    ).order_by(func.count().desc())

    if fare_line_selector.value:
        from uuid import UUID as _UUID
        _query = _query.where(_FareReport.line_id == _UUID(fare_line_selector.value))

    _rows = db.execute(_query).all()
    _matrix = [
        {
            "from": r.boarding_zone,
            "to": r.alighting_zone,
            "avg fare (BOB)": float(r.avg_fare),
            "reports": r.reports,
        }
        for r in _rows
    ]

    _table = mo.ui.table(_matrix, selection=None, label="Zone-pair fares") if _matrix else None
    _content = _table if _table else mo.md("*No fare reports yet.*")
    mo.vstack([mo.md("### Zone-pair fare matrix"), _content])
    return


@app.cell
def _(fare_line_selector, db, mo):
    from sqlalchemy import select as _select
    from database.models.fare import FareReport as _FareReport, FareZone as _FareZone

    _query = _select(_FareReport).order_by(_FareReport.created_at.desc()).limit(20)
    if fare_line_selector.value:
        from uuid import UUID as _UUID
        _query = _query.where(_FareReport.line_id == _UUID(fare_line_selector.value))

    _reports = db.execute(_query).scalars().all()
    _rows = []
    for _r in _reports:
        _bz = db.get(_FareZone, _r.boarding_zone_id) if _r.boarding_zone_id else None
        _az = db.get(_FareZone, _r.alighting_zone_id) if _r.alighting_zone_id else None
        _rows.append({
            "amount (BOB)": float(_r.amount_bob),
            "from zone": _bz.name if _bz else "\u2014",
            "to zone": _az.name if _az else "\u2014",
            "device": _r.device_id[:12],
            "date": _r.created_at.strftime("%Y-%m-%d %H:%M"),
        })

    _table = mo.ui.table(_rows, selection=None, label="Recent fare reports") if _rows else None
    _content = _table if _table else mo.md("*No reports yet.*")
    mo.vstack([mo.md("### Recent fare reports"), _content])
    return


if __name__ == "__main__":
    app.run()
