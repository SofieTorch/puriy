import streamlit as st
import pydeck as pdk
from geoalchemy2.shape import to_shape
from sqlalchemy import select

from database.connection import SessionLocal
from database.models.line import Line, LineStatus
from database.models.recording import LocationPoint, RecordingSession, RecordingStatus

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

            if path_coords:
                center_lat = sum(c[1] for c in path_coords) / len(path_coords)
                center_lon = sum(c[0] for c in path_coords) / len(path_coords)
                st.subheader("Trayecto")
                layers = [
                    pdk.Layer(
                        "PathLayer",
                        data=[{"path": path_coords}],
                        get_path="path",
                        get_color=[59, 130, 246],
                        get_width=12,
                    ),
                ]
                if location_points:
                    layers.append(
                        pdk.Layer(
                            "ScatterplotLayer",
                            data=[{"coordinates": [p.longitude, p.latitude]} for p in location_points],
                            get_position="coordinates",
                            get_color=[239, 68, 68],
                            get_radius=8,
                            radius_min_pixels=4,
                        ),
                    )
                st.pydeck_chart(
                    pdk.Deck(
                        map_style=None,
                        initial_view_state=pdk.ViewState(
                            latitude=center_lat,
                            longitude=center_lon,
                            zoom=14,
                            pitch=0,
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