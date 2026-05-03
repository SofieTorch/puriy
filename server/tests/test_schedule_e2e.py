"""End-to-end test for the schedule inference flow.

Seeds realistic per-bucket TripSession data, runs the pipeline step
directly, then verifies the inferred schedule via the public
`GET /lines/{id}` endpoint.
"""

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from database.models.line import Line, LineStatus
from database.models.trip import SessionStatus, TripSession
from pipeline.steps import infer_schedules


@pytest.fixture
def line_under_test(db: Session) -> Line:
    line = Line(name="L-E2E", status=LineStatus.APPROVED)
    db.add(line)
    db.commit()
    db.refresh(line)
    return line


def _seed_session(db: Session, line_id, started_at_utc: datetime) -> None:
    session = TripSession(
        line_id=line_id,
        status=SessionStatus.COMPLETED,
        started_at=started_at_utc,
        ended_at=started_at_utc + timedelta(minutes=30),
        last_activity_at=started_at_utc + timedelta(minutes=30),
    )
    db.add(session)


def test_infer_pipeline_to_api(
    client: TestClient, db: Session, line_under_test: Line,
) -> None:
    """Seed weekday + saturday + sunday data, run pipeline, hit API."""
    line_id = line_under_test.id

    # Weekday 2026-05-04 (Monday): 30 sessions starting 10:00 UTC = 06:00
    # local, headway 8 min → confiable.
    base_weekday = datetime(2026, 5, 4, 10, 0)
    for i in range(30):
        _seed_session(db, line_id, base_weekday + timedelta(minutes=8 * i))

    # Saturday 2026-05-09: 20 sessions starting 11:00 UTC = 07:00 local,
    # headway 12 min → confiable.
    base_saturday = datetime(2026, 5, 9, 11, 0)
    for i in range(20):
        _seed_session(db, line_id, base_saturday + timedelta(minutes=12 * i))

    # Sunday 2026-05-10: 12 sessions with alternating gaps of 5 / 25 min
    # → CV alta → headway no confiable, pero service hours sí.
    base_sunday = datetime(2026, 5, 10, 12, 0)
    cur = base_sunday
    deltas = [5, 25] * 6
    _seed_session(db, line_id, cur)
    for d in deltas:
        cur = cur + timedelta(minutes=d)
        _seed_session(db, line_id, cur)

    db.commit()

    # Run the pipeline step directly.
    summary = infer_schedules(db)
    assert summary["lines_inferred"] == 1
    assert summary["schedule_rows_written"] == 3

    # Hit the API.
    resp = client.get(f"/lines/{line_id}")
    assert resp.status_code == 200
    body = resp.json()
    by_bucket = {s["day_bucket"]: s for s in body["schedules"]}

    weekday = by_bucket["weekday"]
    assert weekday["headway_min"] == 8
    assert weekday["service_start_at"].startswith("06:")

    saturday = by_bucket["saturday"]
    assert saturday["headway_min"] == 12
    assert saturday["service_start_at"].startswith("07:")

    sunday = by_bucket["sunday"]
    # CV alta → frecuencia descartada (RF-24); horario de servicio se
    # mantiene.
    assert sunday["headway_min"] is None
    assert sunday["service_start_at"] is not None
