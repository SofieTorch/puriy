"""Reusable Folium map builders for transit-lab notebooks."""

import folium
from branca.element import Element
from folium.plugins import Draw

_EXPORT_BUTTON_CSS = """<style>
    #export {{
        background-color: {bg_color} !important;
        color: white !important;
        padding: 6px 16px !important;
        border-radius: 4px !important;
        font-weight: 600 !important;
        font-size: 13px !important;
        text-decoration: none !important;
        box-shadow: 0 2px 4px rgba(0,0,0,0.2) !important;
        z-index: 1000 !important;
        position: absolute !important;
        top: 12px !important;
        right: 12px !important;
        left: auto !important;
        bottom: auto !important;
    }}
    #export:hover {{
        background-color: {hover_color} !important;
    }}
</style>"""

DEFAULT_CENTER = [-17.3895, -66.1568]
DEFAULT_ZOOM = 13


def create_draw_map(
    *,
    export_filename: str = "export.geojson",
    draw_polyline: bool = False,
    draw_polygon: bool = False,
    draw_rectangle: bool = False,
    edit: bool = False,
    button_color: str = "#22c55e",
    button_hover_color: str = "#16a34a",
    center: list[float] | None = None,
    zoom: int = DEFAULT_ZOOM,
) -> folium.Map:
    """Create a Folium map with the Draw plugin and styled export button."""
    m = folium.Map(
        location=center or DEFAULT_CENTER,
        zoom_start=zoom,
        tiles="CartoDB positron",
        control_scale=True,
    )
    Draw(
        export=True,
        filename=export_filename,
        position="topleft",
        draw_options={
            "polyline": draw_polyline,
            "polygon": draw_polygon,
            "rectangle": draw_rectangle,
            "circle": False,
            "marker": False,
            "circlemarker": False,
        },
        edit_options={"edit": edit, "remove": True},
    ).add_to(m)
    m.get_root().html.add_child(
        Element(
            _EXPORT_BUTTON_CSS.format(
                bg_color=button_color,
                hover_color=button_hover_color,
            )
        )
    )
    return m


def overlay_route(
    m: folium.Map,
    route_coords: list,
    color: str = "#6366f1",
    fit_bounds: bool = True,
) -> None:
    """Add a dashed polyline overlay and optionally fit map bounds."""
    if len(route_coords) < 2:
        return
    folium.PolyLine(
        locations=[[lat, lon] for lon, lat in route_coords],
        color=color,
        weight=3,
        opacity=0.7,
        dash_array="8",
    ).add_to(m)
    if fit_bounds:
        lats = [c[1] for c in route_coords]
        lons = [c[0] for c in route_coords]
        m.fit_bounds([[min(lats), min(lons)], [max(lats), max(lons)]])
