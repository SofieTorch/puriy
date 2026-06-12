// Use case diagram — pure Typst (no external packages)
//
// Coordinate system: I draw on a fixed-size canvas with `place` so the layout
// stays predictable. All coordinates are in millimetres from the top-left of
// the canvas box.

#set page(paper: "a4")
#set text(font: "Arial", size: 9pt)

// Lucidchart/drawio-ish palette: dark slate strokes on a soft off-white fill,
// muted gray for connectors, lighter gray for «extends» relations.
#let node-stroke = rgb("#37474f")
#let node-fill   = rgb("#fafafa")
#let edge-color  = rgb("#546e7a")
#let ext-color   = rgb("#90a4ae")
#let bound-color = rgb("#90a4ae")

// ----- helpers -----------------------------------------------------------

// An ellipse-shaped use case at (x, y) (its centre), with the given size.
#let usecase(x, y, w, h, body, color: node-stroke) = place(
  top + left,
  dx: x - w / 2,
  dy: y - h / 2,
  ellipse(
    width: w,
    height: h,
    stroke: 1pt + color,
    fill: node-fill,
    inset: 4pt,
  )[
    #set align(center + horizon)
    #body
  ],
)

// A rectangular node (for the "Sistema" actor box, drawn as a rectangle in the
// original diagram).
#let rectnode(x, y, w, h, body, color: node-stroke) = place(
  top + left,
  dx: x - w / 2,
  dy: y - h / 2,
  box(
    width: w,
    height: h,
    stroke: 1pt + color,
    fill: node-fill,
    radius: 2pt,
    inset: 4pt,
  )[#set align(center + horizon); #body],
)

// A stick-figure actor centred horizontally at x, with the head top at y.
#let actor(x, y, label) = {
  let head-r = 2.5mm
  // head (filled circle)
  place(top + left, dx: x - head-r, dy: y, circle(radius: head-r, fill: black))
  // body
  place(top + left, dx: x, dy: y + 2 * head-r, line(
    start: (0pt, 0pt), end: (0pt, 7mm), stroke: 1pt,
  ))
  // arms
  place(top + left, dx: x - 5mm, dy: y + 7mm, line(
    start: (0pt, 0pt), end: (10mm, 0pt), stroke: 1pt,
  ))
  // legs
  place(top + left, dx: x, dy: y + 12mm, line(
    start: (0pt, 0pt), end: (-4mm, 6mm), stroke: 1pt,
  ))
  place(top + left, dx: x, dy: y + 12mm, line(
    start: (0pt, 0pt), end: (4mm, 6mm), stroke: 1pt,
  ))
  // label
  place(top + left, dx: x - 20mm, dy: y + 22mm, box(width: 40mm)[
    #set align(center)
    #label
  ])
}

// Straight line from (x1, y1) to (x2, y2) given in mm. With an open-triangle
// arrowhead at the end. Optionally dashed; optional gray text label.
#let arrow(x1, y1, x2, y2, dashed: false, color: edge-color, label: none) = {
  // Convert all coordinates to unitless numbers (in mm).
  let ax = x1 / 1mm
  let ay = y1 / 1mm
  let cx = x2 / 1mm
  let cy = y2 / 1mm

  let dx = cx - ax
  let dy = cy - ay
  let len = calc.sqrt(dx * dx + dy * dy)
  let ux = dx / len
  let uy = dy / len

  // base of the arrowhead (in mm)
  let head = 2.5
  let bx = cx - ux * head
  let by = cy - uy * head

  let stroke-style = if dashed {
    (paint: color, thickness: 0.8pt, dash: "dashed")
  } else {
    (paint: color, thickness: 1pt)
  }

  // line
  place(top + left, dx: ax * 1mm, dy: ay * 1mm, line(
    start: (0pt, 0pt),
    end: ((bx - ax) * 1mm, (by - ay) * 1mm),
    stroke: stroke-style,
  ))

  // open triangle arrowhead
  let nx = -uy
  let ny = ux
  let half = 1.6
  let p1x = bx + nx * half
  let p1y = by + ny * half
  let p2x = bx - nx * half
  let p2y = by - ny * half
  place(top + left, dx: 0mm, dy: 0mm, path(
    closed: true,
    stroke: (paint: color, thickness: 1pt),
    fill: white,
    (cx * 1mm, cy * 1mm),
    (p1x * 1mm, p1y * 1mm),
    (p2x * 1mm, p2y * 1mm),
  ))

  if label != none {
    let mx = (ax + cx) / 2
    let my = (ay + cy) / 2
    // If the line is mostly vertical, shift the label to the right;
    // otherwise centre it as before.
    let vertical = calc.abs(cx - ax) < calc.abs(cy - ay)
    let lx = if vertical { mx + 2 } else { mx - 10 }
    let ly = my - 3
    place(top + left, dx: lx * 1mm, dy: ly * 1mm, box(width: 20mm)[
      #set align(left)
      #set text(size: 7pt, fill: gray)
      #label
    ])
  }
}

// ----- the diagram canvas ------------------------------------------------

#block(width: 100%, height: 100%, [

  // System boundary (subtle gray, slightly rounded — drawio-style container)
  #place(top + left, dx: 35mm, dy: 2mm, rect(
    width: 135mm, height: 168mm,
    stroke: 0.8pt + bound-color,
    radius: 3pt,
  ))
  #place(top + left, dx: 38mm, dy: 4mm, text(size: 11pt, fill: node-stroke)[Aplicación])

  // Actors (head-top y)
  #actor(15mm, 10mm,  [Usuario])
  #actor(15mm, 100mm, [Usuario \ Contribuidor])

  // Inheritance: Contribuidor -> Usuario.
  // Tip at y=40 lands just below Usuario's label (label sits ~y=32-37),
  // so the arrowhead doesn't overlap the "Usuario" text.
  #arrow(15mm, 100mm, 15mm, 40mm, label: [hereda])

  // ---------- USUARIO column -----------
  #let W1 = 36mm
  #let H1 = 14mm

  #usecase(70mm, 20mm,  W1, H1, [CU-01: \ Planificar ruta])
  #usecase(70mm, 38mm,  W1, H1, [CU-02: Consultar \ líneas cercanas])
  #usecase(70mm, 56mm,  W1, H1, [CU-04: Guardar \ ruta])

  // CU-03 — extension target, upper-right
  #usecase(135mm, 29mm, W1, H1, [CU-03: Consultar \ desvíos activos])

  // ---------- CONTRIBUIDOR column -----
  #usecase(70mm, 78mm,  W1, H1, [CU-05: Grabar \ recorrido])
  #usecase(70mm, 95mm,  W1, H1, [CU-07: Reportar \ desvío activo])
  #usecase(70mm, 112mm, W1, H1, [CU-08: Registrar \ tarifa])
  #usecase(70mm, 130mm, W1, H1, [CU-10: Validar \ ruta inferida])

  // CU-06 and CU-09 — extension targets from CU-05
  #usecase(135mm, 65mm, W1, H1, [CU-06: Proponer \ nueva línea])
  #usecase(135mm, 82mm, W1, H1, [CU-09: Confirmar \ tarifa])

  // ---------- SISTEMA column -----------
  #usecase(135mm, 100mm, W1, H1,        [CU-11: Reconstruir \ rutas])
  #usecase(135mm, 117mm, W1, H1,        [CU-12: Inferir \ horarios])
  #usecase(135mm, 135mm, W1 + 5mm, H1 + 2mm,  [CU-13: Notificar \ desvíos en rutas \ recurrentes])
  #usecase(135mm, 153mm, W1, H1,        [CU-14: Notificar \ inicio de ruta])

  // Sistema actor — placed OUTSIDE the application boundary (right side).
  // UML convention for non-human actors: rectangle with «actor» stereotype.
  // x=185 keeps the right edge (x=198) inside the A4-portrait usable area.
  #place(top + left, dx: 185mm - 13mm, dy: 122mm,
    text(size: 7pt, fill: node-stroke, style: "italic")[«actor»])
  #rectnode(185mm, 130mm, 26mm, 12mm, [Sistema])

  // ----- associations ---------------------------------------------------

  // Usuario -> use cases (left column, top half)
  #arrow(20mm, 17mm,  52mm, 20mm)
  #arrow(20mm, 17mm,  52mm, 38mm)
  #arrow(20mm, 17mm,  52mm, 56mm)

  // Contribuidor -> use cases (left column, bottom half)
  #arrow(20mm, 107mm, 52mm, 78mm)
  #arrow(20mm, 107mm, 52mm, 95mm)
  #arrow(20mm, 107mm, 52mm, 112mm)
  #arrow(20mm, 107mm, 52mm, 130mm)

  // Sistema -> system-driven use cases (right column).
  // Sistema's left edge is at x = 185 - 13 = 172mm.
  #arrow(172mm, 130mm, 153mm, 100mm)
  #arrow(172mm, 130mm, 153mm, 117mm)
  #arrow(172mm, 130mm, 156mm, 135mm)
  #arrow(172mm, 130mm, 153mm, 153mm)

  // ----- «extends» relations -------------------------------------------
  #arrow(88mm, 20mm, 117mm, 29mm, dashed: true, color: ext-color, label: [«extiende»])
  #arrow(88mm, 38mm, 117mm, 29mm, dashed: true, color: ext-color, label: [«extiende»])
  #arrow(88mm, 78mm, 117mm, 65mm, dashed: true, color: ext-color, label: [«extiende»])
  #arrow(88mm, 78mm, 117mm, 82mm, dashed: true, color: ext-color, label: [«extiende»])
])

