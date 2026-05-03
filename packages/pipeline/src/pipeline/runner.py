"""Pipeline runner — orchestrates steps and tracks results in the database."""

import traceback
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from database import PipelineRun, PipelineRunStatus, PipelineStepResult, StepStatus
from .steps import STEPS

STEP_ORDER = [
    "cleanup",
    "deduplicate_lines",
    "clean_traces",
    "reconstruct_routes",
    "resolve_edge_votes",
    # `resolve_routes` must come after `resolve_edge_votes` so route
    # promotion sees the latest edge-confirmation state, and before
    # `rebuild_graph` so the directions graph picks up newly-confirmed
    # routes.
    "resolve_routes",
    "resolve_line_votes",
    "rebuild_graph",
    "infer_schedules",
]


def run_pipeline(
    db: Session,
    *,
    trigger: str = "manual",
    steps: list[str] | None = None,
    continue_on_error: bool = True,
    step_params: dict[str, dict] | None = None,
) -> PipelineRun:
    """Run pipeline steps in order, tracking results in the database.

    Args:
        db: Database session.
        trigger: How the run was initiated ("manual", "cli", "cron").
        steps: Which steps to run (None = all). Must be valid step names.
        continue_on_error: If True, continue to next step on failure.
        step_params: Per-step keyword arguments, e.g. {"clean_traces": {"line_id": ...}}.
    """
    requested = steps or STEP_ORDER
    params = step_params or {}

    # Create the run record
    run = PipelineRun(trigger=trigger, status=PipelineRunStatus.RUNNING)
    db.add(run)
    db.flush()  # get the ID

    has_failure = False

    for step_name in STEP_ORDER:
        if step_name not in requested:
            continue

        step_info = STEPS.get(step_name)
        if not step_info:
            continue

        result = PipelineStepResult(
            run_id=run.id,
            step_name=step_name,
            status=StepStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
        )
        db.add(result)
        db.commit()

        try:
            stats = step_info["fn"](db, **params.get(step_name, {}))
            result.status = StepStatus.COMPLETED
            result.stats = stats
            result.ended_at = datetime.now(timezone.utc)
            db.commit()
        except Exception:
            error_text = traceback.format_exc()
            # Roll back any partial writes the step left in the
            # session, then re-attach the result and persist its
            # FAILED status. Without this re-attach the rollback would
            # also revert the in-memory status update we just made.
            db.rollback()
            result.status = StepStatus.FAILED
            result.error_message = error_text
            result.ended_at = datetime.now(timezone.utc)
            db.add(result)
            db.commit()
            has_failure = True
            if not continue_on_error:
                break

    run.status = PipelineRunStatus.FAILED if has_failure else PipelineRunStatus.COMPLETED
    run.ended_at = datetime.now(timezone.utc)
    db.commit()

    # Refresh to load relationships
    db.refresh(run)
    return run
