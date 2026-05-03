"""Unit tests for the helpers used by /directions/ to attach fare and
frequency to each bus leg."""

from datetime import datetime, time, timezone
from uuid import uuid4

import pytest
from geoalchemy2.shape import from_shape
from shapely.geometry import Polygon
from sqlalchemy.orm import Session

from database.models.fare import FareReport, FareZone
from database.models.line import Line, LineStatus, LineType
from database.models.line_schedule import DayBucket, LineSchedule

from services.line_metadata import (
    _today_bucket,
    current_headway_min,
    estimate_fare_bob,
)


# ------------------------------------------------------------------
# Day-bucket selection
# ------------------------------------------------------------------

def test_today_bucket_weekday() -> None:
    # Tuesday 2026-05-05 12:00 UTC = 08:00 local Tuesday → WEEKDAY.
    assert _today_bucket(datetime(2026, 5, 5, 12, 0, tzinfo=timezone.utc)) == DayBucket.WEEKDAY


def test_today_bucket_saturday() -> None:
    # Saturday 2026-05-09 12:00 UTC = 08:00 local Saturday.
    assert _today_bucket(datetime(2026, 5, 9, 12, 0, tzinfo=timezone.utc)) == DayBucket.SATURDAY


def test_today_bucket_sunday() -> None:
    # Sunday 2026-05-10 12:00 UTC = 08:00 local Sunday.
    assert _today_bucket(datetime(2026, 5, 10, 12, 0, tzinfo=timezone.utc)) == DayBucket.SUNDAY


def test_today_bucket_crosses_day_when_utc_lt_4() -> None:
    # Monday 02:00 UTC = Sunday 22:00 local — should be SUNDAY.
    assert _today_bucket(datetime(2026, 5, 4, 2, 0, tzinfo=timezone.utc)) == DayBucket.SUNDAY


# ------------------------------------------------------------------
# current_headway_min
# ------------------------------------------------------------------

@pytest.fixture
def line_with_schedule(db: Session):
    line = Line(name="L-meta", status=LineStatus.APPROVED)
    db.add(line)
    db.commit()
    db.refresh(line)
    db.add(LineSchedule(
        line_id=line.id, day_bucket=DayBucket.WEEKDAY,
        service_start_at=time(6, 0), service_end_at=time(22, 0),
        headway_min=8,
    ))
    db.add(LineSchedule(
        line_id=line.id, day_bucket=DayBucket.SUNDAY,
        service_start_at=time(8, 0), service_end_at=time(18, 0),
        headway_min=None,  # unreliable per RF-24
    ))
    db.commit()
    return line


def test_current_headway_min_returns_today_bucket_value(
    db: Session, line_with_schedule: Line,
) -> None:
    """Forcing 'now' to a Tuesday picks WEEKDAY → headway_min=8."""
    weekday_now = datetime(2026, 5, 5, 12, 0, tzinfo=timezone.utc)
    assert current_headway_min(db, line_with_schedule.id, now=weekday_now) == 8


def test_current_headway_min_returns_none_when_unreliable(
    db: Session, line_with_schedule: Line,
) -> None:
    """Sunday bucket exists but headway is null (RF-24) — None propagates."""
    sunday_now = datetime(2026, 5, 10, 12, 0, tzinfo=timezone.utc)
    assert current_headway_min(db, line_with_schedule.id, now=sunday_now) is None


def test_current_headway_min_returns_none_when_no_bucket(
    db: Session, line_with_schedule: Line,
) -> None:
    """No SATURDAY row → None."""
    saturday_now = datetime(2026, 5, 9, 12, 0, tzinfo=timezone.utc)
    assert current_headway_min(db, line_with_schedule.id, now=saturday_now) is None


def test_current_headway_min_returns_none_for_unknown_line(db: Session) -> None:
    assert current_headway_min(db, uuid4()) is None


# ------------------------------------------------------------------
# estimate_fare_bob
# ------------------------------------------------------------------

