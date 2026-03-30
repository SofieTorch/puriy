"""Shared styles and color palettes for transit-lab notebooks."""

GLOBAL_STYLES = """<style>
    label { white-space: nowrap; }
    .markdown p { margin: 0; padding: 0; }
    input[type="number"] { max-width: 5em; }
</style>"""

TRACK_COLORS: list[list[int]] = [
    [59, 130, 246],   # blue
    [34, 197, 94],    # green
    [234, 179, 8],    # amber
    [168, 85, 247],   # violet
    [236, 72, 153],   # pink
    [20, 184, 166],   # teal
]
