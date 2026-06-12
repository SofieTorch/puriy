#!/usr/bin/env python3
"""Genera el diagrama de despliegue del entorno de producción (SVG) en español.

Estilo académico sobrio (serif, escala de grises), coherente con
`_gen_nav_map.py`. Refleja `infra/deploy/docker-compose.yml`, el
`Caddyfile`, el flujo `.github/workflows/deploy.yml` y el cron del host.
"""
from html import escape

# ---- Estilos (paleta académica, escala de grises) ----------------------
SERIF = "Georgia,'Times New Roman',serif"
INK = "#1A1A1A"
RULE = "#3A3A3A"
GRAY = "#8A8A8A"

NODE_HDR = "#E4E4E2"      # banda de cabecera de nodo
NODE_BODY = "#FFFFFF"
DEVICE_BODY = "#F4F4F2"
COMP_FILL = "#FFFFFF"
COMP_STROKE = "#6B6B6B"
JOB_FILL = "#F6F6F6"
EXT_FILL = "#EDEDED"
OBS_FILL = "#F8F8F6"

W, H = 1580, 900
svg = []


# ---- Primitivas ---------------------------------------------------------
def rect(x, y, w, h, fill, stroke, sw=1.2, rx=3, dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" '
               f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{d}/>')


def text(x, y, s, size=13, weight="400", fill=INK, anchor="start",
         italic=False, opacity=1.0):
    st = ' font-style="italic"' if italic else ""
    op = f' opacity="{opacity}"' if opacity != 1.0 else ""
    svg.append(f'<text x="{x}" y="{y}" font-family="{SERIF}" font-size="{size}" '
               f'font-weight="{weight}" fill="{fill}" text-anchor="{anchor}"{st}{op}>'
               f'{escape(s)}</text>')


def node(x, y, w, h, stereo, name, body=NODE_BODY, sw=2):
    """Nodo UML: caja de borde grueso con banda de cabecera (estereotipo + nombre)."""
    rect(x, y, w, h, body, INK, sw=sw)
    rect(x, y, w, 34, NODE_HDR, INK, sw=sw)
    text(x + w / 2, y + 15, stereo, 11, "400", "#444", "middle", italic=True)
    text(x + w / 2, y + 29, name, 14, "700", INK, "middle")


def comp(x, y, w, h, name, sub="", fill=COMP_FILL, stroke=COMP_STROKE,
         sw=1.3, dash=None, bold=True):
    """Componente / contenedor desplegado."""
    rect(x, y, w, h, fill, stroke, sw=sw, dash=dash)
    if sub:
        text(x + w / 2, y + h / 2 - 3, name, 12.5, "700" if bold else "400",
             INK, "middle")
        text(x + w / 2, y + h / 2 + 14, sub, 10.5, "400", "#555", "middle",
             italic=True)
    else:
        text(x + w / 2, y + h / 2 + 4, name, 12.5, "700" if bold else "400",
             INK, "middle")


def arrow(pts, color=RULE, dashed=False, marker="arr", sw=1.4):
    d = ' stroke-dasharray="5 3"' if dashed else ""
    p = " ".join(f"{px},{py}" for px, py in pts)
    svg.append(f'<polyline points="{p}" fill="none" stroke="{color}" '
               f'stroke-width="{sw}"{d} marker-end="url(#{marker})"/>')


def alabel(x, y, s, size=10.5, anchor="middle"):
    """Etiqueta de arista con fondo para legibilidad."""
    wd = max(len(s) * size * 0.5, 10)
    svg.append(f'<rect x="{x - (wd/2 if anchor=="middle" else 0)}" y="{y-10}" '
               f'width="{wd}" height="14" fill="#FCFCFA" opacity="0.92"/>')
    text(x, y + 1, s, size, "400", "#2A2A2A", anchor)


# ---- Lienzo -------------------------------------------------------------
svg.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
           f'viewBox="0 0 {W} {H}" font-family="{SERIF}">')
svg.append('<defs>'
           '<marker id="arr" markerWidth="10" markerHeight="10" refX="7.5" '
           'refY="3" orient="auto" markerUnits="userSpaceOnUse">'
           f'<path d="M0,0 L8,3 L0,6 Z" fill="{RULE}"/></marker>'
           '<marker id="arrL" markerWidth="9" markerHeight="9" refX="7" '
           'refY="3" orient="auto" markerUnits="userSpaceOnUse">'
           f'<path d="M0,0 L7,3 L0,6 Z" fill="{GRAY}"/></marker>'
           '</defs>')
