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
