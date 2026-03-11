import streamlit as st
import pydeck as pdk
from geoalchemy2.shape import to_shape
from sqlalchemy import select

from database.connection import SessionLocal
from database.models.line import Line, LineStatus
from database.models.recording import LocationPoint, RecordingSession, RecordingStatus
from geodata.reduce import reduce_linestring_from_recording_session

# 3D view settings
MAP_PITCH = 50
MAP_ZOOM = 14


def _trip_data(path_coords, location_points=None):
    """Build TripsLayer data with path and timestamps. Uses real timestamps if points available."""
    if location_points and len(location_points) >= 2:
        t0 = location_points[0].timestamp
        timestamps = [(p.timestamp - t0).total_seconds() for p in location_points]
        path = [
            [p.longitude, p.latitude, p.altitude if p.altitude is not None else 0]
            for p in location_points
        ]
    else:
        timestamps = list(range(len(path_coords)))
        path = [[c[0], c[1], 0] for c in path_coords]
    current_time = max(timestamps) if timestamps else 0
    return [{"path": path, "timestamps": timestamps}], current_time


def _deleted_points(coords_before, coords_after):
    """Points from coords_before that were removed by simplification (not in coords_after)."""
    if not coords_after or not coords_before:
        return coords_before if coords_before else []
    kept_indices = set()
    for lon, lat in coords_after:
        min_dist = float("inf")
        best_j = None
        for j, (blon, blat) in enumerate(coords_before):
            dist = (lon - blon) ** 2 + (lat - blat) ** 2
            if dist < min_dist:
                min_dist = dist
                best_j = j
        if best_j is not None:
            kept_indices.add(best_j)
    return [[c[0], c[1]] for j, c in enumerate(coords_before) if j not in kept_indices]


STATUS_LABELS = {
    LineStatus.PENDING: "Pendiente",
    LineStatus.APPROVED: "Aprobada",
    LineStatus.MERGED: "Fusionada",
}

STATUS_ORDER = [LineStatus.PENDING, LineStatus.APPROVED, LineStatus.MERGED]

RECORDING_STATUS_LABELS = {
    RecordingStatus.IN_PROGRESS: "En progreso",
    RecordingStatus.COMPLETED: "Completada",
    RecordingStatus.CANCELLED: "Cancelada",
    RecordingStatus.ABANDONED: "Abandonada",
    RecordingStatus.DISCARDED: "Descartada",
}

st.title("Trayectos")

selected_line = None

with st.sidebar:
    with SessionLocal() as db:
        all_lines = list(db.execute(select(Line).order_by(Line.name)).scalars().all())

    if all_lines:
        selected_statuses = st.segmented_control(
            "Estado de líneas",
            options=[s.value for s in STATUS_ORDER],
            format_func=lambda x: STATUS_LABELS[LineStatus(x)],
            selection_mode="multi",
            key="line_status_filter",
        )

        # Empty selection = show all; otherwise filter to selected statuses
        if not selected_statuses:
            lines = sorted(
                all_lines,
                key=lambda l: (STATUS_ORDER.index(l.status), l.name),
            )
            line_options = {line.id: f"{line.name} · {STATUS_LABELS[line.status]}" for line in lines}
        else:
            status_set = {LineStatus(s) for s in selected_statuses}
            lines = sorted(
                [l for l in all_lines if l.status in status_set],
                key=lambda l: (STATUS_ORDER.index(l.status), l.name),
            )
            line_options = {line.id: f"{line.name} · {STATUS_LABELS[line.status]}" for line in lines}

        if lines:
            selected_line_id = st.selectbox(
                "Línea",
                options=list(line_options.keys()),
                format_func=lambda x: line_options[x],
            )
            selected_line = next((l for l in lines if l.id == selected_line_id), None)
        else:
            st.selectbox("Línea", [], disabled=True)
            labels = ", ".join(STATUS_LABELS[LineStatus(s)] for s in selected_statuses)
            st.info(f"No hay líneas con estado «{labels}»")
    else:
        st.selectbox("Línea", [], disabled=True)
        st.info("No hay líneas en la base de datos")