#pagebreak()

// ============================================================
// UML component diagram — system architecture
// ============================================================
//
// Compact layered view: each box carries the UML component icon
// (small rectangle with two tabs) in its top-right corner. Solid
// arrows are runtime use; dashed arrows are package dependencies.

// UML component icon: a small rectangle with two tabs poking out of
// its left side.
#let comp-icon(x, y) = {
  place(top + left, dx: x + 0.8mm, dy: y, rect(
    width: 3mm, height: 4mm,
    stroke: 0.5pt + node-stroke,
    fill: white,
  ))
  place(top + left, dx: x, dy: y + 0.5mm, rect(
    width: 1.6mm, height: 0.9mm,
    stroke: 0.5pt + node-stroke,
    fill: white,
  ))
  place(top + left, dx: x, dy: y + 2.3mm, rect(
    width: 1.6mm, height: 0.9mm,
    stroke: 0.5pt + node-stroke,
    fill: white,
  ))
}

// A UML component: rectangle + bold title + small description +
// component icon in the top-right corner.
#let comp(x, y, w, h, title, desc: none) = {
  let bx = x - w / 2
  let by = y - h / 2
  place(top + left, dx: bx, dy: by, box(
    width: w, height: h,
    stroke: 0.8pt + node-stroke,
    fill: node-fill,
    radius: 1pt,
    inset: (left: 4pt, right: 16pt, top: 3pt, bottom: 3pt),
  )[
    #set align(center + horizon)
    #text(weight: "bold", size: 8pt)[#title]
    #if desc != none [
      \ #text(size: 6.5pt, fill: gray)[#desc]
    ]
  ])
  comp-icon(bx + w - 5.5mm, by + 1.6mm)
}

// Grouping boundary with title in the top-left corner.
#let boundary(x, y, w, h, title) = {
  place(top + left, dx: x, dy: y, rect(
    width: w, height: h,
    stroke: 0.7pt + bound-color,
    radius: 2pt,
  ))
  place(top + left, dx: x + 2.5mm, dy: y + 1.5mm,
    text(size: 8pt, fill: node-stroke)[#title])
}

// UML ball-and-socket joint — a small "lollipop" (provided interface)
// optionally wrapped by a "socket" half-circle (required interface).
// The socket cups the ball from below: rim at the ball's centre-line,
// arc curving downward past the ball's underside.
#let lollipop(x, y, r: 1.2mm, socket: false) = {
  // Provided-interface ball.
  place(top + left, dx: x - r, dy: y - r, circle(
    radius: r,
    stroke: 0.8pt + node-stroke,
    fill: white,
  ))
  // Required-interface socket — bottom half-circle slightly larger than
  // the ball, drawn as two cubic Bezier quarters (Bezier circle constant
  // k = 0.5523).
  if socket {
    let R = r * 1.55
    let k = 0.5522847498
    place(top + left, dx: x - R, dy: y, curve(
      stroke: 0.8pt + node-stroke,
      fill: none,
      curve.move((0mm, 0mm)),
      curve.cubic((0mm, k * R), (R - k * R, R), (R, R)),
      curve.cubic((R + k * R, R), (2 * R, k * R), (2 * R, 0mm)),
    ))
  }
}

== Arquitectura del sistema

#align(center, block(width: 158mm, height: 128mm, [

  // ----- layer boundaries ------------------------------------------
  #boundary(2mm,   2mm, 154mm, 25mm, [Cliente])
  #boundary(2mm,  30mm, 154mm, 28mm, [Servicios del sistema])
  #boundary(2mm,  61mm, 154mm, 27mm, [Paquetes internos])
  #boundary(2mm,  91mm, 154mm, 27mm, [Dependencias externas])

  // ----- Cliente ---------------------------------------------------
  #comp(45mm,  15mm, 50mm, 13mm, [Aplicación móvil],    desc: [cliente Android / iOS])
  #comp(115mm, 15mm, 50mm, 13mm, [Base de datos local], desc: [SQLite · Drizzle])

  // ----- Servicios del sistema -------------------------------------
  #comp(45mm,  46mm, 50mm, 14mm, [API REST],             desc: [FastAPI · interfaz HTTP])
  #comp(115mm, 46mm, 56mm, 14mm, [Entorno exploratorio], desc: [transit-lab · Marimo])

  // ----- Paquetes internos -----------------------------------------
  #comp(30mm,  76mm, 42mm, 13mm, [database], desc: [modelos y migraciones])
  #comp(79mm,  76mm, 42mm, 13mm, [pipeline], desc: [reconstrucción de rutas])
  #comp(128mm, 76mm, 42mm, 13mm, [geodata],  desc: [procesamiento geoespacial])

  // ----- Dependencias externas -------------------------------------
  #comp(45mm,  106mm, 60mm, 13mm, [PostgreSQL + PostGIS], desc: [almacenamiento espacial])
  #comp(115mm, 106mm, 46mm, 13mm, [Valhalla],             desc: [map-matching HMM])

  // ----- arrows ----------------------------------------------------

  // App móvil writes to its local DB; app talks to API REST.
  #arrow(70mm,  15mm,  90mm, 15mm)
  #arrow(45mm,  21.5mm, 45mm, 39mm)
  // Provided-interface lollipop: API REST exposes HTTP for the mobile app.
  #lollipop(45mm, 28mm, socket: true)

  // Servicios -> Paquetes internos («use» dependencies, dashed).
  #arrow(45mm,  53mm,  30mm, 69.5mm, dashed: true, color: ext-color)
  #arrow(45mm,  53mm, 128mm, 69.5mm, dashed: true, color: ext-color)
  #arrow(115mm, 53mm,  30mm, 69.5mm, dashed: true, color: ext-color)
  #arrow(115mm, 53mm,  79mm, 69.5mm, dashed: true, color: ext-color)
  #arrow(115mm, 53mm, 128mm, 69.5mm, dashed: true, color: ext-color)

  // pipeline depends on database (left) and geodata (right).
  #arrow(58mm, 76mm,  51mm, 76mm, dashed: true, color: ext-color)
  #arrow(100mm, 76mm, 107mm, 76mm, dashed: true, color: ext-color)

  // Paquetes -> Dependencias externas.
  #arrow(30mm,  82.5mm,  45mm, 99.5mm)
  #arrow(128mm, 82.5mm, 115mm, 99.5mm)
  // Provided-interface lollipop: Valhalla exposes its HTTP API to geodata.
  #lollipop(121.5mm, 90.5mm, socket: true)
]))

#pagebreak()

// ============================================================
// Sequence diagram — registro de recorrido (trace recording)
// ============================================================
//
// All sizes (lifeline x positions, row spacing, fonts) are derived
// from the actual content area via `layout`, so the diagram always
// fills the page regardless of margins or paper size.

