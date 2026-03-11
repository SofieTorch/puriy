"""Shared navbar for transit-lab notebooks."""

import marimo as mo


def navbar() -> mo.Html:
    """Navigation menu to switch between Tracks and Lines notebooks."""
    return mo.nav_menu(
        {
            "/tracks": "Tracks",
            "/lines": "Lines",
        },
        orientation="horizontal",
    )
