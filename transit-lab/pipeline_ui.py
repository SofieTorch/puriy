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
def _():
    from pipeline.steps import STEPS
    from pipeline.runner import STEP_ORDER, run_pipeline
    return STEPS, STEP_ORDER, run_pipeline


@app.cell
def _(mo):
    mo.md("# Pipeline")
    return


# ── Run all ──────────────────────────────────────────────────────────────────

@app.cell
def _(mo, STEPS, STEP_ORDER):
    _checkboxes = []
    for _n in STEP_ORDER:
        _checkboxes.append(mo.ui.checkbox(value=True, label=STEPS[_n]["label"]))

    cb_cleanup, cb_dedup, cb_clean, cb_reconstruct, cb_edge, cb_line, cb_graph = _checkboxes
    run_all_btn = mo.ui.run_button(label="Run selected steps", kind="success")

    mo.hstack([
        cb_cleanup, cb_dedup, cb_clean, cb_reconstruct, cb_edge, cb_line, cb_graph,
        run_all_btn,
    ], gap=1.5, justify="start", align="center")
    return cb_cleanup, cb_dedup, cb_clean, cb_reconstruct, cb_edge, cb_line, cb_graph, run_all_btn


@app.cell
def _(mo, db, run_all_btn, run_pipeline, STEP_ORDER,
      cb_cleanup, cb_dedup, cb_clean, cb_reconstruct, cb_edge, cb_line, cb_graph):
    mo.stop(not run_all_btn.value)

    _flags = [cb_cleanup.value, cb_dedup.value, cb_clean.value, cb_reconstruct.value,
              cb_edge.value, cb_line.value, cb_graph.value]
    _selected = [_n for _n, _on in zip(STEP_ORDER, _flags) if _on]

    if not _selected:
        mo.stop(True, mo.callout("No steps selected.", kind="warn"))

    _run = run_pipeline(db, trigger="manual", steps=_selected)

    _rows = []
    _icons = {"completed": "✓", "failed": "✗", "skipped": "–", "pending": "…", "running": "⟳"}
    for _s in sorted(_run.steps, key=lambda s: STEP_ORDER.index(s.step_name) if s.step_name in STEP_ORDER else 99):
        _dur = ""
        if _s.started_at and _s.ended_at:
            _dur = f"{(_s.ended_at - _s.started_at).total_seconds():.1f}s"
        _rows.append({
            "": _icons.get(_s.status.value, "?"),
            "Step": _s.step_name,
            "Status": _s.status.value,
            "Duration": _dur,
            "Stats": str(_s.stats) if _s.stats else "",
            "Error": _s.error_message.strip().split("\n")[-1] if _s.error_message else "",
        })

    _kind = "success" if _run.status.value == "completed" else "danger"
    mo.vstack([
        mo.callout(f"Run {str(_run.id)[:8]} — **{_run.status.value}**", kind=_kind),
        mo.ui.table(_rows, selection=None),
    ])
    return


# ── Individual step buttons ──────────────────────────────────────────────────

@app.cell
def _(mo, STEPS, STEP_ORDER):
    _cards = []
    step_buttons = {}
    for _n in STEP_ORDER:
        _info = STEPS[_n]
        _btn = mo.ui.run_button(label="Run", kind="neutral")
        step_buttons[_n] = _btn
        _cards.append(mo.vstack([
            mo.md(f"**{_info['label']}**"),
            mo.md(f"<small style='color:#6b7280'>{_info['description']}</small>"),
            _btn,
        ], gap=0.25))

    mo.vstack([
        mo.md("### Run individual steps"),
        mo.hstack(_cards, gap=1.5, wrap=True),
    ])
    return (step_buttons,)