#layout(size => {
  let W = size.width
  let H = size.height

  // ---- horizontal layout: 5 lifelines evenly spread ----
  let xL = W * 0.04
  let xR = W * 0.96
  let step = (xR - xL) / 4
  let xs = (xL, xL + step, xL + 2 * step, xL + 3 * step, xL + 4 * step)
  let (xUser, xApp, xSens, xApi, xDb) = xs

  // ---- vertical layout: header band + grid of message rows ----
  let hdr-h = H * 0.045
  let yB = H * 0.995           // bottom of lifelines
  let n-rows = 27              // total grid slots between header and bottom
  let row = (yB - hdr-h) / n-rows
  let yT = hdr-h + row * 0.7   // first message row, leaves padding under header
  let r(i) = yT + row * i

  // ---- font sizes (small enough that the diagram never overflows) ----
  let f-name = 7.5pt
  let f-stereotype = 5.5pt
  let f-msg = 6.5pt
  let f-tab = 5.5pt

  // ---- box dimensions (relative to step / row) ----
  let p-w = step * 0.65
  let self-w = step * 0.13
  let self-h = row * 0.5

  // ============ helpers (closures over W, H, fonts) ============

  let participant(cx, label, w: p-w, actor: false) = place(
    top + left, dx: cx - w / 2, dy: 0pt,
    box(
      width: w, height: hdr-h,
      stroke: 0.8pt + node-stroke,
      fill: node-fill,
      radius: 1pt,
      inset: 1.5pt,
    )[
      #set align(center + horizon)
      #if actor [
        #text(size: f-stereotype, fill: gray, style: "italic")[«actor»] \
      ]
      #text(weight: "bold", size: f-name)[#label]
    ],
  )

  let lifeline(cx) = place(top + left, dx: cx, dy: hdr-h, line(
    start: (0pt, 0pt), end: (0pt, yB - hdr-h),
    stroke: (paint: bound-color, thickness: 0.5pt, dash: "dashed"),
  ))

  let msg(xa, xb, y, label, dashed: false) = {
    arrow(xa, y, xb, y, dashed: dashed)
    let mx = (xa + xb) / 2
    let lw = step * 1.6
    place(top + left, dx: mx - lw / 2, dy: y - row * 0.55, box(width: lw)[
      #set align(center)
      #set text(size: f-msg, fill: node-stroke)
      #label
    ])
  }

  let self-msg(cx, y, label) = {
    place(top + left, dx: cx, dy: y, line(
      start: (0pt, 0pt), end: (self-w, 0pt),
      stroke: 0.9pt + edge-color,
    ))
    place(top + left, dx: cx + self-w, dy: y, line(
      start: (0pt, 0pt), end: (0pt, self-h),
      stroke: 0.9pt + edge-color,
    ))
    arrow(cx + self-w, y + self-h, cx, y + self-h)
    place(top + left, dx: cx + self-w + 1pt, dy: y - 1pt,
      box(width: step * 1.4)[
        #set text(size: f-msg, fill: node-stroke)
        #label
      ])
  }

  let frame(xa, ya, xb, yb, kind, label) = {
    let tab-w = step * 0.28
    let tab-h = row * 0.55
    place(top + left, dx: xa, dy: ya, rect(
      width: xb - xa, height: yb - ya,
      stroke: 0.5pt + bound-color,
      fill: none,
    ))
    place(top + left, dx: xa, dy: ya, box(
      width: tab-w, height: tab-h,
      stroke: 0.5pt + bound-color,
      fill: rgb("#eef2f5"),
      inset: 1.5pt,
    )[
      #set align(left + horizon)
      #set text(size: f-tab, weight: "bold", fill: node-stroke)
      #kind
    ])
    place(top + left, dx: xa + tab-w + 1mm, dy: ya + 1pt,
      text(size: f-msg, fill: node-stroke)[\[#label\]])
  }

  let note(xa, xb, y, label) = place(top + left, dx: xa, dy: y, box(
    width: xb - xa, height: row * 1.0,
    stroke: 0.5pt + node-stroke,
    fill: rgb("#fff8c4"),
    inset: 1.5pt,
  )[
    #set align(center + horizon)
    #set text(size: f-msg, fill: node-stroke, style: "italic")
    #label
  ])

  // ============ the diagram ============

  block(width: W, height: H, {
    // ---- participants & lifelines ----
    participant(xUser, [Usuario], w: step * 0.55, actor: true)
    participant(xApp,  [App móvil])
    participant(xSens, [Sensores])
    participant(xApi,  [API REST])
    participant(xDb,   [Base de datos], w: step * 0.85)

    lifeline(xUser); lifeline(xApp); lifeline(xSens); lifeline(xApi); lifeline(xDb)

    // ---- inicio de la grabación ----
    msg(xUser, xApp,  r(0.5), [desliza para iniciar])
    self-msg(xApp,    r(1.5), [crea sesión local (SQLite)])
    msg(xApp,  xSens, r(2.5), [inicia GPS y sensores])

    // ---- bucle de captura ----
    frame(xApp - step * 0.1, r(3.1), xSens + step * 0.5, r(6.2),
      [loop], [GPS cada 2 s · sensores cada 100 ms])
    msg(xSens, xApp, r(4.3), [lat, lng, ts · accel, gyro], dashed: true)
    self-msg(xApp,   r(5.3), [almacena en SQLite local])

    // ---- nota: continúa hasta detener ----
    note(xUser + step * 0.5, xSens + step * 0.4, r(6.8),
      [continúa hasta que el usuario detenga la grabación])

    // ---- detención y selección de línea ----
    msg(xUser, xApp,  r(8.5),  [desliza para detener])
    msg(xApp,  xSens, r(9.5),  [detiene captura])
    msg(xUser, xApp,  r(10.5), [selecciona línea])
    self-msg(xApp,    r(11.5), [marca como `pending_sync`])

    // ---- nota: sincronización ----
    note(xUser + step * 0.5, xDb + step * 0.2, r(12.7),
      [Sincronización · requiere conexión a la red])

    // ---- crear sesión en el servidor ----
    msg(xApp, xApi, r(14.4), [POST /recordings])
    msg(xApi, xDb,  r(15.4), [INSERT TripSession])
    msg(xDb,  xApi, r(16.4), [session id], dashed: true)
    msg(xApi, xApp, r(17.4), [201 \{ id \}], dashed: true)

    // ---- bucle de subida por lotes ----
    frame(xApp - step * 0.1, r(18.0), xDb + step * 0.2, r(20.6),
      [loop], [lotes de 100])
    msg(xApp, xApi, r(19.2), [POST /recordings/\{id\}/locations/batch])
    msg(xApp, xApi, r(20.1), [POST /recordings/\{id\}/sensors/batch])

    // ---- cierre y confirmación ----
    msg(xApp, xApi,  r(21.3), [POST /recordings/\{id\}/end \{ line\_id, path \}])
    msg(xApi, xDb,   r(22.3), [UPDATE session = completed])
    msg(xApi, xApp,  r(23.3), [200 OK], dashed: true)
    self-msg(xApp,   r(24.3), [borra datos locales])
    msg(xApp, xUser, r(25.5), [confirmación], dashed: true)
  })
})

#pagebreak()

// ============================================================
// Sequence diagram — votación por secciones (segment voting)
// ============================================================
//
// Shows the community-voting flow on the Contribute screen: how
// candidates are listed, how the user votes section-by-section,
// and how the server tallies edge-level counters.

#layout(size => {
  let W = size.width
  let H = size.height

  // ---- horizontal layout: 4 lifelines evenly spread ----
  let xL = W * 0.04
  let xR = W * 0.96
  let step = (xR - xL) / 3
  let xUser = xL
  let xApp = xL + step
  let xApi = xL + 2 * step
  let xDb = xL + 3 * step

  // ---- vertical grid ----
  let hdr-h = H * 0.045
  let yB = H * 0.995
  let n-rows = 19
  let row = (yB - hdr-h) / n-rows
  let yT = hdr-h + row * 0.7
  let r(i) = yT + row * i

  // ---- font sizes ----
  let f-name = 7.5pt
  let f-stereotype = 5.5pt
  let f-msg = 6.5pt
  let f-tab = 5.5pt

  // ---- box dimensions ----
  let p-w = step * 0.65

  // ============ helpers ============

  let participant(cx, label, w: p-w, actor: false) = place(
    top + left, dx: cx - w / 2, dy: 0pt,
    box(
      width: w, height: hdr-h,
      stroke: 0.8pt + node-stroke,
      fill: node-fill,
      radius: 1pt,
      inset: 1.5pt,
    )[
      #set align(center + horizon)
      #if actor [
        #text(size: f-stereotype, fill: gray, style: "italic")[«actor»] \
      ]
      #text(weight: "bold", size: f-name)[#label]
    ],
  )

  let lifeline(cx) = place(top + left, dx: cx, dy: hdr-h, line(
    start: (0pt, 0pt), end: (0pt, yB - hdr-h),
    stroke: (paint: bound-color, thickness: 0.5pt, dash: "dashed"),
  ))

  let msg(xa, xb, y, label, dashed: false) = {
    arrow(xa, y, xb, y, dashed: dashed)
    let mx = (xa + xb) / 2
    let lw = step * 1.6
    place(top + left, dx: mx - lw / 2, dy: y - row * 0.55, box(width: lw)[
      #set align(center)
      #set text(size: f-msg, fill: node-stroke)
      #label
    ])
  }

  let frame(xa, ya, xb, yb, kind, label) = {
    let tab-w = step * 0.28
    let tab-h = row * 0.55
    place(top + left, dx: xa, dy: ya, rect(
      width: xb - xa, height: yb - ya,
      stroke: 0.5pt + bound-color,
      fill: none,
    ))
    place(top + left, dx: xa, dy: ya, box(
      width: tab-w, height: tab-h,
      stroke: 0.5pt + bound-color,
      fill: rgb("#eef2f5"),
      inset: 1.5pt,
    )[
      #set align(left + horizon)
      #set text(size: f-tab, weight: "bold", fill: node-stroke)
      #kind
    ])
    place(top + left, dx: xa + tab-w + 1mm, dy: ya + 1pt,
      text(size: f-msg, fill: node-stroke)[\[#label\]])
  }

  // ============ the diagram ============

  block(width: W, height: H, {
    // Participants & lifelines
    participant(xUser, [Usuario], w: step * 0.55, actor: true)
    participant(xApp,  [App móvil])
    participant(xApi,  [API REST])
    participant(xDb,   [Base de datos], w: step * 0.85)

    lifeline(xUser); lifeline(xApp); lifeline(xApi); lifeline(xDb)

    // ---- listado inicial en la pestaña "Contribuir" ----
    msg(xUser, xApp, r(0.5), [abre pestaña «Contribuir»])
    msg(xApp,  xApi, r(1.7), [GET /vote/pending, /vote/lines/nearby])
    msg(xApi,  xDb,  r(2.7), [SELECT líneas con secciones pendientes])
    msg(xDb,   xApi, r(3.7), [líneas candidatas], dashed: true)
    msg(xApi,  xApp, r(4.7), [\{ pending, nearby \}], dashed: true)

    // ---- selección de una línea ----
    msg(xUser, xApp, r(5.9), [tap «Votar por secciones»])
    msg(xApp,  xApi, r(6.9), [GET /vote/\{line\_id\}/segment])
    msg(xApi,  xDb,  r(7.9), [SELECT Route + RouteEdges (agrupa secciones)])
    msg(xDb,   xApi, r(8.9), [ruta + aristas], dashed: true)
    msg(xApi,  xApp, r(9.9), [\{ sections, route\_geojson \}], dashed: true)

    // ---- bucle de votación por sección ----
    frame(xUser - step * 0.08, r(10.7), xDb + step * 0.08, r(16.5),
      [loop], [por sección])
    msg(xUser, xApp, r(12.0), [aprobar / rechazar])
    msg(xApp,  xApi, r(13.0), [POST /vote/\{line\_id\} \{ vote, section\_index \}])
    msg(xApi,  xDb,  r(14.0), [UPSERT EdgeVote · incrementa contadores])
    msg(xDb,   xApi, r(15.0), [ok], dashed: true)
    msg(xApi,  xApp, r(16.0), [\{ edges\_voted, vote \}], dashed: true)

    // ---- resumen final ----
    msg(xApp, xUser, r(17.5),
      [resumen: votaste en N secciones (X aprobadas, Y rechazadas)],
      dashed: true)
  })
})


// ============================================================
// Activity-diagram primitives (mm coordinates, like arrow())
// ============================================================
//
// All primitives place themselves at given (x, y) in mm. Designed to
// be composed inside a fixed-size canvas via #place / #box, mirroring
// the use case + sequence diagram conventions above.

// Initial node — filled black circle.
#let act-start(cx, cy, r: 1.6) = place(
  top + left, dx: (cx - r) * 1mm, dy: (cy - r) * 1mm,
  circle(radius: r * 1mm, fill: node-stroke, stroke: none),
)

