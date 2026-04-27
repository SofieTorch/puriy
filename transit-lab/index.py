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
def _(db):
    from sqlalchemy import func, select
    from database.models import (
        Line, LineStatus, TripSession, SessionStatus, Trip,
        Route, RouteStatus,
    )

    line_count = db.execute(select(func.count()).where(Line.status == LineStatus.APPROVED)).scalar() or 0
    pending_line_count = db.execute(select(func.count()).where(Line.status == LineStatus.PENDING)).scalar() or 0
    session_count = db.execute(select(func.count(TripSession.id)).where(TripSession.status == SessionStatus.COMPLETED)).scalar() or 0
    trip_count = db.execute(select(func.count(Trip.id))).scalar() or 0
    route_count = db.execute(select(func.count(Route.id)).where(Route.status != RouteStatus.SUPERSEDED)).scalar() or 0

    lines_without_route = db.execute(
        select(func.count(Line.id)).where(
            Line.status == LineStatus.APPROVED,
            ~Line.id.in_(
                select(Route.line_id).where(Route.status != RouteStatus.SUPERSEDED)
            ),
        )
    ).scalar() or 0

    fragmented_routes = db.execute(
        select(func.count(Route.id)).where(
            Route.status != RouteStatus.SUPERSEDED,
            Route.fragment_count > 1,
            Route.fragment_index == 0,
        )
    ).scalar() or 0

    return (
        line_count, pending_line_count, session_count,
        trip_count, route_count, lines_without_route, fragmented_routes,
    )


@app.cell
def _(mo, line_count, pending_line_count, session_count, trip_count, route_count):
    stats = mo.hstack(
        [
            mo.stat(label="Approved lines", value=str(line_count)),
            mo.stat(label="Pending lines", value=str(pending_line_count)),
            mo.stat(label="Completed sessions", value=str(session_count)),
            mo.stat(label="Cleaned trips", value=str(trip_count)),
            mo.stat(label="Active routes", value=str(route_count)),
        ],
        gap=1,
        justify="start",
    )
    stats
    return


@app.cell
def _(mo, lines_without_route, fragmented_routes):
    health = mo.hstack(
        [
            mo.stat(label="Lines missing routes", value=str(lines_without_route)),
            mo.stat(label="Fragmented routes", value=str(fragmented_routes)),
        ],
        gap=1,
        justify="start",
    )
    mo.vstack([mo.md("### Route health"), health])
    return


@app.cell
def _(db, mo):
    from sqlalchemy import select as _select
    from database.models import TripSession as _TS

    recent_sessions = db.execute(
        _select(_TS).order_by(_TS.started_at.desc()).limit(10)
    ).scalars().all()

    rows = [
        {
            "status": s.status.value,
            "device": s.device_id or "\u2014",
            "line_id": str(s.line_id)[:8] + "\u2026" if s.line_id else "\u2014",
            "started": s.started_at.strftime("%Y-%m-%d %H:%M") if s.started_at else "",
            "points": len(s.points) if s.points else 0,
        }
        for s in recent_sessions
    ]

    table = mo.ui.table(rows, label="Recent sessions", selection=None)
    mo.vstack([mo.md("### Recent activity"), table])
    return


if __name__ == "__main__":
    app.run()