@pytest.fixture
def micro_line_with_reports(db: Session) -> Line:
    line = Line(name="L-micro", status=LineStatus.APPROVED, line_type=LineType.MICRO)
    db.add(line)
    db.commit()
    db.refresh(line)
    for amount in (2.0, 2.5, 3.0):
        db.add(FareReport(
            line_id=line.id, device_id="test-device-abc",
            amount_bob=amount,
            boarding_latitude=-17.39, boarding_longitude=-66.16,
            alighting_latitude=-17.40, alighting_longitude=-66.17,
        ))
    db.commit()
    return line


def test_estimate_fare_micro_returns_average(
    db: Session, micro_line_with_reports: Line,
) -> None:
    fare = estimate_fare_bob(
        db, micro_line_with_reports.id,
        boarding_lat=-17.39, boarding_lon=-66.16,
        alighting_lat=-17.40, alighting_lon=-66.17,
    )
    assert fare == 2.5


def test_estimate_fare_unknown_line_returns_none(db: Session) -> None:
    fare = estimate_fare_bob(
        db, uuid4(),
        boarding_lat=-17.39, boarding_lon=-66.16,
        alighting_lat=-17.40, alighting_lon=-66.17,
    )
    assert fare is None


def test_estimate_fare_micro_no_reports_returns_none(db: Session) -> None:
    line = Line(name="L-empty", status=LineStatus.APPROVED, line_type=LineType.MICRO)
    db.add(line)
    db.commit()
    db.refresh(line)
    assert estimate_fare_bob(
        db, line.id,
        boarding_lat=-17.39, boarding_lon=-66.16,
        alighting_lat=-17.40, alighting_lon=-66.17,
    ) is None


def test_estimate_fare_trufi_uses_zone_pair(db: Session) -> None:
    """Trufi line — fare is averaged over the resolved zone-pair, symmetric."""
    # Two square zones side-by-side near Cochabamba (lon, lat).
    cala_cala = from_shape(Polygon([
        (-66.18, -17.40), (-66.17, -17.40),
        (-66.17, -17.39), (-66.18, -17.39), (-66.18, -17.40),
    ]), srid=4326)
    centro = from_shape(Polygon([
        (-66.16, -17.40), (-66.15, -17.40),
        (-66.15, -17.39), (-66.16, -17.39), (-66.16, -17.40),
    ]), srid=4326)
    cala_zone = FareZone(name="Cala Cala test", boundary=cala_cala)
    centro_zone = FareZone(name="Centro test", boundary=centro)
    db.add_all([cala_zone, centro_zone])
    db.commit()
    db.refresh(cala_zone)
    db.refresh(centro_zone)

    line = Line(name="L-trufi", status=LineStatus.APPROVED, line_type=LineType.TRUFI)
    db.add(line)
    db.commit()
    db.refresh(line)

    # Two reports: one in each direction. Average should be 4.0.
    db.add(FareReport(
        line_id=line.id, device_id="test-device-abc",
        amount_bob=3.5,
        boarding_latitude=-17.395, boarding_longitude=-66.175,
        alighting_latitude=-17.395, alighting_longitude=-66.155,
        boarding_zone_id=cala_zone.id, alighting_zone_id=centro_zone.id,
    ))
    db.add(FareReport(
        line_id=line.id, device_id="other-device-xyz",
        amount_bob=4.5,
        boarding_latitude=-17.395, boarding_longitude=-66.155,
        alighting_latitude=-17.395, alighting_longitude=-66.175,
        boarding_zone_id=centro_zone.id, alighting_zone_id=cala_zone.id,
    ))
    db.commit()

    fare = estimate_fare_bob(
        db, line.id,
        boarding_lat=-17.395, boarding_lon=-66.175,
        alighting_lat=-17.395, alighting_lon=-66.155,
    )
    assert fare == 4.0


def test_estimate_fare_trufi_unresolvable_zones_returns_none(db: Session) -> None:
    """Trufi line without zones touching the coords → None."""
    line = Line(name="L-trufi-noz", status=LineStatus.APPROVED, line_type=LineType.TRUFI)
    db.add(line)
    db.commit()
    db.refresh(line)
    assert estimate_fare_bob(
        db, line.id,
        boarding_lat=0.0, boarding_lon=0.0,
        alighting_lat=0.1, alighting_lon=0.1,
    ) is None