// Final node — filled circle inside an open ring.
#let act-end(cx, cy, r-outer: 2.4, r-inner: 1.4) = {
  place(top + left, dx: (cx - r-outer) * 1mm, dy: (cy - r-outer) * 1mm,
    circle(radius: r-outer * 1mm, fill: none, stroke: 0.8pt + node-stroke))
  place(top + left, dx: (cx - r-inner) * 1mm, dy: (cy - r-inner) * 1mm,
    circle(radius: r-inner * 1mm, fill: node-stroke, stroke: none))
}

// Action — rounded rectangle with text. cx/cy is the centre.
#let act-action(cx, cy, w, h, label, fill: node-fill) = place(
  top + left, dx: (cx - w / 2) * 1mm, dy: (cy - h / 2) * 1mm,
  box(
    width: w * 1mm, height: h * 1mm,
    stroke: 0.8pt + node-stroke,
    fill: fill,
    radius: 2mm,
    inset: (x: 2mm, y: 1.5mm),
  )[
    #set align(center + horizon)
    #set text(size: 7pt, fill: node-stroke)
    #label
  ],
)

// Decision — diamond with question label. cx/cy is the centre.
#let act-decision(cx, cy, w, h, label) = {
  place(top + left, dx: 0mm, dy: 0mm, path(
    closed: true,
    stroke: 0.8pt + node-stroke,
    fill: rgb("#fff8e1"),
    ((cx) * 1mm, (cy - h / 2) * 1mm),
    ((cx + w / 2) * 1mm, (cy) * 1mm),
    ((cx) * 1mm, (cy + h / 2) * 1mm),
    ((cx - w / 2) * 1mm, (cy) * 1mm),
  ))
  place(top + left, dx: (cx - w / 2 + 2) * 1mm, dy: (cy - h / 2 + 0.5) * 1mm,
    box(width: (w - 4) * 1mm, height: (h - 1) * 1mm)[
      #set align(center + horizon)
      #set text(size: 6.5pt, fill: node-stroke)
      #label
    ])
}

// Fork/join bar — thick black horizontal bar.
#let act-bar(cx, cy, w, thickness: 1.2) = place(
  top + left, dx: (cx - w / 2) * 1mm, dy: (cy - thickness / 2) * 1mm,
  rect(width: w * 1mm, height: thickness * 1mm, fill: node-stroke, stroke: none),
)

// Activity-flow edge — same as arrow() but shifts the optional label
// closer to the line end (for branch labels like "Sí" / "No").
#let act-edge(x1, y1, x2, y2, label: none, label-near: "mid") = {
  arrow(x1 * 1mm, y1 * 1mm, x2 * 1mm, y2 * 1mm)
  if label != none {
    let f = if label-near == "start" { 0.18 }
            else if label-near == "end" { 0.82 }
            else { 0.5 }
    let lx = x1 + (x2 - x1) * f
    let ly = y1 + (y2 - y1) * f
    place(top + left, dx: (lx + 1.5) * 1mm, dy: (ly - 3) * 1mm,
      box(width: 20mm)[
        #set text(size: 6.5pt, fill: gray, weight: "bold")
        #label
      ])
  }
}

// Note attached to a node (yellow sticky).
#let act-note(cx, cy, w, h, label) = place(
  top + left, dx: (cx - w / 2) * 1mm, dy: (cy - h / 2) * 1mm,
  box(
    width: w * 1mm, height: h * 1mm,
    stroke: 0.5pt + node-stroke,
    fill: rgb("#fff8c4"),
    inset: 1.5mm,
  )[
    #set align(center + horizon)
    #set text(size: 6pt, fill: node-stroke, style: "italic")
    #label
  ],
)


// ============================================================
// Activity diagram — Deduplicación de líneas (Fig. 14)
// ============================================================

#let dedup-activity = block(width: 100%, height: 165mm, {
  // Canvas in mm. Centre column at 95mm, decisions branch left/right.
  let cx = 95
  let aw = 70    // action width
  let ah = 9     // action height
  let dw = 56    // decision width
  let dh = 18    // decision height

  act-start(cx, 5)
  act-edge(cx, 6.6, cx, 12)

  act-action(cx, 16, aw, ah, [Cargar todas las `Line[DRAFT]`])
  act-edge(cx, 20.5, cx, 26)

  act-decision(cx, 35, dw, dh, [¿Hay líneas DRAFT pendientes?])
  act-edge(cx + dw / 2, 35, cx + dw / 2 + 12, 35,
    label: [No], label-near: "start")
  act-edge(cx + dw / 2 + 12, 35, cx + dw / 2 + 12, 158)  // jump to end
  act-edge(cx, 44, cx, 50, label: [Sí], label-near: "end")

  act-action(cx, 55, aw, ah, [Normalizar nombre por línea\
    (lowercase + sin tildes + sin prefijos)])
  act-edge(cx, 60, cx, 65)

  act-action(cx, 70, aw, ah * 1.4,
    [Fusionar grupos con mismo nombre normalizado\
     (conserva la `Line` más antigua, marca el resto como `MERGED`)])
  act-edge(cx, 76.5, cx, 82)

  act-action(cx, 87, aw, ah * 1.4,
    [Para cada DRAFT restante:\
     ¿coincide con APPROVED/PENDING por nombre? → fusionar])
  act-edge(cx, 93.5, cx, 99)

  act-action(cx, 104, aw, ah * 1.6,
    [`_find_overlapping_line_pairs`:\
     `ST_Envelope(ST_Collect(computed_path))` por línea →\
     self-join con `ST_Intersects` + ratio área común])
  act-edge(cx, 112, cx, 118)

  act-decision(cx, 127, dw, dh, [¿Algún par con ratio ≥ 0.7?])
  act-edge(cx + dw / 2, 127, cx + 50, 127, label: [No], label-near: "start")
  act-edge(cx + 50, 127, cx + 50, 145)
  act-edge(cx, 136, cx, 141, label: [Sí], label-near: "end")

  act-action(cx, 146, aw, ah * 1.2,
    [Fusionar más reciente en más antigua\
     (`_merge_line` mueve TripSession + Trip)])
  act-edge(cx, 151, cx, 156)

  act-action(cx, 161, aw, ah,
    [Promover DRAFT no fusionadas a `PENDING`])
  act-edge(cx, 165.5, cx, 171)

  act-end(cx, 173)
})


// ============================================================
// Activity diagram — Pipeline completo (Fig. 15)
// ============================================================

