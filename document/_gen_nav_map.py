#!/usr/bin/env python3
"""Genera el mapa de navegación de la app (SVG) en español."""
from html import escape

# ---- Datos del árbol de navegación -------------------------------------
# tipo: 'view' (pantalla/estado), 'modal' (overlay), 'alert' (confirmación)
TABS = [
    {
        "label": "Explorar",
        "sub": "Buscar y ver rutas de bus",
        "children": [
            {"label": "Búsqueda", "sub": "Origen y destino", "type": "view"},
            {"label": "Resultados", "sub": "Rutas disponibles", "type": "view"},
            {"label": "Detalle de ruta", "sub": "Pasos: caminar · tomar · bajar", "type": "view",
             "children": [
                 {"label": "Guardar ruta", "sub": "Recurrente · hora (opcional)", "type": "modal"},
             ]},
            {"label": "Detalle de línea", "sub": "Recorrido de la línea", "type": "view"},
        ],
    },
    {
        "label": "Trazar",
        "sub": "Grabar trayecto en bus",
        "children": [
            {"label": "Grabación", "sub": "Inactivo / grabando · duración · puntos", "type": "view"},
            {"label": "Permiso de ubicación", "sub": "Solicitud de GPS", "type": "modal"},
            {"label": "Guardar recorrido", "sub": "¿En qué línea viajaste?", "type": "modal",
             "children": [
                 {"label": "Selección de línea", "sub": "Existente o nueva línea", "type": "sub"},
                 {"label": "Tarifas", "sub": "Precio del pasaje", "type": "sub"},
                 {"label": "Desvío", "sub": "Razón y descripción", "type": "sub",
                  "children": [
                      {"label": "Confirmar desvío", "sub": "Publicar para todos", "type": "alert"},
                  ]},
             ]},
        ],
    },
    {
        "label": "Contribuir",
        "sub": "Votar rutas pendientes",
        "children": [
            {"label": "¿Conoces estas líneas?", "sub": "Familiaridad · aprobar / rechazar", "type": "view"},
            {"label": "¿Estas rutas son correctas?", "sub": "Líneas con segmentos pendientes", "type": "view"},
            {"label": "Votación por secciones", "sub": "Aprobar / rechazar cada sección", "type": "modal",
             "children": [
                 {"label": "Describir ramal", "sub": "Solo si hay ≥2 ramales", "type": "sub"},
                 {"label": "Resumen", "sub": "Listo · gracias", "type": "sub"},
             ]},
        ],
    },
    {
        "label": "Favoritos",
        "sub": "Rutas guardadas",
        "children": [
            {"label": "Recurrentes", "sub": "Viajes frecuentes", "type": "view"},
            {"label": "Para hoy", "sub": "Programados hoy", "type": "view"},
            {"label": "Detalle", "sub": "Pasos del viaje", "type": "view"},
            {"label": "Eliminar ruta", "sub": "Confirmación", "type": "alert"},
        ],
    },
]

# ---- Estilos (paleta académica, escala de grises sobria) ----------------
SERIF = "Georgia,'Times New Roman',serif"
INK = "#1A1A1A"
RULE = "#3A3A3A"
COLORS = {
    # (relleno, texto, borde)
    "root":  ("#2B2B2B", "#FFFFFF", "#2B2B2B"),
    "tabs":  ("#4A4A4A", "#FFFFFF", "#2B2B2B"),
    "tab":   ("#FFFFFF", "#1A1A1A", "#2B2B2B"),
    "view":  ("#FFFFFF", "#1A1A1A", "#6B6B6B"),
    "modal": ("#EDEDED", "#1A1A1A", "#6B6B6B"),
    "sub":   ("#F6F6F6", "#3A3A3A", "#9A9A9A"),
    "alert": ("#FFFFFF", "#1A1A1A", "#6B6B6B"),
}

COL_X = [40, 400, 760, 1120]
COL_W = 300
INDENT = 22
ROW_H = 70
BOX_H = 50
TAB_Y = 250
FIRST_CHILD_Y = TAB_Y + 96

svg = []


def box(x, y, w, h, label, sub, kind, font=14, rx=2):
    fill, txt, stroke = COLORS[kind]
    dash = ' stroke-dasharray="5 3"' if kind == "alert" else ""
    sw = 2 if kind in ("root", "tabs", "tab") else 1.2
    svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" '
               f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{dash}/>')
    if sub:
        svg.append(f'<text x="{x+14}" y="{y+22}" font-family="{SERIF}" '
                   f'font-size="{font}" font-weight="700" fill="{txt}">{escape(label)}</text>')
        svg.append(f'<text x="{x+14}" y="{y+39}" font-family="{SERIF}" '
                   f'font-size="11" font-style="italic" fill="{txt}" opacity="0.75">{escape(sub)}</text>')
    else:
        svg.append(f'<text x="{x+w/2}" y="{y+h/2+5}" text-anchor="middle" '
                   f'font-family="{SERIF}" font-size="{font}" '
                   f'font-weight="700" fill="{txt}">{escape(label)}</text>')


