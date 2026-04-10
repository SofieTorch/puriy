"""Shared navbar for transit-lab notebooks."""

import marimo as mo


def navbar() -> mo.Html:
    """Navigation menu to switch between transit-lab notebooks."""
    return mo.nav_menu(
        {
            "/tracks": "Tracks",
            "/lines": "Lines",
            "/reconstruction": "Reconstruction",
            "/routes": "Routes",
        },
        orientation="horizontal",
    )
