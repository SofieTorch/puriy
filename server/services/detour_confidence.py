"""Compute the displayed confidence percentage for an active detour.

Earlier the formula was a pure linear time decay (`100 - days*100/7`)
that ignored `Detour.confirmed_count` entirely — even though every
endpoint that confirmed a detour incremented that field. The thesis
talks about "validación colaborativa" so the surfaced confidence
should actually reflect how many independent users have confirmed.

The new formula is the product of two factors:

- `time_factor` — linear decay from 1.0 (fresh) to 0.0 (≥14 days
  since `last_confirmed_at`). 14 days instead of the old 7 because a
  recent confirmation should be able to keep the detour believable
  past one week.
- `corroboration_factor` — log-shaped boost from `confirmed_count`.
  Bottoms out at 0.5 with `confirmed_count=1` (the original report
  alone — one user's word) and asymptotes toward 1.0 with more
  confirmations. The log shape captures diminishing returns: going
  from 1 → 3 confirmations matters more than 18 → 20.

Concrete reference points:
- Fresh report, 1 confirmer (the reporter): 50 %
- Fresh report, 3 confirmers: ~68 %
- Fresh report, 10 confirmers: ~88 %
- 7-day-old, 1 confirmer: 25 %
- 7-day-old, 10 confirmers: ~44 %
- 14-day-old: always 0 %
"""

import math

# Days after which the time factor decays to zero. A confirmation
# extends the clock because `last_confirmed_at` is updated on every
# vote (see `Detour.last_confirmed_at`).
DECAY_HORIZON_DAYS = 14

# Number of confirmations that produce ~96 % of the corroboration
# boost (the rest is asymptotic). Picked to make the log curve land
# at sensible values across the realistic range (1–30).
CORROBORATION_SATURATION = 20


def compute_confidence_pct(
    days_since_confirmed: int, confirmed_count: int,
) -> int:
    """Confidence in `[0, 100]` decaying with time + rising with votes."""
    time_factor = max(
        0.0, min(1.0, 1.0 - days_since_confirmed / DECAY_HORIZON_DAYS),
    )
    corroboration = math.log1p(max(0, confirmed_count - 1)) / math.log1p(
        CORROBORATION_SATURATION,
    )
    corroboration_factor = min(1.0, 0.5 + 0.5 * corroboration)
    return max(0, min(100, int(round(100 * time_factor * corroboration_factor))))
