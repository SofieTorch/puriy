"""Shared navbar for transit-lab notebooks."""

import os

import marimo as mo


def navbar() -> mo.Html:
    """Navigation menu to switch between transit-lab notebooks."""
    prefix = os.getenv("MARIMO_PATH_PREFIX", "")
    return mo.nav_menu(
        {
            f"{prefix}/tracks": "Tracks",
            f"{prefix}/lines": "Lines",
            f"{prefix}/reconstruction": "Reconstruction",
            f"{prefix}/routes": "Routes",
        },
        orientation="horizontal",
    )
