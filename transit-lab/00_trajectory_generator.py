import marimo

__generated_with = "0.20.4"
app = marimo.App(width="medium")


@app.cell
def _():
    import folium
    import math
    import marimo as mo
    import pandas as pd
    import pydeck as pdk
    import random
    from datetime import datetime, timedelta
    from folium.plugins import Draw
    from geoalchemy2.shape import to_shape
    from sqlalchemy import select

    from database.connection import SessionLocal
    from database.models.line import Line, LineStatus

    return (
        Draw,
        Line,
        LineStatus,
        SessionLocal,
        datetime,
        folium,
        math,
        mo,
        pd,
        pdk,
        random,
        select,
        timedelta,
        to_shape,
    )


@app.cell
def _(SessionLocal, mo):
    db = SessionLocal()
    get_refresh, set_refresh = mo.state(0)
    get_last_create_click, set_last_create_click = mo.state(0)
    get_last_generate_click, set_last_generate_click = mo.state(0)
    get_simulated_points, set_simulated_points = mo.state([])
    get_simulation_message, set_simulation_message = mo.state(
        "Set your controls and click **Generate simulated tracks**."
    )
    return (
        db,
        get_last_create_click,
        get_last_generate_click,
        get_refresh,
        get_simulated_points,
        get_simulation_message,
        set_last_create_click,
        set_last_generate_click,
        set_refresh,
        set_simulated_points,
        set_simulation_message,
    )


