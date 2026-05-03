"""Tests for the schedule inference algorithm."""

from datetime import datetime, time, timedelta

from geodata.schedule import (
    LOCAL_TZ,
    DayBucket,
    ScheduleInference,
    day_bucket_of,
    infer_line_schedule,
    infer_schedule_for_bucket,
    utc_to_local,
)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _local(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    """Aware local datetime in Cochabamba TZ."""
    return datetime(year, month, day, hour, minute, tzinfo=LOCAL_TZ)


def _utc(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    """Naïve UTC datetime, like `datetime.utcnow()` returns."""
    return datetime(year, month, day, hour, minute)


def _regular_day(date: datetime, start_h: int, end_h: int, headway_min: int) -> list[datetime]:
    """A day's worth of session starts at constant headway."""
    starts = []
    cur = date.replace(hour=start_h, minute=0)
    end = date.replace(hour=end_h, minute=0)
    while cur <= end:
        starts.append(cur)
        cur = cur + timedelta(minutes=headway_min)
    return starts


# ==================================================================
# Single-bucket: infer_schedule_for_bucket
# ==================================================================

def test_empty_input_returns_all_none() -> None:
    result = infer_schedule_for_bucket([])
    assert result == ScheduleInference(None, None, None, None, 0, 0)


def test_few_sessions_only_no_metrics() -> None:
    """Below min_sessions_total → service hours stay None."""
    starts = [_local(2026, 5, 4, 8), _local(2026, 5, 4, 9), _local(2026, 5, 4, 10)]
    result = infer_schedule_for_bucket(starts)
    assert result.service_start_at is None
    assert result.service_end_at is None
    assert result.headway_min is None  # below per-day threshold too
    assert result.n_sessions == 3


def test_regular_headway_is_confident() -> None:
    """30 sessions at exactly 10-min intervals → headway_min = 10, CV ≈ 0."""
    monday = _local(2026, 5, 4, 0)  # 2026-05-04 is a Monday
    starts = []
    cur = monday.replace(hour=6)
    for _ in range(30):
        starts.append(cur)
        cur += timedelta(minutes=10)
    result = infer_schedule_for_bucket(starts)
    assert result.headway_min == 10
    assert result.headway_cv is not None and result.headway_cv < 0.01


def test_irregular_headway_is_unreliable() -> None:
    """Alternating 5-min and 25-min gaps → CV high → headway_min = None."""
    monday = _local(2026, 5, 4, 6)
    starts = [monday]
    deltas = [5, 25] * 15
    for d in deltas:
        starts.append(starts[-1] + timedelta(minutes=d))
    result = infer_schedule_for_bucket(starts)
    assert result.headway_min is None
    assert result.headway_cv is not None and result.headway_cv > 0.5


def test_service_hours_robust_to_outliers() -> None:
    """One stray 03:00 start should not drag service_start_at down to 03:00."""
    monday = _local(2026, 5, 4, 0)
    starts = []
    # 30 sessions between 06:00 and 22:00
    for h in range(6, 22):
        for m in (0, 30):
            starts.append(monday.replace(hour=h, minute=m))
    starts.append(monday.replace(hour=3, minute=0))  # outlier
    result = infer_schedule_for_bucket(starts)
    assert result.service_start_at is not None
    # P5 of 33 values puts the cutoff well above 03:00
    assert result.service_start_at >= time(5, 0)
    assert result.service_end_at is not None and result.service_end_at >= time(20, 0)


def test_max_headway_filter_excludes_day_gaps() -> None:
    """Gaps > 60 min between days don't count as headway."""
    monday = _local(2026, 5, 4, 6)
    tuesday = _local(2026, 5, 5, 6)
    # 10 sessions monday at 5-min headway, 10 sessions tuesday at 5-min headway
    monday_starts = [monday + timedelta(minutes=5 * i) for i in range(10)]
    tuesday_starts = [tuesday + timedelta(minutes=5 * i) for i in range(10)]
    result = infer_schedule_for_bucket(monday_starts + tuesday_starts)
    # The big gap between monday-end and tuesday-start (~22h) was filtered.
    assert result.headway_min == 5
    assert result.n_valid_days == 2


# ==================================================================
# Bucketing: day_bucket_of and infer_line_schedule
# ==================================================================

def test_weekday_dt_goes_to_weekday_bucket() -> None:
    # 2026-05-05 is a Tuesday.
    assert day_bucket_of(_local(2026, 5, 5, 12)) == DayBucket.WEEKDAY


def test_saturday_dt_goes_to_saturday_bucket() -> None:
    # 2026-05-09 is a Saturday.
    assert day_bucket_of(_local(2026, 5, 9, 12)) == DayBucket.SATURDAY


def test_sunday_dt_goes_to_sunday_bucket() -> None:
    # 2026-05-10 is a Sunday.
    assert day_bucket_of(_local(2026, 5, 10, 12)) == DayBucket.SUNDAY


def test_buckets_are_independent() -> None:
    """Sessions in distinct buckets produce distinct results per bucket."""
    # Weekday: 30 sessions at 10-min headway.
    weekday_utc = [_utc(2026, 5, 4, 10) + timedelta(minutes=10 * i) for i in range(30)]
    # Saturday: 30 sessions at 20-min headway.
    saturday_utc = [_utc(2026, 5, 9, 11) + timedelta(minutes=20 * i) for i in range(30)]
    by_bucket = infer_line_schedule(weekday_utc + saturday_utc)
    assert by_bucket[DayBucket.WEEKDAY].headway_min == 10
    assert by_bucket[DayBucket.SATURDAY].headway_min == 20
    assert by_bucket[DayBucket.SUNDAY].n_sessions == 0


def test_utc_to_local_changes_day_when_hour_lt_4() -> None:
    """A session at 02:00 UTC on Monday is 22:00 Sunday local (UTC-4)."""
    utc_dt = _utc(2026, 5, 4, 2, 0)  # Monday 02:00 UTC
    local_dt = utc_to_local(utc_dt)
    # 02:00 UTC - 4h = -2:00 = 22:00 prior day (Sunday).
    assert local_dt.hour == 22
    assert local_dt.weekday() == 6  # Sunday
    assert day_bucket_of(local_dt) == DayBucket.SUNDAY


def test_timezone_conversion_in_service_hours() -> None:
    """A session at 10:00 UTC should appear as 06:00 local in service_start_at."""
    # 30 sessions at 10:00 UTC + 10-min increments → 06:00–10:50 local.
    starts_utc = [_utc(2026, 5, 4, 10) + timedelta(minutes=10 * i) for i in range(30)]
    by_bucket = infer_line_schedule(starts_utc)
    weekday = by_bucket[DayBucket.WEEKDAY]
    assert weekday.service_start_at is not None
    assert weekday.service_start_at.hour == 6  # 10 UTC - 4 = 06 local