def elbow(x1, y1, x2, y2, color=RULE):
    # conector en forma de L desde abajo del padre a la izquierda del hijo
    svg.append(f'<path d="M {x1} {y1} V {y2} H {x2}" fill="none" '
               f'stroke="{color}" stroke-width="1"/>')


def straight(x1, y1, x2, y2, color=RULE):
    svg.append(f'<path d="M {x1} {y1} V {(y1+y2)/2} H {x2} V {y2}" fill="none" '
               f'stroke="{color}" stroke-width="1"/>')


# layout recursivo de los hijos de una pestaña
y_cursor = 0


def render_children(children, col_x, depth, parent_x, parent_bottom):
    global y_cursor
    for ch in children:
        x = col_x + depth * INDENT
        w = COL_W - depth * INDENT
        y = y_cursor
        # conector L del padre a este hijo
        elbow(parent_x + 16, parent_bottom, x, y + BOX_H / 2)
        box(x, y, w, BOX_H, ch["label"], ch.get("sub", ""), ch["type"])
        y_cursor += ROW_H
        if ch.get("children"):
            render_children(ch["children"], col_x, depth + 1, x, y + BOX_H)


# ---- Calcular altura total ---------------------------------------------
def count_rows(children):
    n = 0
    for ch in children:
        n += 1
        if ch.get("children"):
            n += count_rows(ch["children"])
    return n


max_rows = max(count_rows(t["children"]) for t in TABS)
height = int(FIRST_CHILD_Y + max_rows * ROW_H + 110)
width = 1460

svg.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
           f'viewBox="0 0 {width} {height}" font-family="{SERIF}">')
svg.append(f'<rect width="{width}" height="{height}" fill="#FCFCFA"/>')

# Título
svg.append(f'<text x="{width/2}" y="48" text-anchor="middle" font-size="24" '
           f'font-weight="700" fill="{INK}">Estructura de navegación de la aplicación</text>')
svg.append(f'<text x="{width/2}" y="72" text-anchor="middle" font-size="13" '
           f'font-style="italic" fill="#555">Puriy — app móvil (Expo / React Native): pestañas, pantallas y ventanas</text>')
svg.append(f'<line x1="40" y1="84" x2="{width-40}" y2="84" stroke="{INK}" stroke-width="1"/>')

# Raíz
root_w, root_h = 380, 54
root_x = (width - root_w) / 2
root_y = 96
box(root_x, root_y, root_w, root_h, "Inicio", "index → redirige a Explorar", "root")

# (tabs)
tabs_w, tabs_h = 380, 50
tabs_x = (width - tabs_w) / 2
tabs_y = 178
box(tabs_x, tabs_y, tabs_w, tabs_h, "(tabs) · Barra de pestañas", "", "tabs", font=15)
straight(width / 2, root_y + root_h, width / 2, tabs_y)

# Pestañas + hijos
for i, tab in enumerate(TABS):
    cx = COL_X[i] + COL_W / 2
    box(COL_X[i], TAB_Y, COL_W, 56, tab["label"], tab["sub"], "tab", font=17)
    # conector de (tabs) a la pestaña
    straight(width / 2, tabs_y + tabs_h, cx, TAB_Y)
    y_cursor = FIRST_CHILD_Y
    render_children(tab["children"], COL_X[i], 0, COL_X[i], TAB_Y + 56)

# ---- Leyenda ------------------------------------------------------------
legend = [
    ("tab", "Pestaña"),
    ("view", "Pantalla / estado"),
    ("modal", "Ventana modal"),
    ("sub", "Paso dentro de modal"),
    ("alert", "Confirmación"),
]
ly = height - 62
svg.append(f'<line x1="40" y1="{ly-22}" x2="{width-40}" y2="{ly-22}" stroke="{INK}" stroke-width="1"/>')
lx = 40
svg.append(f'<text x="{lx}" y="{ly}" font-size="12.5" font-weight="700" fill="{INK}">Leyenda.</text>')
lx += 72
for kind, name in legend:
    fill, txt, stroke = COLORS[kind]
    dash = ' stroke-dasharray="4 2.5"' if kind == "alert" else ""
    svg.append(f'<rect x="{lx}" y="{ly-12}" width="17" height="17" rx="2" fill="{fill}" stroke="{stroke}" stroke-width="1.2"{dash}/>')
    svg.append(f'<text x="{lx+25}" y="{ly+1}" font-size="12" fill="{INK}">{escape(name)}</text>')
    lx += 56 + len(name) * 7

# Pie de figura
svg.append(f'<text x="40" y="{height-26}" font-size="12" fill="#444">'
           f'<tspan font-weight="700">Figura.</tspan> '
           f'<tspan font-style="italic">Mapa de navegación de la aplicación móvil Puriy.</tspan></text>')

svg.append('</svg>')

with open("document/mapa-navegacion-app.svg", "w", encoding="utf-8") as f:
    f.write("\n".join(svg))
print(f"OK · {width}x{height}")