@app.cell
def _(Line, LineStatus, db, get_refresh, select):
    _ = get_refresh()
    approved_lines = (
        db.execute(
            select(Line)
            .where(Line.status == LineStatus.APPROVED)
            .order_by(Line.name)
        )
        .scalars()
        .all()
    )
    return (approved_lines,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Trajectory generator
    """)
    return


@app.cell
def _(approved_lines, mo):
    line_options = [f"{line.id} - {line.name}" for line in approved_lines]
    approved_line_selector = mo.ui.dropdown(
        options=line_options,
        value=line_options[0] if line_options else None,
        label="Approved lines",
    )
    return (approved_line_selector,)


@app.cell
def _(Line, approved_line_selector, db, mo):
    selected_line = None
    if approved_line_selector.value:
        selected_line_id = int(approved_line_selector.value.split(" - ", 1)[0])
        selected_line = db.get(Line, selected_line_id)

    selected_line_info = (
        mo.md(
            f"**Selected line:** `{selected_line.id}` - `{selected_line.name}` - `{selected_line.description or 'No description'}`"
        )
        if selected_line is not None
        else mo.md("No approved lines found.")
    )
    return selected_line, selected_line_info


@app.cell
def _(Draw, folium, mo):
    draw_map = folium.Map(
        location=[40.4168, -3.7038],
        zoom_start=12,
        tiles="CartoDB positron",
        control_scale=True,
    )

    Draw(
        export=True,
        filename="trajectory.geojson",
        position="topleft",
        draw_options={
            "polyline": True,
            "polygon": False,
            "rectangle": False,
            "circle": False,
            "marker": False,
            "circlemarker": False,
        },
        edit_options={"edit": False, "remove": True},
    ).add_to(draw_map)

    draw_path_section = mo.vstack(
        [
            mo.md("## Draw trajectory path"),
            mo.md(
                "Use the polyline tool (top-left) and click on the map to draw the path."
            ),
            mo.Html(draw_map._repr_html_()),
            mo.md(
                "_Tip: click **Export** on the map toolbar to download the drawn path as GeoJSON._"
            ),
        ],
        gap=1,
        align="start",
    )
    route_source = mo.ui.dropdown(
        options=["Selected approved line path", "Pasted GeoJSON route"],
        value="Selected approved line path",
        label="Route source",
    )
    route_geojson_input = mo.ui.text_area(
        label="Pasted route GeoJSON",
        placeholder='Paste exported GeoJSON here (FeatureCollection/Feature/LineString).',
        value="",
        rows=8,
    )
    return draw_path_section, route_geojson_input, route_source


@app.cell
def _(mo):
    sim_num_tracks = mo.ui.text(label="Number of simulated tracks", value="5")
    sim_sampling_rate_s = mo.ui.text(label="Sampling rate (seconds)", value="2.0")
    sim_speed_mps = mo.ui.text(label="Base speed (m/s)", value="8.0")
    sim_speed_jitter_pct = mo.ui.text(label="Speed jitter (%)", value="12.0")
    sim_target_points = mo.ui.text(label="Target points per track (0 = auto)", value="0")
    sim_seed = mo.ui.text(label="Random seed (-1 = random)", value="42")

    gaussian_noise_m = mo.ui.text(label="Gaussian GPS noise sigma (m)", value="3.0")
    perpendicular_noise_m = mo.ui.text(label="Perpendicular road noise sigma (m)", value="2.0")
    zigzag_amplitude_m = mo.ui.text(label="Zig-zag amplitude (m)", value="1.5")
    zigzag_period_points = mo.ui.text(label="Zig-zag period (points)", value="8")
    jump_probability = mo.ui.text(label="Random jump probability (0-1)", value="0.02")
    jump_distance_m = mo.ui.text(label="Random jump distance mean (m)", value="40.0")
    missing_probability = mo.ui.text(label="Missing points probability (0-1)", value="0.03")
    biased_drift_m_per_point = mo.ui.text(label="Biased drift (m/point)", value="0.05")
    biased_bearing_deg = mo.ui.text(label="Biased drift bearing (deg, 0=north)", value="70.0")
    lateral_drift_total_m = mo.ui.text(label="Lateral drift total (m)", value="3.0")
    timestamp_jitter_s = mo.ui.text(label="Timestamp jitter sigma (s)", value="0.15")

    generate_tracks_button = mo.ui.button(
        label="Generate simulated tracks",
        value=0,
        on_click=lambda v: (v or 0) + 1,
        kind="success",
    )
    return (
        biased_bearing_deg,
        biased_drift_m_per_point,
        gaussian_noise_m,
        generate_tracks_button,
        jump_distance_m,
        jump_probability,
        lateral_drift_total_m,
        missing_probability,
        perpendicular_noise_m,
        sim_num_tracks,
        sim_sampling_rate_s,
        sim_seed,
        sim_speed_jitter_pct,
        sim_speed_mps,
        sim_target_points,
        timestamp_jitter_s,
        zigzag_amplitude_m,
        zigzag_period_points,
    )


@app.cell
def _(
    biased_bearing_deg,
    biased_drift_m_per_point,
    datetime,
    gaussian_noise_m,
    generate_tracks_button,
    get_last_generate_click,
    jump_distance_m,
    jump_probability,
    lateral_drift_total_m,
    math,
    missing_probability,
    perpendicular_noise_m,
    random,
    route_geojson_input,
    route_source,
    selected_line,
    set_last_generate_click,
    set_simulated_points,
    set_simulation_message,
    sim_num_tracks,
    sim_sampling_rate_s,
    sim_seed,
    sim_speed_jitter_pct,
    sim_speed_mps,
    sim_target_points,
    timedelta,
    timestamp_jitter_s,
    to_shape,
    zigzag_amplitude_m,
    zigzag_period_points,
):
    def _to_float(raw: str, default: float) -> float:
        try:
            return float((raw or "").strip())
        except Exception:
            return default

    def _to_int(raw: str, default: int) -> int:
        try:
            return int((raw or "").strip())
        except Exception:
            return default

    def _clamp(value: float, lo: float, hi: float) -> float:
        return max(lo, min(hi, value))

    def _parse_route_from_geojson(raw: str) -> list[list[float]]:
        import json

        payload = json.loads(raw)
        geometry = None
        if payload.get("type") == "FeatureCollection":
            for feature in payload.get("features", []):
                geom = feature.get("geometry", {})
                if geom.get("type") == "LineString":
                    geometry = geom
                    break
        elif payload.get("type") == "Feature":
            geometry = payload.get("geometry", {})
        elif payload.get("type") == "LineString":
            geometry = payload

        if not geometry or geometry.get("type") != "LineString":
            raise ValueError("GeoJSON must contain a LineString geometry")

        coords = geometry.get("coordinates", [])
        route = []
        for coord in coords:
            if not isinstance(coord, (list, tuple)) or len(coord) < 2:
                continue
            route.append([float(coord[0]), float(coord[1])])
        return route

    def _route_from_selected_line() -> list[list[float]]:
        if selected_line is None or selected_line.path is None:
            return []
        try:
            shape = to_shape(selected_line.path)
            return [[float(lon), float(lat)] for lon, lat in shape.coords]
        except Exception:
            return []

    def _haversine_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
        r = 6_371_000
        p1 = math.radians(lat1)
        p2 = math.radians(lat2)
        dp = math.radians(lat2 - lat1)
        dl = math.radians(lon2 - lon1)
        a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
        return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    def _offset_lon_lat(lon: float, lat: float, east_m: float, north_m: float) -> tuple[float, float]:
        lat_out = lat + (north_m / 111_320.0)
        cos_lat = max(1e-6, abs(math.cos(math.radians(lat_out))))
        lon_out = lon + (east_m / (111_320.0 * cos_lat))
        return lon_out, lat_out

    def _heading_and_perp(route: list[list[float]], idx: int) -> tuple[tuple[float, float], tuple[float, float]]:
        if len(route) < 2:
            return (1.0, 0.0), (0.0, 1.0)
        i0 = max(0, idx - 1)
        i1 = min(len(route) - 1, idx + 1)
        lon0, lat0 = route[i0]
        lon1, lat1 = route[i1]
        mean_lat = math.radians((lat0 + lat1) / 2.0)
        east = (lon1 - lon0) * 111_320.0 * math.cos(mean_lat)
        north = (lat1 - lat0) * 111_320.0
        norm = max(1e-6, math.sqrt(east**2 + north**2))
        heading = (east / norm, north / norm)
        perp = (-heading[1], heading[0])
        return heading, perp

    def _interpolate_route(route: list[list[float]], step_m: float) -> list[list[float]]:
        if len(route) < 2:
            return route
        seg_lengths = []
        for i in range(len(route) - 1):
            lon0, lat0 = route[i]
            lon1, lat1 = route[i + 1]
            seg_lengths.append(_haversine_m(lon0, lat0, lon1, lat1))
        total = sum(seg_lengths)
        if total <= 0:
            return [route[0], route[-1]]

        points_count = max(2, int(total / max(0.5, step_m)) + 1)
        targets = [total * i / (points_count - 1) for i in range(points_count)]
        interpolated = []
        seg_idx = 0
        seg_start_dist = 0.0
        for target in targets:
            while seg_idx < len(seg_lengths) - 1 and seg_start_dist + seg_lengths[seg_idx] < target:
                seg_start_dist += seg_lengths[seg_idx]
                seg_idx += 1
            lon0, lat0 = route[seg_idx]
            lon1, lat1 = route[seg_idx + 1]
            seg_len = max(1e-6, seg_lengths[seg_idx])
            frac = _clamp((target - seg_start_dist) / seg_len, 0.0, 1.0)
            lon = lon0 + (lon1 - lon0) * frac
            lat = lat0 + (lat1 - lat0) * frac
            interpolated.append([lon, lat])
        return interpolated

    generate_click = generate_tracks_button.value or 0
    if generate_click > get_last_generate_click():
        set_last_generate_click(generate_click)

        num_tracks = max(1, _to_int(sim_num_tracks.value, 5))
        sampling_rate_s = max(0.2, _to_float(sim_sampling_rate_s.value, 2.0))
        base_speed_mps = max(0.5, _to_float(sim_speed_mps.value, 8.0))
        speed_jitter_pct = max(0.0, _to_float(sim_speed_jitter_pct.value, 12.0))
        target_points = max(0, _to_int(sim_target_points.value, 0))
        seed_value = _to_int(sim_seed.value, 42)

        gaussian_m = max(0.0, _to_float(gaussian_noise_m.value, 3.0))
        perpendicular_m = max(0.0, _to_float(perpendicular_noise_m.value, 2.0))
        zigzag_amp_m = max(0.0, _to_float(zigzag_amplitude_m.value, 1.5))
        zigzag_period = max(2, _to_int(zigzag_period_points.value, 8))
        jump_prob = _clamp(_to_float(jump_probability.value, 0.02), 0.0, 1.0)
        jump_distance_mean_m = max(0.0, _to_float(jump_distance_m.value, 40.0))
        missing_prob = _clamp(_to_float(missing_probability.value, 0.03), 0.0, 0.95)
        biased_drift_step_m = _to_float(biased_drift_m_per_point.value, 0.05)
        biased_bearing = math.radians(_to_float(biased_bearing_deg.value, 70.0))
        lateral_drift_total_m_value = _to_float(lateral_drift_total_m.value, 3.0)
        timestamp_jitter = max(0.0, _to_float(timestamp_jitter_s.value, 0.15))

        route_error = None
        try:
            if route_source.value == "Pasted GeoJSON route":
                route = _parse_route_from_geojson(route_geojson_input.value or "")
            else:
                route = _route_from_selected_line()
        except Exception as exc:
            route = []
            route_error = str(exc)

        if route_error:
            set_simulated_points([])
            set_simulation_message(f"Route error: {route_error}")
        elif len(route) < 2:
            set_simulated_points([])
            set_simulation_message("Route needs at least 2 points.")
        else:
            records = []
            start_time = datetime.utcnow().replace(microsecond=0)

            for track_idx in range(num_tracks):
                track_seed = None if seed_value < 0 else seed_value + track_idx * 1009
                rng = random.Random(track_seed)

                speed_factor = max(0.1, 1 + rng.gauss(0, speed_jitter_pct / 100.0))
                step_m = max(0.5, base_speed_mps * speed_factor * sampling_rate_s)
                base_points = _interpolate_route(route, step_m)

                if target_points > 1 and len(base_points) > target_points:
                    idxs = [
                        round(i * (len(base_points) - 1) / (target_points - 1))
                        for i in range(target_points)
                    ]
                    base_points = [base_points[i] for i in idxs]

                drift_acc_m = 0.0
                noisy_points = []
                elapsed_s = 0.0

                for i, (lon, lat) in enumerate(base_points):
                    _, perp = _heading_and_perp(base_points, i)
                    east_m = 0.0
                    north_m = 0.0

                    east_m += rng.gauss(0, gaussian_m)
                    north_m += rng.gauss(0, gaussian_m)

                    if perpendicular_m > 0:
                        perp_offset = rng.gauss(0, perpendicular_m)
                        east_m += perp[0] * perp_offset
                        north_m += perp[1] * perp_offset

                    if zigzag_amp_m > 0:
                        zigzag_offset = zigzag_amp_m * math.sin(
                            (2 * math.pi * i) / zigzag_period
                        )
                        east_m += perp[0] * zigzag_offset
                        north_m += perp[1] * zigzag_offset

                    if (
                        jump_prob > 0
                        and rng.random() < jump_prob
                        and jump_distance_mean_m > 0
                    ):
                        jump_angle = rng.uniform(0, 2 * math.pi)
                        jump_dist = max(
                            0.0,
                            rng.gauss(
                                jump_distance_mean_m, jump_distance_mean_m * 0.35
                            ),
                        )
                        east_m += math.cos(jump_angle) * jump_dist
                        north_m += math.sin(jump_angle) * jump_dist

                    drift_acc_m += biased_drift_step_m
                    east_m += math.sin(biased_bearing) * drift_acc_m
                    north_m += math.cos(biased_bearing) * drift_acc_m

                    if len(base_points) > 1 and lateral_drift_total_m_value != 0:
                        lateral_progress = i / (len(base_points) - 1)
                        lateral_offset = lateral_progress * lateral_drift_total_m_value
                        east_m += perp[0] * lateral_offset
                        north_m += perp[1] * lateral_offset

                    nlon, nlat = _offset_lon_lat(lon, lat, east_m, north_m)
                    if i > 0:
                        elapsed_s += max(
                            0.2, sampling_rate_s + rng.gauss(0, timestamp_jitter)
                        )
                    noisy_points.append((nlon, nlat, elapsed_s))

                kept_points = []
                for i, point in enumerate(noisy_points):
                    if i in (0, len(noisy_points) - 1) or rng.random() >= missing_prob:
                        kept_points.append(point)
                if len(kept_points) < 2 and len(noisy_points) >= 2:
                    kept_points = [noisy_points[0], noisy_points[-1]]

                track_start = start_time + timedelta(minutes=track_idx)
                for point_idx, (lon, lat, t_s) in enumerate(kept_points):
                    timestamp = track_start + timedelta(seconds=t_s)
                    records.append(
                        {
                            "track_id": track_idx + 1,
                            "point_index": point_idx + 1,
                            "timestamp": timestamp.isoformat(),
                            "longitude": lon,
                            "latitude": lat,
                        }
                    )

            set_simulated_points(records)
            set_simulation_message(
                f"Generated {num_tracks} track(s) with {len(records)} geopoint(s) total."
            )
    return


@app.cell
def _(get_simulated_points, get_simulation_message, mo, pd, pdk):
    generated_records = get_simulated_points()
    simulation_message = get_simulation_message()

    if not generated_records:
        simulated_tracks_output = mo.md(simulation_message)
    else:
        generated_df = pd.DataFrame(generated_records)
        preview_table = mo.ui.table(
            data=generated_df.head(300),
            label="Generated geopoints (first 300 rows)",
            pagination=True,
        )

        palette = [
            [59, 130, 246],
            [34, 197, 94],
            [234, 179, 8],
            [168, 85, 247],
            [236, 72, 153],
            [20, 184, 166],
        ]
        path_layer_data = []
        for idx, (track_id, group) in enumerate(
            generated_df.sort_values(["track_id", "point_index"]).groupby("track_id")
        ):
            path_layer_data.append(
                {
                    "track_id": int(track_id),
                    "path": group[["longitude", "latitude"]].values.tolist(),
                    "color": palette[idx % len(palette)],
                }
            )

        center_lat = float(generated_df["latitude"].mean())
        center_lon = float(generated_df["longitude"].mean())
        deck = pdk.Deck(
            map_style="light",
            map_provider="carto",
            initial_view_state=pdk.ViewState(
                latitude=center_lat,
                longitude=center_lon,
                zoom=30,
                pitch=0,
                bearing=0,
            ),
            layers=[
                pdk.Layer(
                    "PathLayer",
                    path_layer_data,
                    get_path="path",
                    get_color="color",
                    get_width=0.5,
                    width_min_pixels=1,
                    pickable=True,
                )
            ],
            tooltip={"text": "Track {track_id}"},
            height=420,
        )

        simulated_tracks_output = mo.vstack(
            [
                mo.md(f"## Simulated tracks\n\n{simulation_message}"),
                deck,
                preview_table,
            ],
            gap=1,
            align="stretch",
        )
    return (simulated_tracks_output,)


@app.cell
def _(LineStatus, mo):
    new_line_name = mo.ui.text(label="New line name", placeholder="Line 42")
    new_line_description = mo.ui.text(
        label="Description (optional)",
        placeholder="Main corridor from A to B",
    )
    new_line_status = mo.ui.dropdown(
        options=[status.value for status in LineStatus],
        value=LineStatus.PENDING.value,
        label="Status",
    )
    create_line_button = mo.ui.button(
        label="Create new line",
        value=0,
        on_click=lambda v: (v or 0) + 1,
        kind="neutral",
    )
    return (
        create_line_button,
        new_line_description,
        new_line_name,
        new_line_status,
    )


@app.cell
def _(
    Line,
    LineStatus,
    create_line_button,
    db,
    get_last_create_click,
    new_line_description,
    new_line_name,
    new_line_status,
    set_last_create_click,
    set_refresh,
):
    create_line_feedback = ""
    current_click = create_line_button.value or 0
    if current_click > get_last_create_click():
        set_last_create_click(current_click)
        name = (new_line_name.value or "").strip()
        description = (new_line_description.value or "").strip() or None

        if not name:
            create_line_feedback = "Please provide a name before creating a line."
        else:
            try:
                new_line = Line(
                    name=name,
                    description=description,
                    status=LineStatus(new_line_status.value),
                )
                db.add(new_line)
                db.commit()
                set_refresh(lambda v: v + 1)
                create_line_feedback = f"Created new line: {name}"
            except Exception as exc:
                db.rollback()
                create_line_feedback = f"Could not create line: {exc}"
    return (create_line_feedback,)


@app.cell
def _(
    approved_line_selector,
    biased_bearing_deg,
    biased_drift_m_per_point,
    create_line_button,
    create_line_feedback,
    draw_path_section,
    gaussian_noise_m,
    generate_tracks_button,
    jump_distance_m,
    jump_probability,
    lateral_drift_total_m,
    missing_probability,
    mo,
    new_line_description,
    new_line_name,
    new_line_status,
    perpendicular_noise_m,
    route_geojson_input,
    route_source,
    selected_line_info,
    sim_num_tracks,
    sim_sampling_rate_s,
    sim_seed,
    sim_speed_jitter_pct,
    sim_speed_mps,
    sim_target_points,
    simulated_tracks_output,
    timestamp_jitter_s,
    zigzag_amplitude_m,
    zigzag_period_points,
):
    form_body = mo.vstack(
        [
            mo.hstack(
                [new_line_name, new_line_description, new_line_status, create_line_button],
                gap=1,
            ),
            mo.md(create_line_feedback) if create_line_feedback else mo.md(""),
        ],
        gap=1,
        align="start",
    )

    accordion = mo.accordion({"Add a new line": form_body})
    simulation_controls = mo.accordion(
        {
            "Simulation controls": mo.vstack(
                [
                    mo.hstack(
                        [
                            sim_num_tracks,
                            sim_sampling_rate_s,
                            sim_speed_mps,
                            sim_speed_jitter_pct,
                            sim_target_points,
                            sim_seed,
                        ],
                        gap=1,
                    ),
                    mo.hstack(
                        [
                            gaussian_noise_m,
                            perpendicular_noise_m,
                            zigzag_amplitude_m,
                            zigzag_period_points,
                        ],
                        gap=1,
                    ),
                    mo.hstack(
                        [
                            jump_probability,
                            jump_distance_m,
                            missing_probability,
                            biased_drift_m_per_point,
                            biased_bearing_deg,
                        ],
                        gap=1,
                    ),
                    mo.hstack(
                        [lateral_drift_total_m, timestamp_jitter_s, generate_tracks_button],
                        gap=1,
                    ),
                ],
                gap=1,
                align="start",
            )
        }
    )

    mo.vstack([
        approved_line_selector,
        selected_line_info,
        draw_path_section,
        route_source,
        route_geojson_input if route_source.value == "Pasted GeoJSON route" else mo.md(""),
        simulation_controls,
        simulated_tracks_output,
        accordion,
    ])
    return


if __name__ == "__main__":
    app.run()
