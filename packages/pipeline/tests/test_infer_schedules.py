"""Integration tests for the infer_schedules pipeline step."""

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from database import (
    DayBucket,
    Line,
    LineSchedule,
    LineStatus,
    SessionStatus,
    TripSession,
)
from pipeline.steps import infer_schedules


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _make_line(db: Session, name: str = "Test Line") -> Line:
    line = Line(name=name, status=LineStatus.APPROVED)
    db.add(line)
    db.commit()
    db.refresh(line)
    return line


def _seed_sessions(
    db: Session,
    line: Line,
    starts_utc: list[datetime],
) -> None:
    """Insert COMPLETED TripSessions for `line` at the given UTC starts."""
    for ts in starts_utc:
        session = TripSession(
            line_id=line.id,
            status=SessionStatus.COMPLETED,
            started_at=ts,
            ended_at=ts + timedelta(minutes=30),
            last_activity_at=ts + timedelta(minutes=30),
        )
        db.add(session)
    db.commit()


def _weekday_starts(start_utc: datetime, count: int, headway_min: int) -> list[datetime]:
    """`count` sessions starting at `start_utc`, spaced by `headway_min`."""
    return [start_utc + timedelta(minutes=headway_min * i) for i in range(count)]


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------

def test_pipeline_step_populates_three_buckets(db: Session) -> None:
    """30 sessions distributed across weekday/saturday/sunday → 3 rows."""
    line = _make_line(db, name="L1")
    # Monday 2026-05-04 10:00 UTC = 06:00 local. 30 starts at 10-min headway.
    weekday_starts = _weekday_starts(datetime(2026, 5, 4, 10, 0), 30, 10)
    # Saturday 2026-05-09 12:00 UTC = 08:00 local. 20 starts at 20-min headway.
    saturday_starts = _weekday_starts(datetime(2026, 5, 9, 12, 0), 20, 20)
    # Sunday 2026-05-10 14:00 UTC = 10:00 local. 15 starts at 30-min headway.
    sunday_starts = _weekday_starts(datetime(2026, 5, 10, 14, 0), 15, 30)
    _seed_sessions(db, line, weekday_starts + saturday_starts + sunday_starts)

    result_dict = infer_schedules(db)

    assert result_dict["lines_inferred"] == 1
    assert result_dict["schedule_rows_written"] == 3

    rows = db.execute(
        select(LineSchedule).where(LineSchedule.line_id == line.id)
    ).scalars().all()
    by_bucket = {r.day_bucket: r for r in rows}
    assert set(by_bucket) == {DayBucket.WEEKDAY, DayBucket.SATURDAY, DayBucket.SUNDAY}
    assert by_bucket[DayBucket.WEEKDAY].headway_min == 10
    assert by_bucket[DayBucket.SATURDAY].headway_min == 20
    assert by_bucket[DayBucket.SUNDAY].headway_min == 30


def test_pipeline_step_skips_lines_without_data(db: Session) -> None:
    """A line with no sessions yields zero schedule rows and no crash."""
    _make_line(db, name="Empty Line")
    result_dict = infer_schedules(db)
    assert result_dict["lines_inferred"] == 0
    assert result_dict["schedule_rows_written"] == 0


def test_pipeline_step_idempotent(db: Session) -> None:
    """Running the step twice yields the same row count, only inferred_at advances."""
    line = _make_line(db, name="L2")
    starts = _weekday_starts(datetime(2026, 5, 4, 10, 0), 30, 10)
    _seed_sessions(db, line, starts)

    infer_schedules(db)
    rows_first = db.execute(
        select(LineSchedule).where(LineSchedule.line_id == line.id)
    ).scalars().all()
    first_inferred_at = {r.day_bucket: r.inferred_at for r in rows_first}

    # Second run.
    infer_schedules(db)
    rows_second = db.execute(
        select(LineSchedule).where(LineSchedule.line_id == line.id)
    ).scalars().all()

    assert len(rows_second) == len(rows_first)  # no duplicates created
    for r in rows_second:
        assert r.inferred_at >= first_inferred_at[r.day_bucket]


def test_pipeline_step_only_completed_sessions(db: Session) -> None:
    """Cancelled / abandoned sessions are excluded from the inference."""
    line = _make_line(db, name="L3")
    # 30 completed sessions on a weekday.
    completed = _weekday_starts(datetime(2026, 5, 4, 10, 0), 30, 10)
    _seed_sessions(db, line, completed)
    # 20 cancelled sessions on a saturday — should NOT yield a SATURDAY row.
    for ts in _weekday_starts(datetime(2026, 5, 9, 12, 0), 20, 20):
        db.add(TripSession(
            line_id=line.id,
            status=SessionStatus.CANCELLED,
            started_at=ts,
            ended_at=ts + timedelta(minutes=10),
            last_activity_at=ts + timedelta(minutes=10),
        ))
    db.commit()

    infer_schedules(db)
    rows = db.execute(
        select(LineSchedule).where(LineSchedule.line_id == line.id)
    ).scalars().all()
    assert {r.day_bucket for r in rows} == {DayBucket.WEEKDAY}


def test_partial_bucket_data(db: Session) -> None:
    """A line with sessions only on weekdays produces only the WEEKDAY row."""
    line = _make_line(db, name="L4")
    starts = _weekday_starts(datetime(2026, 5, 4, 10, 0), 30, 10)
    _seed_sessions(db, line, starts)

    infer_schedules(db)

    rows = db.execute(
        select(LineSchedule).where(LineSchedule.line_id == line.id)
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].day_bucket == DayBucket.WEEKDAY