@app.cell
def _(mo, db, step_buttons, STEPS, STEP_ORDER, run_pipeline):
    _clicked = None
    for _n in STEP_ORDER:
        _b = step_buttons.get(_n)
        if _b and _b.value:
            _clicked = _n
            break

    mo.stop(_clicked is None)

    _result = run_pipeline(db, trigger="manual", steps=[_clicked])
    _step = _result.steps[0] if _result.steps else None
    if _step and _step.status.value == "completed":
        mo.callout(f"**{STEPS[_clicked]['label']}** completed: {_step.stats}", kind="success")
    elif _step:
        _err = _step.error_message.strip().split("\n")[-1] if _step.error_message else "unknown"
        mo.callout(f"**{STEPS[_clicked]['label']}** failed: {_err}", kind="danger")
    return


# ── Run history ──────────────────────────────────────────────────────────────

@app.cell
def _(mo):
    mo.md("---\n## Run history")
    return


@app.cell
def _(mo, db):
    from sqlalchemy import select as _select
    from database import PipelineRun as _PR

    _runs = db.execute(
        _select(_PR).order_by(_PR.started_at.desc()).limit(25)
    ).scalars().all()

    if not _runs:
        history_table = None
        all_runs = []
        mo.output.replace(mo.callout("No pipeline runs yet. Click **Run selected steps** above to start one.", kind="info"))
    else:
        _rows = []
        for _r in _runs:
            _dur = ""
            if _r.started_at and _r.ended_at:
                _t = (_r.ended_at - _r.started_at).total_seconds()
                _dur = f"{_t:.1f}s" if _t < 60 else f"{int(_t)//60}m {int(_t)%60}s"
            _ok = sum(1 for _s in _r.steps if _s.status.value == "completed") if _r.steps else 0
            _fail = sum(1 for _s in _r.steps if _s.status.value == "failed") if _r.steps else 0
            _summary = f"{_ok} ok" + (f", {_fail} failed" if _fail else "")
            _rows.append({
                "ID": str(_r.id)[:8],
                "Trigger": _r.trigger,
                "Status": _r.status.value,
                "Started": _r.started_at.strftime("%Y-%m-%d %H:%M") if _r.started_at else "",
                "Duration": _dur,
                "Steps": _summary,
            })

        history_table = mo.ui.table(_rows, selection="single", label="Select a run to inspect")
        all_runs = list(_runs)
        history_table
    return history_table, all_runs


@app.cell
def _(mo, history_table, all_runs, STEP_ORDER):
    mo.stop(history_table is None or not history_table.value)

    _row = history_table.value[0]
    _prefix = _row["ID"]
    _run = next((_r for _r in all_runs if str(_r.id).startswith(_prefix)), None)
    mo.stop(not _run)

    mo.md(f"### Run {_prefix} — {_run.trigger} — {_run.status.value}")
    return


@app.cell
def _(mo, history_table, all_runs, STEP_ORDER):
    mo.stop(history_table is None or not history_table.value)

    _row2 = history_table.value[0]
    _prefix2 = _row2["ID"]
    _run2 = next((_r for _r in all_runs if str(_r.id).startswith(_prefix2)), None)
    mo.stop(not _run2)

    _details = {}
    for _s in sorted(_run2.steps, key=lambda x: STEP_ORDER.index(x.step_name) if x.step_name in STEP_ORDER else 99):
        _items = []
        _status_badge = {"completed": "success", "failed": "danger", "skipped": "info"}.get(_s.status.value, "neutral")
        _items.append(mo.callout(f"**{_s.status.value.upper()}**", kind=_status_badge))

        if _s.started_at and _s.ended_at:
            _items.append(mo.md(f"Duration: **{(_s.ended_at - _s.started_at).total_seconds():.1f}s**"))

        if _s.stats:
            _stat_rows = [{"Metric": _k, "Value": str(_v)} for _k, _v in _s.stats.items() if _v is not None]
            if _stat_rows:
                _items.append(mo.ui.table(_stat_rows, selection=None))

        if _s.error_message:
            _items.append(mo.callout(mo.md(f"```\n{_s.error_message}\n```"), kind="danger"))

        _details[_s.step_name] = mo.vstack(_items)

    mo.accordion(_details)
    return


if __name__ == "__main__":
    app.run()
