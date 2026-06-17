#import "@preview/cetz:0.4.2": canvas, draw

#set page(width: auto, height: auto, margin: 1cm, fill: white)
#set text(font: "New Computer Modern", size: 10pt)

#let accent = rgb("#1f6feb")   // línea 1 / bus
#let muted = rgb("#6e7781")    // grises, caminata
#let ink = rgb("#1f2328")      // línea 2 / texto

#let l1 = 1.1pt + accent
#let l2 = 1.1pt + ink
#let thin = 0.7pt + muted
#let dashWalk = (paint: muted, thickness: 0.8pt, dash: "dashed")
#let dashBridge = (paint: accent, thickness: 1pt, dash: "dashed")
#let mA = (end: ">", fill: accent)
#let mB = (end: ">", fill: ink)
#let mW = (start: ">", end: ">", fill: muted)

#figure(
  canvas(length: 1cm, {
    import draw: *

    // ---- helpers ----
    let node(p) = circle(p, radius: 0.12, fill: white, stroke: 0.7pt + ink)
    let dot(p, c) = circle(p, radius: 0.06, fill: c, stroke: none)
    let cap(t) = content((0, -1.18), text(size: 7pt, fill: muted)[#t], anchor: "center")
    let title(cx, cy, t) = content((cx - 2.0, cy + 1.62), text(size: 8.5pt, weight: "bold", fill: ink)[#t], anchor: "west")
    let frame(cx, cy) = rect((cx - 2.0, cy - 1.55), (cx + 2.0, cy + 1.35), stroke: 0.4pt + muted, radius: 0.08)

    let L1 = ((-1.5, 0.1), (-0.75, 0.6), (0.0, 0.15), (0.75, 0.55), (1.5, 0.05))
    let L2 = ((-1.5, -0.7), (-0.7, -0.95), (0.1, -0.55), (0.9, -0.9), (1.6, -0.5))

    let cx0 = 0.0
    let cx1 = 4.6
    let cx2 = 9.2
    let cx3 = 13.8
    let ry0 = 0.0
    let ry1 = -3.9

    // ===================== (a) Tramos =====================
    title(cx0, ry0, "(a) Tramos de cada ruta")
    frame(cx0, ry0)
    group({
      translate((cx0, ry0))
      line(..L1, stroke: l1)
      line(..L2, stroke: l2)
      for p in L1 { dot(p, accent) }
      for p in L2 { dot(p, ink) }
      cap("cada línea es una secuencia de tramos")
    })

    // ===================== (b) Nodos =====================
    title(cx1, ry0, "(b) Extremos → nodos")
    frame(cx1, ry0)
    group({
      translate((cx1, ry0))
      line(..L1, stroke: thin)
      line(..L2, stroke: thin)
      for p in L1 { node(p) }
      for p in L2 { node(p) }
      cap("el inicio y fin de cada tramo es un nodo")
    })

    // ===================== (c) Fusión =====================
    title(cx2, ry0, "(c) Fusión de nodos")
    frame(cx2, ry0)
    group({
      translate((cx2, ry0))
      line((-1.7, 0.5), (-0.5, 0.12), stroke: thin)
      line((-1.7, -0.45), (-0.34, -0.02), stroke: thin)
      circle((-0.42, 0.05), radius: 0.42, stroke: dashWalk)
      node((-0.5, 0.12))
      node((-0.34, -0.02))
      content((-0.42, 0.72), text(size: 7.5pt, fill: accent)[≤ 20 m], anchor: "center")
      line((0.15, 0.05), (0.75, 0.05), stroke: thin, mark: (end: ">", fill: muted))
      line((1.5, 0.45), (1.28, 0.18), stroke: thin)
      line((1.55, -0.4), (1.3, -0.07), stroke: thin)
      circle((1.2, 0.05), radius: 0.15, fill: accent, stroke: none)
      cap("nodos a ≤ 20 m → una sola parada")
    })

    // ===================== (d) Aristas de bus =====================
    title(cx3, ry0, "(d) Aristas de bus")
    frame(cx3, ry0)
    group({
      translate((cx3, ry0))
      let n1 = (-1.5, -0.2)
      let n2 = (-0.5, 0.45)
      let n3 = (0.5, -0.2)
      let n4 = (1.5, 0.35)
      line(n1, n2, stroke: l1, mark: mA)
      line(n2, n3, stroke: l1, mark: mA)
      line(n3, n4, stroke: dashBridge, mark: mA)
      node(n1)
      node(n2)
      node(n3)
      node(n4)
      content((0.05, 0.42), text(size: 7pt, fill: accent)[peso = d / v], anchor: "center")
      content((1.0, -0.05), text(size: 7pt, fill: accent)[puente], anchor: "center")
      cap("aristas dirigidas con tiempo de viaje")
    })

    // ===================== (e) Tramo compartido =====================
    title(cx0, ry1, "(e) Tramo compartido")
    frame(cx0, ry1)
    group({
      translate((cx0, ry1))
      let a = (-1.3, -0.05)
      let b = (0.0, -0.05)
      let c = (1.3, -0.05)
      bezier(a, b, (-0.65, 0.45), stroke: l1, mark: mA)
      bezier(b, c, (0.65, 0.45), stroke: l1, mark: mA)
      bezier(a, b, (-0.65, -0.55), stroke: l2, mark: mB)
      bezier(b, c, (0.65, -0.55), stroke: l2, mark: mB)
      node(a)
      node(b)
      node(c)
      content((0.0, 0.78), text(size: 7pt, fill: ink)[{L1, L2}], anchor: "center")
      cap("mismos nodos, una arista por línea (sin transbordo)")
    })

    // ===================== (f) Transbordo a pie =====================
    title(cx1, ry1, "(f) Transbordo a pie")
    frame(cx1, ry1)
    group({
      translate((cx1, ry1))
      line((-1.7, 0.6), (-1.0, 0.4), stroke: l1)
      line((1.0, -0.55), (1.7, -0.75), stroke: l2)
      line((-0.85, 0.33), (0.85, -0.48), stroke: dashWalk, mark: mW)
      circle((-1.0, 0.4), radius: 0.12, fill: white, stroke: 0.9pt + accent)
      circle((1.0, -0.55), radius: 0.12, fill: white, stroke: 0.9pt + ink)
      content((0.35, 0.18), text(size: 7.5pt, fill: muted)[≤ 400 m], anchor: "center")
      // figura caminante
      circle((-0.05, 0.12), radius: 0.05, fill: ink, stroke: none)
      line((-0.05, 0.07), (-0.05, -0.08), stroke: 0.7pt + ink)
      line((-0.05, -0.08), (-0.13, -0.2), stroke: 0.7pt + ink)
      line((-0.05, -0.08), (0.03, -0.2), stroke: 0.7pt + ink)
      line((-0.13, 0.0), (0.03, 0.0), stroke: 0.7pt + ink)
      cap("líneas distintas a ≤ 400 m → arista de caminata")
    })

    // ===================== (g) Grafo resultante =====================
    title(cx2, ry1, "(g) Grafo resultante")
    frame(cx2, ry1)
    group({
      translate((cx2, ry1))
      let A = ((-1.5, 0.45), (-0.75, 0.62), (0.0, 0.42), (0.75, 0.58), (1.5, 0.38))
      let B = ((-1.45, -0.6), (-0.7, -0.78), (0.05, -0.56), (0.8, -0.74), (1.5, -0.52))
      for i in range(A.len() - 1) { line(A.at(i), A.at(i + 1), stroke: l1, mark: mA) }
      for i in range(B.len() - 1) { line(B.at(i), B.at(i + 1), stroke: l2, mark: mB) }
      line((0.0, 0.42), (0.05, -0.56), stroke: dashWalk, mark: mW)
      for p in A { node(p) }
      for p in B { node(p) }
      cap("paradas + aristas de bus y de caminata")
    })

    // ===================== Leyenda =====================
    frame(cx3, ry1)
    content((cx3 - 1.85, ry1 + 1.05), text(size: 8pt, weight: "bold", fill: ink)[Leyenda], anchor: "west")
    group({
      translate((cx3, ry1))
      let ix = -1.7
      let tx = -1.25
      let row(y, body) = body
      // bus línea 1
      line((ix, 0.55), (ix + 0.5, 0.55), stroke: l1, mark: mA)
      content((tx, 0.55), text(size: 7.5pt)[bus (línea 1)], anchor: "west")
      // bus línea 2
      line((ix, 0.2), (ix + 0.5, 0.2), stroke: l2, mark: mB)
      content((tx, 0.2), text(size: 7.5pt)[bus (línea 2)], anchor: "west")
      // puente
      line((ix, -0.15), (ix + 0.5, -0.15), stroke: dashBridge)
      content((tx, -0.15), text(size: 7.5pt)[puente], anchor: "west")
      // caminata
      line((ix, -0.5), (ix + 0.5, -0.5), stroke: dashWalk)
      content((tx, -0.5), text(size: 7.5pt)[caminata], anchor: "west")
      // nodo
      circle((ix + 0.25, -0.85), radius: 0.1, fill: white, stroke: 0.7pt + ink)
      content((tx, -0.85), text(size: 7.5pt)[nodo / parada], anchor: "west")
      // nodo fusionado
      circle((ix + 0.25, -1.2), radius: 0.12, fill: accent, stroke: none)
      content((tx, -1.2), text(size: 7.5pt)[nodo fusionado], anchor: "west")
    })
  }),
  caption: [Construcción del grafo de transporte: de los tramos de cada ruta (a) se extraen nodos (b), se fusionan los cercanos (c) y se crean aristas de bus con peso (d). Cuando dos líneas comparten un corredor (e) reutilizan los mismos nodos pero conservan una arista paralela por línea. Finalmente se agregan transbordos a pie entre líneas distintas (f) para obtener el grafo final (g).],
)
