"""Helpers for invoking the pipeline from the API process.

Used by `recordings.py` to fire `clean_traces` immediately after a
recording ends — gives users a fast "trip uploaded → soon visible as
a clean Trip" feedback loop without waiting for the next cron tick.

The heavier downstream steps (`reconstruct_routes`, `resolve_*`,
`infer_schedules`, `rebuild_graph`) stay on the cron schedule because
they're per-line aggregations that don't benefit from per-trip
firing — running them on every upload would be wasteful and would
churn route versions unnecessarily.
"""

from uuid import UUID

from database.connection import SessionLocal
from pipeline.runner import run_pipeline


def run_clean_traces_for_line(line_id: UUID) -> None:
    """Open a fresh DB session and run only the `clean_traces` step
    scoped to one line. Wraps the call in `run_pipeline` so the run
    is recorded in `PipelineRun`/`PipelineStepResult` with
    `trigger="event:recording_end"` — telemetry parity with cron.

    Designed to be passed to FastAPI's `BackgroundTasks.add_task`,
    so it runs after the response is sent and never blocks the
    request handler.
    """
    db = SessionLocal()
    try:
        run_pipeline(
            db,
            trigger="event:recording_end",
            steps=["clean_traces"],
            step_params={"clean_traces": {"line_id": line_id}},
            continue_on_error=True,
        )
    finally:
        db.close()
