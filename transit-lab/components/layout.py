"""Shared layout helpers for transit-lab notebooks."""

import marimo as mo


def page_header(title: str, subtitle: str = "") -> mo.Html:
    sub = f"\n<p style='color: #6b7280; margin-top: 4px;'>{subtitle}</p>" if subtitle else ""
    return mo.md(f"# {title}{sub}")


def stat_row(stats: list[tuple[str, str | int | float]]) -> mo.Html:
    """Render a horizontal row of stat badges."""
    items = [mo.stat(label=label, value=str(value)) for label, value in stats]
    return mo.hstack(items, gap=1, justify="start")


def section(title: str, *content: mo.Html) -> mo.Html:
    """Wrap content in a titled section."""
    header = mo.md(f"### {title}")
    return mo.vstack([header, *content], gap=0.5)


def control_bar(*controls: mo.Html) -> mo.Html:
    """Horizontal bar of controls with consistent spacing."""
    return mo.hstack(list(controls), gap=1, justify="start", align="end")