#let pipeline-activity = block(width: 100%, height: 200mm, {
  let cx = 95
  let aw = 110
  let ah = 9
  let dy = 18

  act-start(cx, 5)
  act-edge(cx, 6.6, cx, 12)

  act-action(cx, 12 + dy * 0,    aw, ah,
    [`cleanup` — abandona sesiones colgadas, expira desvíos > 7 días])
  act-edge(cx, 17 + dy * 0, cx, 12 + dy * 0 - 6 + dy)

  act-action(cx, 12 + dy * 1,    aw, ah,
    [`deduplicate_lines` — colapsa DRAFT por nombre + bbox, promueve a PENDING])
  act-edge(cx, 17 + dy * 1, cx, 12 + dy * 1 - 6 + dy)

  act-action(cx, 12 + dy * 2,    aw, ah,
    [`clean_traces` — Valhalla map-match (HMM), 6 hilos paralelos])
  act-edge(cx, 17 + dy * 2, cx, 12 + dy * 2 - 6 + dy)

  act-action(cx, 12 + dy * 3,    aw, ah,
    [`reconstruct_routes` — clustering en ramales + estrategia por cluster])
  act-edge(cx, 17 + dy * 3, cx, 12 + dy * 3 - 6 + dy)

  act-action(cx, 12 + dy * 4,    aw, ah,
    [`resolve_edge_votes` — promueve aristas con ≥3 votos y ≥60 % a favor])
  act-edge(cx, 17 + dy * 4, cx, 12 + dy * 4 - 6 + dy)

  act-action(cx, 12 + dy * 5,    aw, ah,
    [`resolve_routes` — promueve `Route` con ≥80 % de aristas confirmadas])
  act-edge(cx, 17 + dy * 5, cx, 12 + dy * 5 - 6 + dy)

  act-action(cx, 12 + dy * 6,    aw, ah,
    [`resolve_line_votes` — promueve `Line` con ≥3 votos y ≥60 % a favor])
  act-edge(cx, 17 + dy * 6, cx, 12 + dy * 6 - 6 + dy)

  act-action(cx, 12 + dy * 7,    aw, ah,
    [`rebuild_graph` — reconstruye grafo de tránsito (bus + transferencias)])
  act-edge(cx, 17 + dy * 7, cx, 12 + dy * 7 - 6 + dy)

  act-action(cx, 12 + dy * 8,    aw, ah,
    [`infer_schedules` — frecuencias por línea, banda horaria + día])
  act-edge(cx, 17 + dy * 8, cx, 187)

  act-end(cx, 189)

  // Side note: tracking
  act-note(cx + 80, 100, 36, 28,
    [Cada paso registra\
     `PipelineStepResult`\
     (status, stats, error)\
     dentro del `PipelineRun`\
     padre.])
})


// ============================================================
// Activity diagram — Reconstrucción por ramal (Fig. 16)
// ============================================================

#let ramal-reconstruct-activity = block(width: 100%, height: 220mm, {
  let cx = 95
  let aw = 100
  let ah = 9
  let dw = 70
  let dh = 18

  act-start(cx, 5)
  act-edge(cx, 6.6, cx, 12)

  act-action(cx, 16, aw, ah,
    [Cargar `Trip[CLEAN]` de la línea (`load_reconstruction_traces_from_db`)])
  act-edge(cx, 20.5, cx, 26)

  act-decision(cx, 35, dw, dh, [`len(traces) ≥ min_trips`?])
  act-edge(cx + dw / 2, 35, cx + 60, 35, label: [No], label-near: "start")
  act-edge(cx + 60, 35, cx + 60, 215)
  act-edge(cx, 44, cx, 49, label: [Sí], label-near: "end")

  act-action(cx, 54, aw, ah,
    [Cargar ramales activos existentes
    (keyed por `ramal_label`)])
  act-edge(cx, 58.5, cx, 64)

  act-action(cx, 70, aw, ah * 1.6,
    [`cluster_traces_into_ramales`:\
     resamplear a 25m → matriz de Fréchet (con bbox prefiltro) →\
     clustering complete-linkage al threshold (200m) → asignar etiquetas])
  act-edge(cx, 78, cx, 84)

  // Per-cluster loop annotation
  act-note(cx + 80, 90, 32, 14,
    [Para cada cluster\
     (loop por ramal)])

  act-action(cx, 90, aw, ah,
    [`strategy.reconstruct(traces_del_cluster)`])
  act-edge(cx, 94.5, cx, 100)

  act-decision(cx, 109, dw, dh, [¿geojson tiene exactamente 1 feature?])
  act-edge(cx - dw / 2, 109, cx - 60, 109, label: [No], label-near: "start")
  act-edge(cx - 60, 109, cx - 60, 217)  // skip to end
  act-edge(cx, 118, cx, 124, label: [Sí], label-near: "end")

  act-decision(cx, 134, dw, dh, [¿Existe Route con esta `ramal_label`?])
  act-edge(cx + dw / 2, 134, cx + 50, 134, label: [No], label-near: "start")
  act-action(cx + 50, 152, 50, ah * 1.4,
    [`_save_reconstruction`\
     (Route v1 PENDING)])
  act-edge(cx + 50, 142, cx + 50, 145)
  act-edge(cx + 50, 159, cx + 50, 200)

  act-edge(cx, 143, cx, 150, label: [Sí], label-near: "end")
  act-action(cx, 156, aw, ah,
    [`discrete_frechet_distance_m(existing, candidate)`])
  act-edge(cx, 160.5, cx, 166)

  act-decision(cx, 175, dw, dh, [Fréchet < 50m?])
  act-edge(cx - dw / 2, 175, cx - 60 + 5, 175,
    label: [Sí (unchanged)], label-near: "start")
  act-action(cx - 50, 192, 50, ah * 1.4,
    [Bumpear `existing.last_compared_at`])
  act-edge(cx - 50, 175, cx - 50, 187)
  act-edge(cx - 50, 199, cx - 50, 215)

  act-edge(cx, 184, cx, 188,
    label: [No (≥50m)], label-near: "end")
  act-action(cx, 195, aw, ah * 1.4,
    [`_save_reconstruction`\
     (supersede + nueva versión)])
  act-edge(cx, 202, cx, 215)

  act-end(cx, 217)
})


// ============================================================
// Activity diagram — Cálculo de confidence_pct (Fig. 18)
// ============================================================

#let confidence-activity = block(width: 100%, height: 145mm, {
  let cx = 95
  let aw = 100
  let ah = 9
  let dw = 60
  let dh = 18

  act-start(cx, 5)
  act-edge(cx, 6.6, cx, 12)

  act-action(cx, 16, aw, ah,
    [Recibir `Detour` activo])
  act-edge(cx, 20.5, cx, 26)

  act-action(cx, 31, aw, ah,
    [`days = (now - last_confirmed_at).days`])
  act-edge(cx, 35.5, cx, 41)

  act-action(cx, 46, aw, ah * 1.2,
    [`time_factor = max(0, min(1, 1 - days / 14))`])
  act-edge(cx, 51, cx, 57)

  act-decision(cx, 66, dw, dh, [`time_factor == 0`?])
  act-edge(cx + dw / 2, 66, cx + 50, 66,
    label: [Sí], label-near: "start")
  act-action(cx + 50, 82, 40, ah, [Retornar 0])
  act-edge(cx + 50, 66, cx + 50, 78)
  act-edge(cx + 50, 87, cx + 50, 138)

  act-edge(cx, 75, cx, 81, label: [No], label-near: "end")
  act-action(cx, 87, aw, ah * 1.6,
    [`log_boost = log1p(max(0, count - 1)) / log1p(20)`\
     `corroboration_factor = min(1.0, 0.5 + 0.5 * log_boost)`])
  act-edge(cx, 95, cx, 101)

  act-action(cx, 107, aw, ah * 1.4,
    [`confidence = round(100 * time_factor * corroboration_factor)`\
     clamp a `[0, 100]`])
  act-edge(cx, 114, cx, 121)

  act-action(cx, 127, aw, ah, [Retornar `confidence_pct`])
  act-edge(cx, 131.5, cx, 138)

  act-end(cx, 140)
})


// ============================================================
// Activity diagram — Construcción del transit_graph (Fig. 21)
// ============================================================

