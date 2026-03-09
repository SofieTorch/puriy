import streamlit as st
 
pg = st.navigation([
	st.Page("pages/lines.py", title="Líneas"),
	st.Page("pages/tracks.py", title="Trayectos"),
	st.Page("pages/inferred_lines.py", title="Líneas inferidas"),
])

pg.run()