rect(0, 0, W, H, "#FCFCFA", "#FCFCFA", sw=0, rx=0)

# Título
text(W / 2, 46, "Diagrama de despliegue — Entorno de producción", 24, "700",
     INK, "middle")
text(W / 2, 71, "Puriy — reconstrucción colaborativa de rutas de transporte · "
     "servidor VPS orquestado con Docker Compose", 13, "400", "#555", "middle",
     italic=True)
svg.append(f'<line x1="40" y1="86" x2="{W-40}" y2="86" stroke="{INK}" stroke-width="1"/>')

# ---- Nodos cliente / externos ------------------------------------------
# Dispositivo móvil
node(40, 170, 300, 185, "«dispositivo»", "Dispositivo móvil del usuario",
     body=DEVICE_BODY)
comp(62, 222, 256, 56, "App Puriy", "Expo · React Native (Android / iOS)")
comp(62, 290, 256, 50, "SQLite local", "Drizzle ORM · cola de subida", fill="#F0F0EE")

# GitHub Actions (CI/CD)
node(40, 440, 300, 150, "«servidor CI/CD»", "GitHub Actions")
comp(62, 492, 256, 78, "Workflow deploy.yml",
     "build --no-cache · compose up", fill="#F0F0EE")

# Geofabrik (fuente externa)
node(1390, 250, 160, 120, "«externo»", "Geofabrik", body=EXT_FILL)
comp(1404, 300, 132, 56, "OSM Bolivia", "tiles .osm.pbf", fill="#FFFFFF")

# ---- Nodo VPS -----------------------------------------------------------
VX, VY, VW, VH = 400, 130, 940, 640
node(VX, VY, VW, VH, "«servidor»", "VPS — Ubuntu Linux · Docker Engine")
text(VX + 14, VY + 52, "docker-compose.yml  ·  red interna  +  red externa "
     "compartida  www", 11, "400", "#666", "start", italic=True)

# Caddy (proxy inverso compartido del host)
comp(420, 216, 900, 58,
     "Caddy — proxy inverso (red www · TLS)  ·  puriy.sofietorch.dev *",
     "enruta  /api → server   /valhalla → valhalla   /grafana → grafana",
     fill="#EFEFED", stroke=INK, sw=1.6)

# Capa de aplicación (columna izquierda: servidor, ocupa toda la altura)
comp(420, 300, 240, 212, "server", "FastAPI · Uvicorn :8000")

# Columna central: motor de ruteo (arriba) + base de datos (abajo)
comp(690, 300, 240, 92, "valhalla", "motor de ruteo HMM :8002")
comp(690, 420, 240, 92, "PostgreSQL + PostGIS",
     ":5432 · vol. db_data", fill="#F0F0EE")

# Columna derecha: tareas one-shot (jobs) + programación (cron)
rect(960, 300, 360, 92, JOB_FILL, COMP_STROKE, sw=1.3, dash="5 3")
text(1140, 318, "«jobs» tareas one-shot", 10.5, "400", "#555", "middle", italic=True)
comp(972, 326, 336, 28, "migrate", fill="#FFFFFF", dash="4 2", sw=1.1)
comp(972, 358, 336, 28, "pipeline", fill="#FFFFFF", dash="4 2", sw=1.1)
rect(960, 420, 360, 92, "#FFFFFF", COMP_STROKE, sw=1.3, dash="5 3")
text(1140, 455, "cron del host", 12.5, "700", INK, "middle")
text(1140, 472, "programa el servicio pipeline", 10, "400", "#555", "middle", italic=True)

# Stack de observabilidad
OY = 560
rect(420, OY, 900, 180, OBS_FILL, INK, sw=1.5)
rect(420, OY, 900, 30, "#EAEAE8", INK, sw=1.5)
text(420 + 450, OY + 20, "«stack de observabilidad»  —  telemetría OpenTelemetry",
     12, "700", INK, "middle")
comp(440, OY + 52, 185, 96, "OpenTelemetry", "Collector :4317 (OTLP)")
comp(648, OY + 52, 150, 96, "Tempo", "trazas")
comp(820, OY + 52, 150, 96, "Loki", "logs")
comp(992, OY + 52, 170, 96, "Prometheus", "métricas")
comp(1184, OY + 52, 120, 96, "Grafana", ":3000")