#let transit-graph-activity = block(width: 100%, height: 175mm, {
  let cx = 95
  let aw = 110
  let ah = 9

  act-start(cx, 5)
  act-edge(cx, 6.6, cx, 12)

  act-action(cx, 16, aw, ah,
    [`invalidate_graph()` — descartar caché previo en memoria])
  act-edge(cx, 20.5, cx, 26)

  act-action(cx, 32, aw, ah * 1.6,
    [SELECT `Line + Route + RouteEdge`
    WHERE `Line.status IN {APPROVED, PENDING}`
    AND `Route.status != SUPERSEDED`])
  act-edge(cx, 39, cx, 45)

  // Per-line loop bar
  act-bar(cx, 51, 80)
  place(top + left, dx: (cx + 45) * 1mm, dy: 49 * 1mm,
    text(size: 6.5pt, fill: gray, weight: "bold")[loop por línea])
  act-edge(cx, 52.5, cx, 58)

  act-action(cx, 64, aw, ah * 1.4,
    [Por cada `Route` no superseded:\
     `is_confirmed = (route.status == CONFIRMED)`])
  act-edge(cx, 71, cx, 77)

  act-action(cx, 83, aw, ah * 1.6,
    [Por cada `RouteEdge` ordenado por `sequence`:\
     crear/recuperar nodos por endpoints,\
     agregar arista de bus `(line_id, route_id, is_confirmed, forward)`])
  act-edge(cx, 91, cx, 96)

  act-bar(cx, 100, 80)
  act-edge(cx, 101.5, cx, 107)

  act-action(cx, 113, aw, ah * 1.6,
    [Computar transferencias: para cada par de nodos
    cuya distancia ≤ `walking_threshold` (m), agregar arista
    `transfer` con costo derivado del tiempo de caminata])
  act-edge(cx, 121, cx, 127)

  act-action(cx, 133, aw, ah * 1.4,
    [Cachear grafo en memoria a nivel módulo
    (`transit_graph._cached_graph`)])
  act-edge(cx, 140, cx, 146)

  act-action(cx, 152, aw, ah * 1.4,
    [Retornar `(nodes, bus_edges, transfer_edges)`
    como estadísticas del paso])
  act-edge(cx, 159, cx, 165)

  act-end(cx, 167)
})


// ============================================================
// Sequence-diagram helpers (canvas-relative version)
// ============================================================
//
// Variant of the inline closures used inside the page-filling
// `#layout(size => {...})` blocks above. These take a canvas size
// and lifeline xs as parameters so the diagram can be used as an
// importable block at fixed dimensions inside #figure(...).

#let sd-participant(cx, label, w, hdr-h, actor: false) = place(
  top + left, dx: (cx - w / 2) * 1mm, dy: 0pt,
  box(
    width: w * 1mm, height: hdr-h * 1mm,
    stroke: 0.8pt + node-stroke,
    fill: node-fill,
    radius: 1pt,
    inset: 1.5pt,
  )[
    #set align(center + horizon)
    #if actor [
      #text(size: 5.5pt, fill: gray, style: "italic")[«actor»] \
    ]
    #text(weight: "bold", size: 7pt)[#label]
  ],
)

#let sd-lifeline(cx, hdr-h, h-total) = place(
  top + left, dx: cx * 1mm, dy: hdr-h * 1mm,
  line(
    start: (0pt, 0pt), end: (0pt, (h-total - hdr-h) * 1mm),
    stroke: (paint: bound-color, thickness: 0.5pt, dash: "dashed"),
  ),
)

#let sd-msg(xa, xb, y, label, dashed: false) = {
  arrow(xa * 1mm, y * 1mm, xb * 1mm, y * 1mm, dashed: dashed)
  let mx = (xa + xb) / 2
  let lw = calc.abs(xb - xa) * 0.95
  place(top + left, dx: (mx - lw / 2) * 1mm, dy: (y - 4) * 1mm,
    box(width: lw * 1mm)[
      #set align(center)
      #set text(size: 6.5pt, fill: node-stroke)
      #label
    ])
}

#let sd-self-msg(cx, y, label, w: 6, h: 4) = {
  place(top + left, dx: cx * 1mm, dy: y * 1mm, line(
    start: (0pt, 0pt), end: (w * 1mm, 0pt),
    stroke: 0.9pt + edge-color,
  ))
  place(top + left, dx: (cx + w) * 1mm, dy: y * 1mm, line(
    start: (0pt, 0pt), end: (0pt, h * 1mm),
    stroke: 0.9pt + edge-color,
  ))
  arrow((cx + w) * 1mm, (y + h) * 1mm, cx * 1mm, (y + h) * 1mm)
  place(top + left, dx: (cx + w + 1) * 1mm, dy: (y - 1) * 1mm,
    box(width: 60mm)[
      #set text(size: 6.5pt, fill: node-stroke)
      #label
    ])
}

#let sd-note(xa, xb, y, label, h: 6) = place(
  top + left, dx: xa * 1mm, dy: y * 1mm, box(
    width: (xb - xa) * 1mm, height: h * 1mm,
    stroke: 0.5pt + node-stroke,
    fill: rgb("#fff8c4"),
    inset: 1.5pt,
  )[
    #set align(center + horizon)
    #set text(size: 6pt, fill: node-stroke, style: "italic")
    #label
  ],
)


// ============================================================
// Sequence diagram — Proponer nueva línea (Fig. 13, CU-06)
// ============================================================

#let proponer-linea-sequence = block(width: 100%, height: 95mm, {
  let W = 165
  let H = 95
  let hdr-h = 8
  // Lifelines: Usuario | App | Server | BaseDatos
  let xUser = 18
  let xApp  = 60
  let xApi  = 105
  let xDb   = 150

  sd-participant(xUser, [Usuario], 30, hdr-h, actor: true)
  sd-participant(xApp,  [App móvil], 38, hdr-h)
  sd-participant(xApi,  [Server (FastAPI)], 38, hdr-h)
  sd-participant(xDb,   [Base de datos], 30, hdr-h)

  sd-lifeline(xUser, hdr-h, H)
  sd-lifeline(xApp,  hdr-h, H)
  sd-lifeline(xApi,  hdr-h, H)
  sd-lifeline(xDb,   hdr-h, H)

  // Inicio
  sd-msg(xUser, xApp, 17, [cierra grabación, "proponer nueva línea"])
  sd-self-msg(xApp, 24, [valida `customLineName`])

  // Crear sesión + línea
  sd-msg(xApp, xApi, 36, [`POST /recordings/\{id\}/end \{ line\_name \}`])
  sd-msg(xApi, xDb,  44, [`INSERT Line(status=DRAFT)`])
  sd-msg(xDb,  xApi, 52, [`line_id`], dashed: true)
  sd-msg(xApi, xDb,  60, [`UPDATE TripSession SET line\_id = ...`])
  sd-msg(xDb,  xApi, 68, [ok], dashed: true)
  sd-msg(xApi, xApp, 76, [`200 OK \{ TripSession \}`], dashed: true)

  // Confirmación + nota
  sd-msg(xApp, xUser, 84,
    [navegar a "Mis contribuciones"], dashed: true)
  sd-note(xUser - 5, xDb + 3, 88,
    [Línea aún en DRAFT — se promueve tras `deduplicate_lines` + `resolve_line_votes`])
})


// ============================================================
// Sequence diagram — Reportar desvío activo (Fig. 17, CU-07)
// ============================================================

#let reportar-desvio-sequence = block(width: 100%, height: 130mm, {
  let H = 130
  let hdr-h = 8
  // Lifelines: Usuario | App | Server | Valhalla | DB | BackgroundTasks
  let xUser = 14
  let xApp  = 46
  let xApi  = 80
  let xVal  = 110
  let xDb   = 138
  let xBg   = 168

  sd-participant(xUser, [Usuario], 24, hdr-h, actor: true)
  sd-participant(xApp,  [App móvil], 28, hdr-h)
  sd-participant(xApi,  [Server], 25, hdr-h)
  sd-participant(xVal,  [Valhalla], 23, hdr-h)
  sd-participant(xDb,   [Base de datos], 26, hdr-h)
  sd-participant(xBg,   [BackgroundTasks], 28, hdr-h)

  sd-lifeline(xUser, hdr-h, H)
  sd-lifeline(xApp,  hdr-h, H)
  sd-lifeline(xApi,  hdr-h, H)
  sd-lifeline(xVal,  hdr-h, H)
  sd-lifeline(xDb,   hdr-h, H)
  sd-lifeline(xBg,   hdr-h, H)

  sd-msg(xUser, xApp, 17, [marca como desvío + motivo + descripción])
  sd-msg(xApp,  xApi, 26,
    [`POST /recordings/\{id\}/end \{ is\_detour, detour\_reason, ... \}`])

  // Snap to road via Valhalla
  sd-msg(xApi,  xDb,  35, [cargar `TripSession` + puntos])
  sd-msg(xDb,   xApi, 43, [puntos], dashed: true)
  sd-msg(xApi,  xVal, 51, [`trace_attributes` (snap polyline al callejero)])
  sd-msg(xVal,  xApi, 59, [geometría snapped], dashed: true)

  // Persist Detour
  sd-msg(xApi,  xDb,  68,
    [`INSERT Detour(line\_id, path, reason, status=ACTIVE)`])
  sd-msg(xDb,   xApi, 76, [`detour_id`], dashed: true)

  // Background notify
  sd-msg(xApi,  xBg,  85,
    [encolar `dispatch_detour_notifications` (excluye reportante)])
  sd-msg(xApi,  xApp, 93, [`200 OK \{ TripSession \}`], dashed: true)

  // Async branch
  sd-note(xVal - 5, xBg + 3, 102,
    [Asíncrono — no bloquea la respuesta])
  sd-msg(xBg,   xDb, 113,
    [`INSERT NotificationDispatch` por suscriptor con commute en la línea])
  sd-msg(xBg,   xApp, 121,
    [push (vía Expo) a dispositivos suscritos], dashed: true)
})


