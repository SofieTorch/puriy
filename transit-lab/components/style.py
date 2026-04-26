"""Shared colors, palettes, and styling constants for transit-lab notebooks."""

COLORS = [
    [59, 130, 246],   # blue
    [34, 197, 94],    # green
    [234, 179, 8],    # amber
    [168, 85, 247],   # violet
    [236, 72, 153],   # pink
    [20, 184, 166],   # teal
    [249, 115, 22],   # orange
    [99, 102, 241],   # indigo
]

STATUS_COLORS = {
    "approved": [34, 197, 94],
    "pending": [234, 179, 8],
    "merged": [156, 163, 175],
    "confirmed": [34, 197, 94],
    "superseded": [156, 163, 175],
    "in_progress": [59, 130, 246],
    "completed": [34, 197, 94],
    "cancelled": [239, 68, 68],
    "abandoned": [156, 163, 175],
    "discarded": [107, 114, 128],
}


def confidence_color(value: float, alpha: int = 180) -> list[int]:
    """Map a confidence value (0.0–1.0) to an RGB+A color.

    Green (high confidence) → Red (low confidence).
    """
    r = int(255 * (1 - value))
    g = int(200 * value)
    b = 60
    return [r, g, b, alpha]


def vote_ratio_color(votes_for: int, votes_against: int, alpha: int = 180) -> list[int]:
    """Map a vote ratio to an RGB+A color.

    Green (all approve) → Red (all reject). Grey if no votes.
    """
    total = votes_for + votes_against
    if total == 0:
        return [156, 163, 175, alpha]
    ratio = votes_for / total
    return confidence_color(ratio, alpha)


def cycle_color(index: int) -> list[int]:
    """Pick a color from the palette by index (wraps around)."""
    return list(COLORS[index % len(COLORS)])
