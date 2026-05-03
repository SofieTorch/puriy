"""Infer service hours and headway per (line, day_bucket).

For each APPROVED line, gather all completed/processed TripSession
start timestamps and run the schedule inference (see
`geodata.schedule.infer_line_schedule`). Persist the result as up to
three `LineSchedule` rows (one per `DayBucket`).

This step is independent of the others — it can run after
`reconstruct_routes` for orderly logging but doesn't actually depend
on routes existing. Idempotent: re-running over the same data yields
the same values, only `inferred_at` advances.
"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from database import (
    Line,
    LineStatus,
    SessionStatus,
    TripSession,
)
from database.models import LineSchedule
from geodata.schedule import infer_line_schedule


def execute(db: Session) -> dict:
    lines = db.execute(
        select(Line).where(Line.status == LineStatus.APPROVED)
    ).scalars().all()

    now = datetime.utcnow()
    lines_inferred = 0
    rows_written = 0

    for line in lines:
        starts = db.execute(
            select(TripSession.started_at).where(
                TripSession.line_id == line.id,
                TripSession.status == SessionStatus.COMPLETED,
                TripSession.started_at.is_not(None),
            )
        ).scalars().all()

        if not starts:
            continue

        per_bucket = infer_line_schedule(starts)
        line_had_data = False

        for bucket, result in per_bucket.items():
            # Skip empty buckets — don't write rows that carry no signal.
            if result.n_sessions == 0:
                continue
            line_had_data = True

            existing = db.get(LineSchedule, (line.id, bucket))
            if existing is None:
                existing = LineSchedule(line_id=line.id, day_bucket=bucket)
                db.add(existing)
            existing.service_start_at = result.service_start_at
            existing.service_end_at = result.service_end_at
            existing.headway_min = result.headway_min
            existing.inferred_at = now
            rows_written += 1

        if line_had_data:
            lines_inferred += 1

    db.commit()

    return {
        "lines_inferred": lines_inferred,
        "schedule_rows_written": rows_written,
    }
