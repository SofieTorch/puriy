"""Shared pydeck map builders for transit-lab notebooks."""

from typing import Any

import pydeck as pdk

# Cochabamba city center
DEFAULT_LAT = -17.3935
DEFAULT_LON = -66.1570
DEFAULT_ZOOM = 13

TOOLTIP_STYLE = {
    "backgroundColor": "white",
    "color": "black",
    "fontFamily": "ui-monospace, monospace",
    "border": "1px solid #e5e7eb",
    "fontSize": "12px",
    "padding": "6px 10px",
}


def default_view_state(
    lat: float = DEFAULT_LAT,
    lon: float = DEFAULT_LON,
    zoom: int = DEFAULT_ZOOM,
    pitch: int = 0,
) -> pdk.ViewState:
    return pdk.ViewState(latitude=lat, longitude=lon, zoom=zoom, pitch=pitch, bearing=0)


def path_layer(
    data: list[dict[str, Any]],
    *,
    id: str = "paths",
    width: int = 4,
    pickable: bool = True,
    opacity: float = 0.8,
) -> pdk.Layer:
    """Standard PathLayer. Each item in data needs 'path' and 'color' keys."""
    return pdk.Layer(
        "PathLayer",
        data,
        id=id,
        get_path="path",
        get_color="color",
        get_width=width,
        width_min_pixels=2,
        pickable=pickable,
        auto_highlight=True,
        highlight_color=[255, 255, 100, 255],
        opacity=opacity,
    )


def scatter_layer(
    data: list[dict[str, Any]],
    *,
    id: str = "points",
    radius: int = 30,
    pickable: bool = True,
) -> pdk.Layer:
    """Standard ScatterplotLayer. Each item needs 'position' and 'color' keys."""
    return pdk.Layer(
        "ScatterplotLayer",
        data,
        id=id,
        get_position="position",
        get_fill_color="color",
        get_radius=radius,
        radius_min_pixels=3,
        pickable=pickable,
    )


def polygon_layer(
    data: list[dict[str, Any]],
    *,
    id: str = "polygons",
    opacity: float = 0.3,
    pickable: bool = True,
) -> pdk.Layer:
    """Standard PolygonLayer. Each item needs 'polygon' and 'color' keys."""
    return pdk.Layer(
        "PolygonLayer",
        data,
        id=id,
        get_polygon="polygon",
        get_fill_color="color",
        get_line_color=[80, 80, 80],
        get_line_width=2,
        line_width_min_pixels=1,
        filled=True,
        stroked=True,
        opacity=opacity,
        pickable=pickable,
    )


def deck(
    layers: list[pdk.Layer],
    *,
    view_state: pdk.ViewState | None = None,
    height: int = 500,
    tooltip_html: str | None = None,
) -> pdk.Deck:
    """Create a Deck with consistent defaults."""
    tooltip = None
    if tooltip_html:
        tooltip = {"html": tooltip_html, "style": TOOLTIP_STYLE}

    return pdk.Deck(
        map_style="light",
        map_provider="carto",
        initial_view_state=view_state or default_view_state(),
        layers=layers,
        height=height,
        tooltip=tooltip,
    )
