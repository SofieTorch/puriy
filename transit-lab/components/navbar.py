"""Shared navbar for transit-lab notebooks."""

import os

import marimo as mo


def navbar() -> mo.Html:
    """Navigation menu to switch between transit-lab notebooks."""
    prefix = os.getenv("MARIMO_PATH_PREFIX", "")
    return mo.nav_menu(
        {
            f"{prefix}/": "Overview",
            f"{prefix}/lines": "Lines",
            f"{prefix}/traces": "Traces",
            f"{prefix}/reconstruction": "Reconstruction",
            f"{prefix}/votes": "Votes",
            f"{prefix}/simulator": "Simulator",
            f"{prefix}/fares": "Fares",
        },
        orientation="horizontal",
    )
