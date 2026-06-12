"""Shared pydeck map builders for transit-lab notebooks."""

from typing import Any

import pydeck as pdk
from pydeck.data_utils import compute_view

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


# Keys whose values hold coordinates, in the data dicts the layers consume.
# 'path'/'polygon' hold a list of [lon, lat]; 'position' holds a single [lon, lat].
_COORD_KEYS = ("path", "polygon", "contour", "position")


def _extract_points(
    datasets: tuple[list[dict[str, Any]], ...],
    coord_keys: tuple[str, ...],
) -> list[list[float]]:
    """Flatten every [lon, lat] coordinate found across the given layer datasets."""
    points: list[list[float]] = []
    for data in datasets:
        for item in data:
            for key in coord_keys:
                value = item.get(key)
                if value is None:
                    continue
                if key == "position":
                    points.append(list(value[:2]))
                else:
                    points.extend(list(p[:2]) for p in value)
    return points


def fit_view_state(
    *datasets: list[dict[str, Any]],
    pitch: int = 0,
    padding: float = 0.4,
    max_zoom: float = 17.0,
    min_zoom: float = 1.0,
    coord_keys: tuple[str, ...] = _COORD_KEYS,
) -> pdk.ViewState:
    """Compute a view state that frames all coordinates in the given datasets.

    Pass the same ``data`` lists you hand to the layer builders (path/scatter/
    polygon). The whole geometry is centered and zoomed to fill the frame, so a
    long route no longer reads as a tiny thread on a city-wide map. The map stays
    geographically accurate — this only sets the camera, it does not distort.

    ``padding`` is a zoom-level margin subtracted from the tight fit (0.4 ≈ ~30%
    breathing room around the bounds; raise it for more margin). Falls back to the
    default Cochabamba view when no coordinates are found.
    """
    points = _extract_points(datasets, coord_keys)
    if not points:
        return default_view_state(pitch=pitch)

    view = compute_view(points)
    view.zoom = max(min_zoom, min(float(view.zoom) - padding, max_zoom))
    view.pitch = pitch
    view.bearing = 0
    return view


def path_layer(
    data: list[dict[str, Any]],
    *,
    id: str = "paths",
    width: int = 4,
    width_min_pixels: int = 2,
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
        width_min_pixels=width_min_pixels,
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


def _scale_lines(layer: pdk.Layer, line_factor: float, dot_factor: float) -> pdk.Layer:
    """Scale path/polygon strokes by ``line_factor`` and point radii by ``dot_factor``."""
    kind = getattr(layer, "type", "")
    if kind == "PathLayer":
        if isinstance(getattr(layer, "get_width", None), (int, float)):
            layer.get_width = layer.get_width * line_factor
        if isinstance(getattr(layer, "width_min_pixels", None), (int, float)):
            layer.width_min_pixels = layer.width_min_pixels * line_factor
    elif kind == "ScatterplotLayer":
        if isinstance(getattr(layer, "get_radius", None), (int, float)):
            layer.get_radius = layer.get_radius * dot_factor
        if isinstance(getattr(layer, "radius_min_pixels", None), (int, float)):
            layer.radius_min_pixels = layer.radius_min_pixels * dot_factor
    elif kind == "PolygonLayer":
        if isinstance(getattr(layer, "get_line_width", None), (int, float)):
            layer.get_line_width = layer.get_line_width * line_factor
        if isinstance(getattr(layer, "line_width_min_pixels", None), (int, float)):
            layer.line_width_min_pixels = layer.line_width_min_pixels * line_factor
    return layer


def deck(
    layers: list[pdk.Layer],
    *,
    view_state: pdk.ViewState | None = None,
    height: int = 500,
    tooltip_html: str | None = None,
    fit: bool = False,
    fit_padding: float = 0.4,
    line_scale: float = 1.0,
    dot_scale: float = 1.0,
    fixed_height: bool = False,
) -> pdk.Deck:
    """Create a Deck with consistent defaults.

    Set ``fit=True`` to auto-frame the camera on the layers' geometry (the whole
    route fills the frame instead of being a tiny thread); an explicit
    ``view_state`` always takes precedence over ``fit``. ``line_scale`` multiplies
    path/polygon stroke widths and ``dot_scale`` multiplies point (scatter) radii
    (1.0 = unchanged) — wire them to sliders to tune thickness for screenshots.

    marimo renders pydeck via ``_repr_html_``, which hard-codes a 500px-tall
    iframe and so ignores ``height``. Pass ``fixed_height=True`` to actually honor
    ``height``: the map is rendered through the same iframe path with the real
    height and returned as a marimo ``Html``.
    """
    if line_scale != 1.0 or dot_scale != 1.0:
        layers = [_scale_lines(layer, line_scale, dot_scale) for layer in layers]

    if view_state is None and fit:
        datasets = [layer.data for layer in layers if getattr(layer, "data", None)]
        view_state = fit_view_state(*datasets, padding=fit_padding)

    tooltip = None
    if tooltip_html:
        tooltip = {"html": tooltip_html, "style": TOOLTIP_STYLE}

    deck_obj = pdk.Deck(
        map_style="light",
        map_provider="carto",
        initial_view_state=view_state or default_view_state(),
        layers=layers,
        height=height,
        tooltip=tooltip,
    )

    if fixed_height:
        import marimo as mo

        html = deck_obj.to_html(notebook_display=True, iframe_height=height)
        return mo.Html(getattr(html, "data", ""))
    return deck_obj
