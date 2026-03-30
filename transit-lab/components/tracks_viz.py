"""Pydeck layer builders for track visualization."""

import pandas as pd
import pydeck as pdk

from .styles import TRACK_COLORS


def build_path_layers(
    df: pd.DataFrame,
) -> tuple[list[pdk.Layer], dict]:
    """Build PathLayer + optional accuracy ScatterplotLayer from generated tracks.

    Returns (layers, tooltip_dict).
    """
    path_layer_data = []
    for idx, (track_id, group) in enumerate(
        df.sort_values(["track_id", "point_index"]).groupby("track_id")
    ):
        path_layer_data.append(
            {
                "track_id": int(track_id),
                "path": group[["longitude", "latitude"]].values.tolist(),
                "color": TRACK_COLORS[idx % len(TRACK_COLORS)],
            }
        )

    layers = [
        pdk.Layer(
            "PathLayer",
            path_layer_data,
            get_path="path",
            get_color="color",
            get_width=0.5,
            width_min_pixels=1,
            pickable=True,
        )
    ]
    tooltip = {"text": "Track {track_id}"}

    acc_col = df.get("accuracy") if "accuracy" in df.columns else None
    if acc_col is not None and acc_col.notna().any():
        acc_layer, tooltip = _build_accuracy_layer(df, acc_col)
        layers.append(acc_layer)

    return layers, tooltip


def _build_accuracy_layer(
    df: pd.DataFrame, acc_col: pd.Series
) -> tuple[pdk.Layer, dict]:
    """Build a ScatterplotLayer colored by per-point accuracy values."""
    acc_min = float(acc_col.min())
    acc_max = float(acc_col.max())
    acc_range = max(acc_max - acc_min, 0.01)

    acc_points = []
    for row in df.itertuples(index=False):
        v = getattr(row, "accuracy", None)
        if v is None or (v != v):  # None or NaN
            color = [150, 150, 150, 80]
            acc_val = None
        else:
            t = (float(v) - acc_min) / acc_range
            color = [int(min(255, t * 510)), int(min(255, (1.0 - t) * 510)), 0, 200]
            acc_val = round(float(v), 1)
        acc_points.append(
            {
                "longitude": float(row.longitude),
                "latitude": float(row.latitude),
                "track_id": int(row.track_id),
                "accuracy": acc_val,
                "color": color,
            }
        )

    layer = pdk.Layer(
        "ScatterplotLayer",
        acc_points,
        get_position=["longitude", "latitude"],
        get_fill_color="color",
        get_radius=6,
        radius_min_pixels=3,
        pickable=True,
    )
    tooltip = {"text": "Track {track_id}\nAccuracy: {accuracy} m"}
    return layer, tooltip
