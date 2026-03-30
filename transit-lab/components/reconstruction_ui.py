"""UI helpers for the route reconstruction workflow."""

from __future__ import annotations

from typing import TYPE_CHECKING

import marimo as mo

if TYPE_CHECKING:
    from geodata.reconstruction.base import ApproachInfo, ParamSpec


def build_param_panel(params: tuple[ParamSpec, ...]) -> mo.ui.dictionary:
    """Build a ``mo.ui.dictionary`` of number inputs from ParamSpec descriptors."""
    widgets: dict[str, mo.ui.number] = {}
    for p in params:
        kwargs: dict = {"value": p.default, "label": p.label}
        if p.min_val is not None:
            kwargs["start"] = p.min_val
        if p.max_val is not None:
            kwargs["stop"] = p.max_val
        if p.step is not None:
            kwargs["step"] = p.step
        widgets[p.name] = mo.ui.number(**kwargs)
    return mo.ui.dictionary(widgets)


def build_approach_selector(
    approaches: dict[str, tuple[ApproachInfo, object]],
    default_key: str = "dbscan",
) -> mo.ui.dropdown:
    """Build a dropdown to select a reconstruction approach."""
    options = {info.label: key for key, (info, _) in approaches.items()}
    # value must be one of the option labels (dict keys), not the internal key
    default_label = next(
        (info.label for key, (info, _) in approaches.items() if key == default_key),
        next(iter(options)),  # fallback to first option
    )
    return mo.ui.dropdown(
        options=options,
        value=default_label,
        label="Approach",
    )
