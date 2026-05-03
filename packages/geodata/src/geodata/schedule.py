"""Inference of line service hours and headway from raw session timestamps.

Pure functions, no DB access — called by the pipeline step
`infer_schedules` and tested in isolation. Inputs are lists of
`TripSession.started_at` (naïve UTC `datetime`s, as stored by
`datetime.utcnow()`); outputs are `ScheduleInference` records keyed by
`DayBucket`.

The algorithm:

1. Convert each UTC timestamp to local Cochabamba time (UTC-4, no DST).
2. Bucket by day type: Sunday → SUNDAY, Saturday → SATURDAY,
   Mon-Fri → WEEKDAY. Holidays are treated as the day-of-week they
   fall on (v1 simplification).
3. Per bucket, compute service hours as the [P5, P95] range of
   start-times (robust to outliers). Need ≥ `min_sessions_total`
   datapoints for this to be published.
4. Per bucket, compute headway as the median of differences between
   consecutive starts within the same calendar day, filtering out
   gaps > `max_headway_minutes` (those are day-boundary crossings, not
   real headway). Need ≥ `min_sessions_per_day` datapoints on at least
   one day. The median is published only if the coefficient of
   variation (stddev/mean) of the differences is below
   `cv_threshold` — otherwise the cadence is deemed unreliable
   (RF-24).
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from enum import Enum
from typing import Optional

LOCAL_TZ = timezone(timedelta(hours=-4))  # America/La_Paz, no DST.

DEFAULT_MIN_SESSIONS_TOTAL = 10
DEFAULT_MIN_SESSIONS_PER_DAY = 5
DEFAULT_HEADWAY_CV_THRESHOLD = 0.5
DEFAULT_MAX_HEADWAY_MINUTES = 60


class DayBucket(str, Enum):
    """Three coarse day buckets sharing a typical service pattern."""

    WEEKDAY = "weekday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"


@dataclass(frozen=True)
class ScheduleInference:
    """Result of inferring schedule for a single day bucket."""

    service_start_at: Optional[time]
    service_end_at: Optional[time]
    headway_min: Optional[int]
    headway_cv: Optional[float]   # diagnostic, not persisted
    n_sessions: int
    n_valid_days: int


def utc_to_local(dt_utc: datetime) -> datetime:
    """Convert a naïve UTC datetime to aware local time (Cochabamba)."""
    if dt_utc.tzinfo is None:
        dt_utc = dt_utc.replace(tzinfo=timezone.utc)
    return dt_utc.astimezone(LOCAL_TZ)


def day_bucket_of(dt_local: datetime) -> DayBucket:
    """Bucket an aware-local datetime by day type."""
    weekday = dt_local.weekday()  # 0 = Monday, 6 = Sunday
    if weekday == 5:
        return DayBucket.SATURDAY
    if weekday == 6:
        return DayBucket.SUNDAY
    return DayBucket.WEEKDAY


def _percentile(sorted_values: list[float], p: float) -> float:
    """Linear-interpolation percentile (matches numpy default)."""
    if not sorted_values:
        raise ValueError("percentile of empty sequence")
    if len(sorted_values) == 1:
        return sorted_values[0]
    k = (len(sorted_values) - 1) * (p / 100)
    f = int(k)
    c = min(f + 1, len(sorted_values) - 1)
    if f == c:
        return sorted_values[f]
    return sorted_values[f] + (sorted_values[c] - sorted_values[f]) * (k - f)


def _time_to_seconds(t: time) -> int:
    return t.hour * 3600 + t.minute * 60 + t.second


def _seconds_to_time(s: float) -> time:
    s_int = int(round(s)) % (24 * 3600)
    h, rem = divmod(s_int, 3600)
    m, sec = divmod(rem, 60)
    return time(hour=h, minute=m, second=sec)


def infer_schedule_for_bucket(
    starts_local: list[datetime],
    *,
    min_sessions_total: int = DEFAULT_MIN_SESSIONS_TOTAL,
    min_sessions_per_day: int = DEFAULT_MIN_SESSIONS_PER_DAY,
    cv_threshold: float = DEFAULT_HEADWAY_CV_THRESHOLD,
    max_headway_minutes: int = DEFAULT_MAX_HEADWAY_MINUTES,
) -> ScheduleInference:
    """Compute service hours + headway for ONE day bucket.

    `starts_local` must be a list of aware datetimes already in local
    Cochabamba time (use `utc_to_local` upstream).
    """
    n = len(starts_local)
    if n == 0:
        return ScheduleInference(None, None, None, None, 0, 0)

    # ---- Service hours ----
    service_start: Optional[time] = None
    service_end: Optional[time] = None
    if n >= min_sessions_total:
        seconds = sorted(_time_to_seconds(dt.time()) for dt in starts_local)
        service_start = _seconds_to_time(_percentile(seconds, 5))
        service_end = _seconds_to_time(_percentile(seconds, 95))

    # ---- Headway ----
    by_day: dict[tuple[int, int, int], list[datetime]] = defaultdict(list)
    for dt in starts_local:
        by_day[(dt.year, dt.month, dt.day)].append(dt)

    diffs_min: list[float] = []
    n_valid_days = 0
    for day_starts in by_day.values():
        if len(day_starts) < min_sessions_per_day:
            continue
        n_valid_days += 1
        sorted_starts = sorted(day_starts)
        for prev, curr in zip(sorted_starts, sorted_starts[1:]):
            delta_min = (curr - prev).total_seconds() / 60
            if 0 < delta_min <= max_headway_minutes:
                diffs_min.append(delta_min)

    headway_min: Optional[int] = None
    headway_cv: Optional[float] = None
    if len(diffs_min) >= 2:
        median = statistics.median(diffs_min)
        mean = statistics.mean(diffs_min)
        stdev = statistics.stdev(diffs_min)
        cv = stdev / mean if mean > 0 else float("inf")
        headway_cv = cv
        if cv < cv_threshold:
            headway_min = int(round(median))

    return ScheduleInference(
        service_start_at=service_start,
        service_end_at=service_end,
        headway_min=headway_min,
        headway_cv=headway_cv,
        n_sessions=n,
        n_valid_days=n_valid_days,
    )


def infer_line_schedule(
    starts_utc: list[datetime],
    **kwargs,
) -> dict[DayBucket, ScheduleInference]:
    """Bucket UTC timestamps by local day type and run inference per bucket.

    Returns a dict with all three buckets present; an empty bucket
    yields a ScheduleInference with all-None metrics.
    """
    buckets: dict[DayBucket, list[datetime]] = {b: [] for b in DayBucket}
    for dt_utc in starts_utc:
        dt_local = utc_to_local(dt_utc)
        buckets[day_bucket_of(dt_local)].append(dt_local)
    return {
        bucket: infer_schedule_for_bucket(starts, **kwargs)
        for bucket, starts in buckets.items()
    }