# ---- Aristas (comunicación en ejecución) -------------------------------
# Móvil -> Caddy
arrow([(340, 262), (418, 245)])
alabel(372, 240, "HTTPS :443  /api")
# GitHub Actions -> VPS (despliegue)
arrow([(340, 500), (398, 480)])
alabel(372, 470, "SSH")
alabel(372, 506, "git pull · compose up")
# Caddy -> server / valhalla
arrow([(540, 274), (540, 300)]); alabel(558, 290, ":8000", anchor="start")
arrow([(810, 274), (810, 300)]); alabel(828, 290, ":8002", anchor="start")
# Caddy -> Grafana (por el carril entre columnas central y derecha)
arrow([(945, 274), (945, 548), (1244, 548), (1244, OY)])
alabel(955, 540, ":3000", anchor="start")
# server -> valhalla (map-matching)
arrow([(660, 336), (690, 336)])
alabel(675, 327, "HTTP", anchor="middle")
# server -> db
arrow([(660, 462), (690, 462)])
alabel(675, 453, "SQL :5432", anchor="middle")
# server -> OpenTelemetry Collector (OTLP)
arrow([(490, 512), (490, OY)])
alabel(498, 538, "OTLP :4317", anchor="start")
# jobs (migrate/pipeline) -> db
arrow([(1000, 392), (1000, 406), (905, 406), (905, 420)], dashed=True)
alabel(952, 401, "alembic · SQL")
# cron -> pipeline
arrow([(1140, 420), (1140, 392)], dashed=True)
alabel(1140, 408, "compose run", anchor="middle")
# valhalla -> Geofabrik (descarga de tiles, por el hueco superior)
arrow([(810, 300), (810, 288), (1389, 288)])
alabel(1120, 282, "HTTPS · descarga OSM Bolivia (.pbf)")

# Observabilidad interna (gris, tenue)
for x1, x2 in [(625, 648), (798, 820), (970, 992), (1162, 1184)]:
    arrow([(x1, OY + 100), (x2, OY + 100)], color=GRAY, marker="arrL", sw=1.1)

# ---- Leyenda ------------------------------------------------------------
ly = H - 70
svg.append(f'<line x1="40" y1="{ly-20}" x2="{W-40}" y2="{ly-20}" stroke="{INK}" stroke-width="1"/>')
lx = 40
text(lx, ly, "Leyenda.", 12.5, "700", INK, "start")
lx += 78


def legend_box(lx, fill, stroke, dash, label):
    rect(lx, ly - 12, 18, 16, fill, stroke, sw=1.3, dash=dash)
    text(lx + 25, ly + 1, label, 11.5, "400", INK, "start")
    return lx + 36 + len(label) * 6.6


lx = legend_box(lx, NODE_BODY, INK, None, "Nodo (servidor / dispositivo)")
lx = legend_box(lx, COMP_FILL, COMP_STROKE, None, "Componente / contenedor")
lx = legend_box(lx, JOB_FILL, COMP_STROKE, "4 2", "Tarea one-shot / programada")
lx = legend_box(lx, EXT_FILL, INK, None, "Servicio externo")
# línea sólida vs discontinua
svg.append(f'<line x1="{lx}" y1="{ly-4}" x2="{lx+26}" y2="{ly-4}" stroke="{RULE}" '
           f'stroke-width="1.5" marker-end="url(#arr)"/>')
text(lx + 33, ly + 1, "Comunicación en ejecución", 11.5, "400", INK, "start")
lx += 33 + len("Comunicación en ejecución") * 6.6 + 14
svg.append(f'<line x1="{lx}" y1="{ly-4}" x2="{lx+26}" y2="{ly-4}" stroke="{RULE}" '
           f'stroke-width="1.5" stroke-dasharray="5 3" marker-end="url(#arr)"/>')
text(lx + 33, ly + 1, "Tarea / migración programada", 11.5, "400", INK, "start")

# Nota sobre Caddy y pie de figura
text(40, H - 34, "*  Caddy se ejecuta como proxy inverso compartido del host "
     "(red Docker externa www); el resto de servicios se orquestan con "
     "infra/deploy/docker-compose.yml.", 10.5, "400", "#555", "start", italic=True)
text(40, H - 14, "Figura. ", 12, "700", "#333", "start")
text(85, H - 14, "Diagrama de despliegue del entorno de producción de Puriy.",
     12, "400", "#444", "start", italic=True)

svg.append('</svg>')

with open("document/despliegue-produccion.svg", "w", encoding="utf-8") as f:
    f.write("\n".join(svg))
print(f"OK · {W}x{H}")
