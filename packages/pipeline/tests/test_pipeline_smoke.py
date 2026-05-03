"""End-to-end smoke test for the full pipeline.

Runs `run_pipeline()` with the real `STEPS` registry against minimal
seeded data, with external dependencies (Valhalla `trace_match`,
Nominatim) mocked at the module boundary.

The bar is intentionally low: the pipeline must complete without
crashing, every requested step must land a `PipelineStepResult` row,
and the overall `PipelineRun.status` must reach a terminal state
(COMPLETED or FAILED — both are fine, since some steps may legitimately
have nothing to do on minimal seed data). What this catches is the
regression class of "step X broke when step Y changed its contract"
— the per-step unit test would still pass but the orchestration
glue between them is broken.

`clean_traces` is excluded from the run because it does heavy
Valhalla work that's awkward to mock end-to-end; per-step unit tests
should cover it directly when added.
"""

from datetime import datetime
from unittest.mock import patch

import pytest
from geoalchemy2.shape import from_shape
from shapely.geometry import LineString
from sqlalchemy.orm import Session

from database import (
    Line,
    LineStatus,
    PipelineRun,
    PipelineRunStatus,
    PipelineStepResult,
    Route,
    RouteEdge,
    RouteSource,
    RouteStatus,
    SessionStatus,
    Trip,
    TripPoint,
    TripSession,
    TripStatus,
)
from pipeline.runner import STEP_ORDER, run_pipeline


SMOKE_STEPS = [s for s in STEP_ORDER if s != "clean_traces"]


@pytest.fixture
def seeded_line(db: Session) -> Line:
    """A minimal APPROVED line with one COMPLETED session, one CLEAN
    trip with a few points, and one PENDING route + edge — enough that
    every downstream step finds at least one row to consider."""
    line = Line(name="Smoke Line", status=LineStatus.APPROVED)
    db.add(line)
    db.flush()

    session = TripSession(
        line_id=line.id, status=SessionStatus.COMPLETED,
        started_at=datetime.utcnow(), ended_at=datetime.utcnow(),
        last_activity_at=datetime.utcnow(),
    )
    db.add(session)
    db.flush()

    trip = Trip(session_id=session.id, line_id=line.id, status=TripStatus.CLEAN)
    db.add(trip)
    db.flush()

    base_ts = datetime(2026, 5, 1, 8, 0, 0)
    for i, (lon, lat) in enumerate([
        (-66.157, -17.393), (-66.156, -17.393), (-66.155, -17.393),
    ]):
        db.add(TripPoint(
            trip_id=trip.id, point_index=i,
            timestamp=datetime(2026, 5, 1, 8, i, 0),
            latitude=lat, longitude=lon,
        ))

    route = Route(
        line_id=line.id, version=1, ramal_label="main",
        source=RouteSource.COMPUTED, status=RouteStatus.PENDING,
        trip_count=1, fragment_index=0, fragment_count=1,
    )
    db.add(route)
    db.flush()
    db.add(RouteEdge(
        route_id=route.id, sequence=0, valhalla_edge_id=None, forward=True,
        path=from_shape(LineString([
            (-66.157, -17.393), (-66.155, -17.393),
        ]), srid=4326),
        confidence=1.0,
    ))
    db.commit()
    db.refresh(line)

    # Silence the unused-arg lint on `base_ts` — kept for readability.
    _ = base_ts
    return line


def test_full_pipeline_runs_to_terminal_state(
    db: Session, seeded_line: Line,
) -> None:
    """Run all steps (minus `clean_traces`) end-to-end against seeded
    data with Valhalla + Nominatim mocked. Asserts the runner records
    a `PipelineStepResult` for every requested step and finishes in
    either COMPLETED or FAILED — never stuck in RUNNING."""
    with (
        patch(
            "pipeline.steps.reconstruct_routes.trace_match",
            return_value=None,
        ),
        patch(
            "pipeline.steps.reconstruct_routes.resolve_endpoint_zones",
            return_value=[None, None],
        ),
    ):
        run = run_pipeline(
            db,
            trigger="smoke-test",
            steps=SMOKE_STEPS,
            continue_on_error=True,
        )

    assert run.status in {PipelineRunStatus.COMPLETED, PipelineRunStatus.FAILED}
    assert run.ended_at is not None
    assert run.trigger == "smoke-test"

    # Every requested step left a result behind — no silent skips.
    by_name = {s.step_name: s for s in run.steps}
    assert set(by_name.keys()) == set(SMOKE_STEPS)

    # No step is stuck in RUNNING — the runner should always advance to
    # a terminal status (the bug that runner tests caught).
    from database import StepStatus
    for step in run.steps:
        assert step.status != StepStatus.RUNNING, (
            f"step {step.step_name!r} stuck in RUNNING — "
            f"runner failed to record terminal state"
        )
        assert step.ended_at is not None


def test_smoke_run_persists_to_db_independently_of_session(
    db: Session, seeded_line: Line,
) -> None:
    """After the smoke run, a fresh query (post `expire_all`) finds the
    PipelineRun + all PipelineStepResults — the runner does its own
    commits, doesn't rely on the test session staying open."""
    with (
        patch("pipeline.steps.reconstruct_routes.trace_match",
              return_value=None),
        patch("pipeline.steps.reconstruct_routes.resolve_endpoint_zones",
              return_value=[None, None]),
    ):
        run = run_pipeline(
            db, steps=SMOKE_STEPS, continue_on_error=True,
        )

    run_id = run.id
    db.expire_all()

    fetched = db.get(PipelineRun, run_id)
    assert fetched is not None
    assert fetched.ended_at is not None

    from sqlalchemy import select
    persisted_steps = db.execute(
        select(PipelineStepResult)
        .where(PipelineStepResult.run_id == run_id)
    ).scalars().all()
    assert {s.step_name for s in persisted_steps} == set(SMOKE_STEPS)