if selected_line:
    with SessionLocal() as db:
        sessions = list(
            db.execute(
                select(RecordingSession)
                .where(RecordingSession.line_id == selected_line.id)
                .order_by(RecordingSession.started_at.desc())
            ).scalars().all()
        )

    if sessions:
        table_data = [
            {
                "ID": s.id,
                "Estado": RECORDING_STATUS_LABELS[s.status],
                "Inicio": s.started_at,
                "Fin": s.ended_at,
                "Dirección": s.direction or "—",
                "Dispositivo": s.device_model or "—",
            }
            for s in sessions
        ]
        event = st.dataframe(
            table_data,
            use_container_width=True,
            on_select="rerun",
            selection_mode="single-row",
            key=f"sessions_table_{selected_line.id}",
        )

        selected_rows = event.selection.rows if event.selection else []
        if selected_rows:
            selected_session = sessions[selected_rows[0]]
            with SessionLocal() as db:
                location_points = list(
                    db.execute(
                        select(LocationPoint)
                        .where(LocationPoint.session_id == selected_session.id)
                        .order_by(LocationPoint.timestamp)
                    ).scalars().all()
                )

            # Build path from computed_path or fall back to location_points
            path_coords = None
            if selected_session.computed_path is not None:
                try:
                    geom = to_shape(selected_session.computed_path)
                    path_coords = [[c[0], c[1]] for c in geom.coords]
                except Exception:
                    path_coords = None
            if path_coords is None and location_points:
                path_coords = [[p.longitude, p.latitude] for p in location_points]

            num_points = len(location_points)
            st.metric("Puntos de ubicación", num_points)

            reduce_key = f"reduce_result_{selected_session.id}"
            tolerance = st.number_input(
                "Tolerancia (grados, ~0.00005 ≈ 5 m)",
                value=0.00005,
                format="%.6f",
                step=0.00001,
                key=f"tolerance_{selected_session.id}",
            )
            if st.button("Simplificar trayectoria", key=f"reduce_btn_{selected_session.id}"):
                with SessionLocal() as db:
                    try:
                        result = reduce_linestring_from_recording_session(
                            db,
                            selected_session.id,
                            tolerance=tolerance,
                            return_coords=True,
                        )
                        db.commit()
                        st.session_state[reduce_key] = result
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al simplificar: {e}")

            if reduce_key in st.session_state:
                r = st.session_state[reduce_key]
                st.subheader("Comparación antes / después")
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Puntos antes", r["points_before"])
                with col2:
                    st.metric("Puntos después", r["points_after"])
                with col3:
                    st.metric("Puntos eliminados", r["points_removed"])

                if "coords_before" in r and "coords_after" in r:
                    coords_before = [[c[0], c[1]] for c in r["coords_before"]]
                    coords_after = [[c[0], c[1]] for c in r["coords_after"]]
                    deleted_coords = _deleted_points(coords_before, coords_after)
                    center_lat = sum(c[1] for c in coords_before) / len(coords_before)
                    center_lon = sum(c[0] for c in coords_before) / len(coords_before)
                    show_deleted_points = st.toggle(
                        "Mostrar puntos eliminados",
                        value=True,
                        key=f"show_deleted_{selected_session.id}",
                    )
                    st.caption("Gris: antes · Azul: después · Puntos rojos: eliminados · Puntos azules: simplificados")
                    comparison_layers = [
                        pdk.Layer(
                            "PathLayer",
                            data=[{"path": coords_before}],
                            get_path="path",
                            get_color=[100, 100, 100],
                            get_width=5,
                            width_min_pixels=3,
                        ),
                        pdk.Layer(
                            "PathLayer",
                            data=[{"path": coords_after}],
                            get_path="path",
                            get_color=[33, 150, 243],
                            get_width=12,
                            width_min_pixels=8,
                        ),
                        pdk.Layer(
                            "ScatterplotLayer",
                            data=[{"coordinates": [c[0], c[1], 0]} for c in coords_after],
                            get_position="coordinates",
                            get_color=[33, 150, 243],
                            get_radius=12,
                            radius_min_pixels=6,
                        ),
                    ]
                    if show_deleted_points and deleted_coords:
                        comparison_layers.append(
                            pdk.Layer(
                                "ScatterplotLayer",
                                data=[{"coordinates": [c[0], c[1], 0]} for c in deleted_coords],
                                get_position="coordinates",
                                get_color=[239, 68, 68],
                                get_radius=6,
                                radius_min_pixels=5,
                            )
                        )
                    st.pydeck_chart(
                        pdk.Deck(
                            map_style=None,
                            initial_view_state=pdk.ViewState(
                                latitude=center_lat,
                                longitude=center_lon,
                                zoom=MAP_ZOOM,
                                pitch=MAP_PITCH,
                            ),
                            layers=comparison_layers,
                        ),
                        use_container_width=True,
                    )

            if path_coords:
                center_lat = sum(c[1] for c in path_coords) / len(path_coords)
                center_lon = sum(c[0] for c in path_coords) / len(path_coords)
                trip_data, current_time = _trip_data(path_coords, location_points)
                st.subheader("Trayecto")
                show_points = st.toggle(
                    "Mostrar puntos en el mapa",
                    value=True,
                    key=f"show_points_{selected_session.id}",
                )
                layers = [
                    pdk.Layer(
                        "TripsLayer",
                        trip_data,
                        get_path="path",
                        get_timestamps="timestamps",
                        get_color=[59, 130, 246],
                        opacity=0.9,
                        width_min_pixels=8,
                        trail_length=current_time + 1,
                        current_time=current_time,
                    ),
                ]
                if location_points and show_points:
                    layers.append(
                        pdk.Layer(
                            "ScatterplotLayer",
                            data=[
                                {
                                    "coordinates": [
                                        p.longitude,
                                        p.latitude,
                                        p.altitude if p.altitude is not None else 0,
                                    ]
                                }
                                for p in location_points
                            ],
                            get_position="coordinates",
                            get_color=[239, 68, 68],
                            get_radius=15,
                            radius_min_pixels=4,
                        ),
                    )
                st.pydeck_chart(
                    pdk.Deck(
                        map_style=None,
                        initial_view_state=pdk.ViewState(
                            latitude=center_lat,
                            longitude=center_lon,
                            zoom=MAP_ZOOM,
                            pitch=MAP_PITCH,
                        ),
                        layers=layers,
                    ),
                    use_container_width=True,
                )
            else:
                st.info("No hay trayectoria para mostrar (sin computed_path ni puntos de ubicación)")

            if location_points:
                st.subheader("Puntos de ubicación")
                points_data = [
                    {
                        "ID": p.id,
                        "Timestamp": p.timestamp,
                        "Latitud": p.latitude,
                        "Longitud": p.longitude,
                        "Altitud": p.altitude or "—",
                        "Velocidad": p.speed if p.speed is not None else "—",
                        "Rumbo": p.bearing if p.bearing is not None else "—",
                    }
                    for p in location_points
                ]
                st.dataframe(points_data, use_container_width=True)
            else:
                st.info(f"No hay puntos de ubicación para la sesión {selected_session.id}")
    else:
        st.info(f"No hay sesiones de grabación para «{selected_line.name}»")
else:
    st.info("Selecciona una línea para ver sus sesiones de grabación")