// ============================================================
// Sequence diagram — Registrar tarifa con zonas (Fig. 19, CU-08)
// ============================================================

#let reportar-tarifa-sequence = block(width: 100%, height: 110mm, {
  let H = 110
  let hdr-h = 8
  // Lifelines: Usuario | App | Server | DB
  let xUser = 18
  let xApp  = 60
  let xApi  = 105
  let xDb   = 150

  sd-participant(xUser, [Usuario], 30, hdr-h, actor: true)
  sd-participant(xApp,  [App móvil], 38, hdr-h)
  sd-participant(xApi,  [Server (FastAPI)], 38, hdr-h)
  sd-participant(xDb,   [Base de datos], 30, hdr-h)

  sd-lifeline(xUser, hdr-h, H)
  sd-lifeline(xApp,  hdr-h, H)
  sd-lifeline(xApi,  hdr-h, H)
  sd-lifeline(xDb,   hdr-h, H)

  // Modal opens after recording
  sd-msg(xUser, xApp, 17, [ingresa monto en el modal post-grabación])

  // Preview zones
  sd-msg(xApp, xApi, 26,
    [`POST /fares/zones/resolve \{ boarding\_lat/lon, alighting\_lat/lon \}`])
  sd-msg(xApi, xDb,  34,
    [`ST_Contains(FareZone.boundary, ST_MakePoint(...))`])
  sd-msg(xDb,  xApi, 42,
    [`(boarding_zone_id, alighting_zone_id)`], dashed: true)
  sd-msg(xApi, xApp, 50,
    [`\{ boarding\_zone: "Cochabamba", alighting\_zone: "Sacaba" \}`], dashed: true)

  // Display + confirm
  sd-msg(xApp, xUser, 58,
    [muestra "Tarifa para Cochabamba → Sacaba" sobre el input], dashed: true)
  sd-msg(xUser, xApp, 67, [confirma monto])

  // Submit
  sd-msg(xApp, xApi, 76,
    [`POST /fares/reports \{ line\_id, amount\_bob, lat/lon, source \}`])
  sd-msg(xApi, xDb,  85,
    [`INSERT FareReport` (zonas re-resueltas server-side)])
  sd-msg(xDb,  xApi, 93, [`fare_report`], dashed: true)
  sd-msg(xApi, xApp, 101,
    [`201 Created \{ boarding_zone, alighting_zone, ... \}`], dashed: true)
})


// ============================================================
// Sequence diagram — Búsqueda de itinerario multi-modal (Fig. 20, CU-01)
// ============================================================

#let directions-sequence = block(width: 100%, height: 130mm, {
  let H = 130
  let hdr-h = 8
  // Lifelines: Usuario | App | Server | TransitGraph | DB
  let xUser = 18
  let xApp  = 56
  let xApi  = 96
  let xGr   = 136
  let xDb   = 174

  sd-participant(xUser, [Usuario], 26, hdr-h, actor: true)
  sd-participant(xApp,  [App móvil], 34, hdr-h)
  sd-participant(xApi,  [Server], 34, hdr-h)
  sd-participant(xGr,   [TransitGraph (memoria)], 34, hdr-h)
  sd-participant(xDb,   [Base de datos], 30, hdr-h)

  sd-lifeline(xUser, hdr-h, H)
  sd-lifeline(xApp,  hdr-h, H)
  sd-lifeline(xApi,  hdr-h, H)
  sd-lifeline(xGr,   hdr-h, H)
  sd-lifeline(xDb,   hdr-h, H)

  // Search
  sd-msg(xUser, xApp, 17, [ingresa origen + destino])
  sd-msg(xApp,  xApi, 26,
    [`POST /directions/ \{ origin, destination, include\_pending\_* \}`])

  // Find stops near endpoints
  sd-msg(xApi,  xGr,  35, [paradas cercanas al origen y destino])
  sd-msg(xGr,   xApi, 43, [`(origin_node, dest_node)`], dashed: true)

  // Shortest path
  sd-msg(xApi,  xGr,  52, [`shortest_path(origin_node, dest_node, costing)`])
  sd-msg(xGr,   xApi, 60,
    [secuencia de aristas (bus + walk + transfer)], dashed: true)

  // Enrich each bus leg
  sd-self-msg(xApi, 69, [partir aristas en `legs` por `(line_id, mode)`])
  sd-msg(xApi,  xDb,  78,
    [por cada bus leg: `fare_estimate` + `frequency_min` + `Detour[ACTIVE]`])
  sd-msg(xDb,   xApi, 86, [datos enriquecidos], dashed: true)

  // Build response
  sd-self-msg(xApi, 94,
    [montar `DirectionsResponse \{ legs[], totals \}`])
  sd-msg(xApi,  xApp, 103, [`200 OK \{ legs[], total_fare_bob, total_duration_s \}`], dashed: true)

  // Render
  sd-msg(xApp,  xUser, 112,
    [render mapa + lista de pasos con tarifa, frecuencia, alertas de desvío],
    dashed: true)

  sd-note(xUser - 5, xDb + 3, 121,
    [Aristas con `is_confirmed=false` solo se incluyen si el usuario habilitó "rutas pendientes"])
})


// ============================================================
// ER diagram — diseño lógico de la base de datos
// ============================================================
//
// Modelo entidad-relación para el capítulo de diseño. Excluye
// tablas de infraestructura (alembic_version, spatial_ref_sys).
//
// Convenciones:
//   PK — subrayada en negrita
//   FK — en cursiva
//   Línea continua  — relación de propiedad (FK obligatoria)
//   Línea discontinua — FK opcional o vínculo de auditoría (device_id)
//   Cardinalidad anotada cerca de cada extremo (1 / N / 0..1 / 0..N)

#let er-pk(name) = strong(underline[#name])
#let er-fk(name) = emph[#name]

// Caja de entidad: barra de título coloreada por dominio + lista de atributos.
// (x, y) define la esquina superior izquierda en milímetros.
#let er-entity(x, y, w, title, attrs, fill: rgb("#e0e7ec")) = {
  let title-h = 4.5
  let row-h = 3.4
  let body-h = attrs.len() * row-h + 1.2

  // Barra de título
  place(top + left, dx: x * 1mm, dy: y * 1mm, box(
    width: w * 1mm, height: title-h * 1mm,
    stroke: 0.6pt + node-stroke,
    fill: fill,
    inset: (left: 3pt, right: 3pt, y: 0.5pt),
  )[
    #set align(left + horizon)
    #text(size: 6.5pt, weight: "bold", fill: node-stroke)[#title]
  ])

  // Cuerpo (lista de atributos)
  place(top + left, dx: x * 1mm, dy: (y + title-h) * 1mm, box(
    width: w * 1mm, height: body-h * 1mm,
    stroke: 0.6pt + node-stroke,
    fill: node-fill,
    inset: (x: 3pt, top: 1pt, bottom: 1pt),
  )[
    #set text(size: 5.5pt, fill: node-stroke)
    #set par(leading: 0.45em)
    #stack(spacing: 0.7mm, ..attrs.map(a => [#a]))
  ])
}

// Vínculo ER: línea recta sin punta, con cardinalidades en ambos extremos.
#let er-rel(x1, y1, x2, y2, card1: [1], card2: [N], dashed: false) = {
  let stroke-style = if dashed {
    (paint: ext-color, thickness: 0.5pt, dash: "dashed")
  } else {
    (paint: edge-color, thickness: 0.7pt)
  }
  place(top + left, dx: x1 * 1mm, dy: y1 * 1mm, line(
    start: (0pt, 0pt),
    end: ((x2 - x1) * 1mm, (y2 - y1) * 1mm),
    stroke: stroke-style,
  ))
  // Vector unitario para colocar las etiquetas pegadas al extremo correcto.
  let dx = x2 - x1
  let dy = y2 - y1
  let len = calc.sqrt(dx * dx + dy * dy)
  let ux = dx / len
  let uy = dy / len
  let off = 3.2
  // Desplazamiento perpendicular para que la etiqueta no se monte sobre la línea.
  let perp-x = -uy * 1.2
  let perp-y =  ux * 1.2
  // Etiqueta cerca de (x1, y1)
  place(top + left,
    dx: (x1 + ux * off + perp-x - 3) * 1mm,
    dy: (y1 + uy * off + perp-y - 1.8) * 1mm,
    box(width: 6mm)[
      #set align(center)
      #set text(size: 5.5pt, fill: node-stroke, weight: "bold")
      #card1
    ])
  // Etiqueta cerca de (x2, y2)
  place(top + left,
    dx: (x2 - ux * off + perp-x - 3) * 1mm,
    dy: (y2 - uy * off + perp-y - 1.8) * 1mm,
    box(width: 6mm)[
      #set align(center)
      #set text(size: 5.5pt, fill: node-stroke, weight: "bold")
      #card2
    ])
}


