"""Tests for `services.detour_confidence.compute_confidence_pct`.

The formula combines a linear time decay (`days_since_confirmed`) with
a log-shaped corroboration boost (`confirmed_count`). These tests pin
the headline reference points documented in the helper's docstring so
any change to the formula produces a visible, reviewable diff.
"""

import pytest

from services.detour_confidence import (
    DECAY_HORIZON_DAYS,
    compute_confidence_pct,
)


# ------------------------------------------------------------------
# Bounds + reference points (from the helper's docstring)
# ------------------------------------------------------------------

@pytest.mark.parametrize(
    "days, count, expected",
    [
        (0, 1, 50),    # fresh report, single reporter — no corroboration
        (0, 3, 68),    # fresh, 3 confirmers — meaningful boost
        (0, 10, 88),   # fresh, broad confirmation
        (7, 1, 25),    # week old, no corroboration
        (7, 10, 44),   # week old but well-confirmed
    ],
)
def test_reference_points(days: int, count: int, expected: int) -> None:
    """The formula's documented reference points stay stable so the
    thesis can quote them and the UI's confidence chip stays
    predictable across releases."""
    assert compute_confidence_pct(days, count) == expected


def test_caps_at_zero_after_decay_horizon(
) -> None:
    """At and past the decay horizon, confidence is 0 regardless of
    confirmations — a 14-day-old report shouldn't show as believable
    even with 100 confirmers because the underlying *event* may have
    resolved."""
    assert compute_confidence_pct(DECAY_HORIZON_DAYS, 1) == 0
    assert compute_confidence_pct(DECAY_HORIZON_DAYS, 100) == 0
    assert compute_confidence_pct(DECAY_HORIZON_DAYS + 5, 100) == 0


def test_negative_days_clamps_to_fresh(
) -> None:
    """Defensive: clock skew (`last_confirmed_at` slightly in the
    future) shouldn't produce >100 %; clamps to the freshest case."""
    assert compute_confidence_pct(-1, 1) == 50
    assert compute_confidence_pct(-1, 10) == 88


def test_zero_confirmers_is_treated_like_one(
) -> None:
    """`confirmed_count=0` shouldn't crash the log term and shouldn't
    boost above the single-reporter baseline."""
    assert compute_confidence_pct(0, 0) == compute_confidence_pct(0, 1)


# ------------------------------------------------------------------
# Monotonicity properties
# ------------------------------------------------------------------

def test_confidence_decreases_monotonically_with_age(
) -> None:
    """Holding `confirmed_count` fixed, confidence must never go up
    as the detour ages."""
    prev = 101
    for days in range(0, DECAY_HORIZON_DAYS + 2):
        current = compute_confidence_pct(days, 5)
        assert current <= prev, (
            f"confidence went up between day {days-1} ({prev}) "
            f"and day {days} ({current})"
        )
        prev = current


def test_confidence_increases_monotonically_with_confirmations(
) -> None:
    """Holding `days` fixed, more confirmations must never reduce
    confidence."""
    prev = -1
    for count in range(1, 50):
        current = compute_confidence_pct(0, count)
        assert current >= prev, (
            f"confidence went down between {count-1} confirmers "
            f"({prev}) and {count} confirmers ({current})"
        )
        prev = current


def test_corroboration_boost_has_diminishing_returns(
) -> None:
    """The log-shaped boost means each additional confirmer matters
    less than the previous one. Going from 1→3 confirmers should
    produce a bigger jump than 18→20."""
    early = compute_confidence_pct(0, 3) - compute_confidence_pct(0, 1)
    late = compute_confidence_pct(0, 20) - compute_confidence_pct(0, 18)
    assert early > late, (
        f"early jump ({early}) should exceed late jump ({late}) — "
        f"diminishing returns is the whole point of the log shape"
    )