#let er-diagram = block(width: 100%, height: 190mm, {

  // Paleta de barras de título por dominio (tonos suaves).
  let c-capture = rgb("#dfe9ee")  // captura cruda (puntos, sensores)
  let c-process = rgb("#cfddc8")  // sesiones y trayectorias procesadas
  let c-id      = rgb("#fde9c4")  // dispositivos
  let c-event   = rgb("#f1dfdf")  // desvíos, notificaciones, tarifas
  let c-line    = rgb("#dbe7d4")  // líneas y rutas
  let c-vote    = rgb("#e8dde9")  // votos y suscripciones
  let c-ops     = rgb("#e2e2e2")  // pipeline (operaciones)

  // -------------------------------------------------------------------
  // Columna 1 — Captura cruda
  // -------------------------------------------------------------------
  er-entity(2, 4, 50, [trip_session_points], (
    er-pk[id], er-fk[session_id], [latitude, longitude], [timestamp],
  ), fill: c-capture)

  er-entity(2, 32, 50, [trip_sensor_readings], (
    er-pk[id], er-fk[session_id], [accel_x/y/z, gyro_x/y/z], [timestamp],
  ), fill: c-capture)

  er-entity(2, 60, 50, [trip_points], (
    er-pk[id], er-fk[trip_id], [latitude, longitude], [point_index],
  ), fill: c-capture)

  er-entity(2, 88, 50, [trip_matched_edges], (
    er-pk[id], er-fk[trip_id], [valhalla_edge_id], [sequence, forward],
  ), fill: c-capture)

  er-entity(2, 116, 50, [travel_time_samples], (
    er-pk[id], er-fk[trip_id], er-fk[edge_id], [duration_seconds],
  ), fill: c-capture)

  // -------------------------------------------------------------------
  // Columna 2 — Sesiones y trayectorias
  // -------------------------------------------------------------------
  er-entity(60, 4, 52, [trip_sessions], (
    er-pk[id], er-fk[device_id], er-fk[line_id],
    [status], [processing_status],
  ), fill: c-process)

  er-entity(60, 80, 52, [trips], (
    er-pk[id], er-fk[session_id], er-fk[line_id],
    [status], [frechet_distance],
  ), fill: c-process)

  // -------------------------------------------------------------------
  // Columna 3 — Identidad y eventos
  // -------------------------------------------------------------------
  er-entity(120, 4, 50, [devices], (
    er-pk[id], [platform], [locale], [expo_push_token],
  ), fill: c-id)

  er-entity(120, 32, 50, [detours], (
    er-pk[id], er-fk[line_id], er-fk[session_id], [reason], [status],
  ), fill: c-event)

  er-entity(120, 64, 50, [notification_dispatches], (
    er-pk[id], er-fk[line_id], er-fk[detour_id], er-fk[device_id],
  ), fill: c-event)

  er-entity(120, 92, 50, [fare_zones], (
    er-pk[id], [name], [boundary],
  ), fill: c-event)

  er-entity(120, 116, 50, [fare_reports], (
    er-pk[id], er-fk[line_id],
    er-fk[boarding_zone_id], er-fk[alighting_zone_id], [amount_bob],
  ), fill: c-event)

  // -------------------------------------------------------------------
  // Columna 4 — Líneas y rutas
  // -------------------------------------------------------------------
  er-entity(178, 4, 52, [lines], (
    er-pk[id], [name], [line_type], [status], er-fk[merged_into_id],
  ), fill: c-line)

  er-entity(178, 36, 52, [routes], (
    er-pk[id], er-fk[line_id], [ramal_label], [version], [source], [status],
  ), fill: c-line)

  er-entity(178, 72, 52, [route_edges], (
    er-pk[id], er-fk[route_id], [sequence], [forward], [status], [confidence],
  ), fill: c-line)

  er-entity(178, 108, 52, [ramal_descriptors], (
    er-pk[id], er-fk[route_id], [text], [votes_count],
  ), fill: c-line)

  // -------------------------------------------------------------------
  // Columna 5 — Comunidad y operaciones
  // -------------------------------------------------------------------
  er-entity(238, 4, 46, [line_votes], (
    er-pk[id], er-fk[line_id], er-fk[device_id], [vote],
  ), fill: c-vote)

  er-entity(238, 32, 46, [edge_votes], (
    er-pk[id], er-fk[edge_id], er-fk[device_id], [vote],
  ), fill: c-vote)

  er-entity(238, 60, 46, [ramal_descriptor_votes], (
    er-pk[id], er-fk[descriptor_id], er-fk[device_id],
  ), fill: c-vote)

  er-entity(238, 84, 46, [line_subscriptions], (
    er-pk[id], er-fk[line_id], er-fk[device_id], [kind],
  ), fill: c-vote)

  er-entity(238, 112, 46, [line_schedules], (
    er-fk[line_id], [day_bucket], [headway_min],
    [service_start_at], [service_end_at],
  ), fill: c-vote)

  er-entity(238, 140, 46, [pipeline_runs], (
    er-pk[id], [trigger], [status],
  ), fill: c-ops)

  er-entity(238, 162, 46, [pipeline_step_results], (
    er-pk[id], er-fk[run_id], [step_name], [status], [stats],
  ), fill: c-ops)

  // -------------------------------------------------------------------
  // Vínculos
  // -------------------------------------------------------------------

  // ---- Captura cruda → sesiones / trips (col 1 → col 2) ----
  er-rel(52, 14, 60, 16, card1: [N], card2: [1])    // session_points → sessions
  er-rel(52, 42, 60, 16, card1: [N], card2: [1])    // sensor_readings → sessions
  er-rel(52, 70, 60, 92, card1: [N], card2: [1])    // trip_points → trips
  er-rel(52, 98, 60, 92, card1: [N], card2: [1])    // matched_edges → trips
  er-rel(52, 126, 60, 92, card1: [N], card2: [1])   // tt_samples → trips

  // ---- Sesiones → trips (vertical en col 2) ----
  er-rel(86, 28, 86, 80, card1: [1], card2: [N])

  // ---- Sesiones / trips → devices y lines ----
  er-rel(112, 16, 120, 14, card1: [N], card2: [0..1], dashed: true)  // sessions → devices
  er-rel(112, 12, 178, 12, card1: [N], card2: [0..1], dashed: true)  // sessions → lines (opc.)
  er-rel(112, 92, 178, 22, card1: [N], card2: [1])                   // trips → lines

  // ---- travel_time_samples → route_edges (vínculo entre dominios) ----
  er-rel(52, 130, 178, 86, card1: [N], card2: [1], dashed: true)

  // ---- Desvíos ----
  er-rel(120, 44, 112, 22, card1: [N], card2: [1])   // detours → trip_sessions
  er-rel(170, 44, 178, 20, card1: [N], card2: [1])   // detours → lines

  // ---- Notificaciones ----
  er-rel(145, 64, 145, 56, card1: [N], card2: [0..1])  // notifications → detours
  er-rel(170, 74, 178, 24, card1: [N], card2: [1])     // notifications → lines
  er-rel(125, 64, 125, 24, card1: [N], card2: [1], dashed: true)  // notifications → devices

  // ---- Tarifas (zonas) ----
  er-rel(135, 116, 135, 108, card1: [N], card2: [0..1])  // fare_reports → fare_zones (boarding)
  er-rel(155, 116, 155, 108, card1: [N], card2: [0..1])  // fare_reports → fare_zones (alighting)
  er-rel(170, 128, 178, 26, card1: [N], card2: [1])      // fare_reports → lines
  er-rel(120, 128, 112, 20, card1: [N], card2: [0..1], dashed: true)  // fare_reports → sessions

  // ---- Jerarquía de líneas y rutas (col 4 vertical) ----
  er-rel(204, 36, 204, 28, card1: [N], card2: [1])   // routes → lines
  er-rel(204, 72, 204, 64, card1: [N], card2: [1])   // route_edges → routes
  er-rel(228, 108, 228, 64, card1: [N], card2: [1])  // ramal_descriptors → routes (margen der.)

  // ---- Comunidad / suscripciones → entidades padre ----
  er-rel(238, 14, 230, 16, card1: [N], card2: [1])    // line_votes → lines
  er-rel(238, 42, 230, 86, card1: [N], card2: [1])    // edge_votes → route_edges
  er-rel(238, 68, 230, 118, card1: [N], card2: [1])   // ramal_descriptor_votes → ramal_descriptors
  er-rel(238, 94, 230, 24, card1: [N], card2: [1])    // line_subscriptions → lines
  er-rel(238, 124, 230, 26, card1: [N], card2: [1])   // line_schedules → lines

  // ---- Pipeline ----
  er-rel(260, 162, 260, 156, card1: [N], card2: [1])  // step_results → runs
})
