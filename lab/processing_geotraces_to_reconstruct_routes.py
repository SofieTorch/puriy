import marimo

__generated_with = "0.23.9"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _():
    import os

    import psycopg
    from dotenv import load_dotenv

    load_dotenv()
    conn = psycopg.connect(os.environ["DATABASE_URL"].replace("+psycopg", ""))
    return (conn,)


@app.cell
def _(conn, mo):
    with conn.cursor() as cur:
        cur.execute("SELECT id, name, description FROM lines ORDER BY name")
        _lines = cur.fetchall()

    _options = {
        f"{name} — {desc}".strip(" —") if desc else name: str(id)
        for id, name, desc in _lines
    }
    line_selector = mo.ui.dropdown(options=_options, label="Line")
    line_selector
    return (line_selector,)


@app.cell
def _():
    import base64
    import json

    import numpy as np

    return base64, json, np


@app.cell
def _(np):
    def resample_polyline(points, n):
        """Resample a polyline to *n* evenly-spaced points via linear interpolation."""
        pts = np.array(points)
        if len(pts) <= 1:
            return np.tile(pts[0] if len(pts) else [0, 0], (n, 1))
        dists = np.cumsum(np.r_[0, np.linalg.norm(np.diff(pts, axis=0), axis=1)])
        if dists[-1] == 0:
            return np.tile(pts[0], (n, 1))
        dists /= dists[-1]
        t = np.linspace(0, 1, n)
        return np.column_stack([np.interp(t, dists, pts[:, c]) for c in range(2)])

    return (resample_polyline,)


@app.cell
def _():
    def query_trace_points(conn, line_id):
        """Query raw GPS and HMM-cleaned points, grouped by session."""
        from collections import defaultdict

        conn.rollback()

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT tsp.session_id::text, tsp.latitude, tsp.longitude
                FROM trip_session_points tsp
                JOIN trip_sessions ts ON ts.id = tsp.session_id
                WHERE ts.line_id = %s::uuid
                ORDER BY tsp.session_id, tsp.timestamp
                """,
                (line_id,),
            )
            raw_rows = cur.fetchall()

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT t.session_id::text, tp.latitude, tp.longitude
                FROM trip_points tp
                JOIN trips t ON t.id = tp.trip_id
                WHERE t.line_id = %s::uuid
                ORDER BY t.session_id, tp.point_index
                """,
                (line_id,),
            )
            clean_rows = cur.fetchall()

        raw_by = defaultdict(list)
        for sid, lat, lon in raw_rows:
            raw_by[sid].append((lat, lon))

        clean_by = defaultdict(list)
        for sid, lat, lon in clean_rows:
            clean_by[sid].append((lat, lon))

        return dict(raw_by), dict(clean_by)

    return (query_trace_points,)


@app.cell
def _(np, resample_polyline):
    PALETTE = [
        [31, 119, 180],
        [255, 127, 14],
        [44, 160, 44],
        [214, 39, 40],
        [148, 103, 189],
        [140, 86, 75],
        [227, 119, 194],
        [127, 127, 127],
        [188, 189, 34],
        [23, 190, 207],
    ]

    def pair_traces(raw_by, clean_by):
        """Pair raw/cleaned traces by session and resample to equal lengths."""
        paired = sorted(set(raw_by) & set(clean_by))
        raw_only = sorted(set(raw_by) - set(clean_by))

        raw_arrs, clean_arrs, sids, colors = [], [], [], []
        raw_paths = []  # per-session raw paths for trace lines
        clean_paths = []  # per-session cleaned paths for the final line

        def _to_lonlat(pts):
            return [[float(p[1]), float(p[0])] for p in pts]

        for i, sid in enumerate(paired):
            n = min(max(len(raw_by[sid]), len(clean_by[sid]), 30), 200)
            col = PALETTE[i % len(PALETTE)]
            raw_resampled = resample_polyline(raw_by[sid], n)
            clean_resampled = resample_polyline(clean_by[sid], n)
            raw_arrs.append(raw_resampled)
            clean_arrs.append(clean_resampled)
            sids.extend([sid[:8]] * n)
            colors.extend([col] * n)
            raw_paths.append({"path": _to_lonlat(raw_resampled), "color": col})
            clean_paths.append({"path": _to_lonlat(clean_resampled), "color": col})

        for i, sid in enumerate(raw_only):
            pts = np.array(raw_by[sid])
            col = PALETTE[(len(paired) + i) % len(PALETTE)]
            raw_arrs.append(pts)
            clean_arrs.append(pts)
            sids.extend([sid[:8]] * len(pts))
            colors.extend([col] * len(pts))
            raw_paths.append({"path": _to_lonlat(pts), "color": col})
            clean_paths.append({"path": _to_lonlat(pts), "color": col})

        return {
            "raw": np.vstack(raw_arrs) if raw_arrs else np.empty((0, 2)),
            "clean": np.vstack(clean_arrs) if clean_arrs else np.empty((0, 2)),
            "sessions": sids,
            "colors": colors,
            "raw_paths": raw_paths,
            "clean_paths": clean_paths,
            "n_paired": len(paired),
            "n_raw_only": len(raw_only),
        }

    return (pair_traces,)


@app.cell
def _(json, np):
    def build_trace_map(trace_points):
        """Build an HTML map with deck.gl, client-side slider and play button."""
        raw = trace_points["raw"].tolist()
        clean = trace_points["clean"].tolist()
        colors = trace_points["colors"]
        raw_paths = trace_points["raw_paths"]
        clean_paths = trace_points["clean_paths"]

        center_lat = float(np.mean(trace_points["raw"][:, 0]))
        center_lon = float(np.mean(trace_points["raw"][:, 1]))

        return f"""\
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<script src="https://unpkg.com/deck.gl@9.1.14/dist.min.js"></script>
<script src="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.js"></script>
<link href="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.css" rel="stylesheet"/>
<style>
  body {{ margin:0; font-family:system-ui,sans-serif; }}
  #map {{ width:100%; height:560px; }}
  .controls {{ display:flex; align-items:center; gap:8px; padding:8px 12px; justify-content:center; }}
  .controls input[type=range] {{ width:240px; }}
  #play-btn {{
    border:none; background:#eee; border-radius:4px;
    padding:4px 10px; cursor:pointer; font-size:14px;
  }}
  #play-btn:hover {{ background:#ddd; }}
</style>
</head>
<body>
<div id="map"></div>
<div class="controls">
  <b>Raw GPS</b>
  <button id="play-btn">▶</button>
  <input type="range" id="slider" min="0" max="100" value="0">
  <b>HMM-cleaned</b>
</div>
<script>
const raw={json.dumps(raw)};
const clean={json.dumps(clean)};
const colors={json.dumps(colors)};
const rawPaths={json.dumps(raw_paths)};
const cleanPaths={json.dumps(clean_paths)};

function makeLayers(t) {{
  const points=raw.map((r,i)=>({{
    position:[r[1]*(1-t)+clean[i][1]*t, r[0]*(1-t)+clean[i][0]*t],
    color:[...colors[i],200],
  }}));
  const scatter=new deck.ScatterplotLayer({{
    id:'scatter', data:points,
    getPosition:d=>d.position, getFillColor:d=>d.color,
    getRadius:3, radiusMinPixels:1, radiusMaxPixels:4,
  }});
  const traceData=rawPaths.map((rp,i)=>({{
    path:rp.path.map((p,j)=>[
      p[0]*(1-t)+cleanPaths[i].path[j][0]*t,
      p[1]*(1-t)+cleanPaths[i].path[j][1]*t,
    ]),
    color:rp.color,
  }}));
  const traces=new deck.PathLayer({{
    id:'traces', data:traceData,
    getPath:d=>d.path,
    getColor:d=>[...d.color,60],
    getWidth:1, widthMinPixels:1,
    updateTriggers:{{getPath:t}},
  }});
  const cleanAlpha=Math.round(Math.pow(t,5)*220);
  const cleanLines=new deck.PathLayer({{
    id:'clean', data:cleanPaths,
    getPath:d=>d.path,
    getColor:d=>[...d.color,cleanAlpha],
    getWidth:2, widthMinPixels:1,
    updateTriggers:{{getColor:cleanAlpha}},
  }});
  return [traces, cleanLines, scatter];
}}

const gl=new deck.DeckGL({{
  container:'map',
  mapStyle:'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json',
  initialViewState:{{latitude:{center_lat},longitude:{center_lon},zoom:13}},
  controller:true,
  layers:makeLayers(0),
}});

const slider=document.getElementById('slider');
slider.addEventListener('input',()=>{{
  gl.setProps({{layers:makeLayers(slider.value/100)}});
}});

let animId;
const btn=document.getElementById('play-btn');
btn.addEventListener('click',()=>{{
  slider.value=0;
  gl.setProps({{layers:makeLayers(0)}});
  animate();
}});
function animate(){{
  let v=parseInt(slider.value)+1;
  if(v>100) return;
  slider.value=v;
  gl.setProps({{layers:makeLayers(v/100)}});
  animId=requestAnimationFrame(()=>setTimeout(animate,12));
}}
</script>
</body>
</html>"""

    return (build_trace_map,)


@app.cell
def _(conn, line_selector, mo, pair_traces, query_trace_points):
    mo.stop(not line_selector.value, mo.md("*Select a line above.*"))

    _raw_by, _clean_by = query_trace_points(conn, line_selector.value)
    trace_points = pair_traces(_raw_by, _clean_by)

    mo.md(
        f"**{trace_points['n_paired']}** paired traces, "
        f"**{trace_points['n_raw_only']}** raw-only — "
        f"**{len(trace_points['sessions'])}** points total"
    )
    return (trace_points,)


@app.cell
def _(base64, build_trace_map, mo, trace_points):
    mo.stop(len(trace_points["sessions"]) == 0, mo.md("*No traces found.*"))

    _html = build_trace_map(trace_points)
    _b64 = base64.b64encode(_html.encode()).decode()
    mo.Html(
        f'<iframe src="data:text/html;base64,{_b64}"'
        ' style="width:100%;height:620px;border:none;"></iframe>'
    )
    return


@app.cell
def _():
    def compute_edge_density(clean_paths):
        """Count how many traces share each edge using midpoint grid binning."""
        from collections import defaultdict

        bin_traces = defaultdict(set)
        edge_list = []

        for trace_idx, trace in enumerate(clean_paths):
            path = trace["path"]
            for j in range(len(path) - 1):
                mid = (
                    round((path[j][0] + path[j + 1][0]) / 2, 4),
                    round((path[j][1] + path[j + 1][1]) / 2, 4),
                )
                bin_traces[mid].add(trace_idx)
                edge_list.append({"path": [path[j], path[j + 1]], "mid": mid})

        max_count = max((len(s) for s in bin_traces.values()), default=1)

        edges = []
        for e in edge_list:
            count = len(bin_traces[e["mid"]])
            f = count / max_count
            edges.append({
                "path": e["path"],
                "count": count,
                "color": [int(255 * (1 - f * 0.7)), int(100 * (1 - f)), int(30 + 100 * f)],
                "width": 1 + 3 * f,
            })

        return edges, max_count

    return (compute_edge_density,)


@app.cell
def _(compute_edge_density, mo, trace_points):
    mo.stop(
        not trace_points or trace_points["n_paired"] == 0,
        mo.md("*No paired traces for density analysis.*"),
    )

    _clean_only = trace_points["clean_paths"][: trace_points["n_paired"]]
    edge_data, max_edge_count = compute_edge_density(_clean_only)

    min_count_input = mo.ui.number(
        value=2, start=1, stop=max_edge_count, step=1,
        label="Min. occurrences to keep",
    )
    mo.hstack([
        mo.md(f"**{len(edge_data)}** edges, max frequency: **{max_edge_count}**"),
        min_count_input,
    ], justify="space-between", align="center")
    return edge_data, max_edge_count, min_count_input


@app.cell
def _(json, np):
    def build_density_map(edges, max_count, min_count):
        """Build HTML map showing edge density with cleanup animation."""
        all_lons, all_lats = [], []
        for e in edges:
            for p in e["path"]:
                all_lons.append(p[0])
                all_lats.append(p[1])
        center_lon = float(np.mean(all_lons))
        center_lat = float(np.mean(all_lats))

        return f"""\
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<script src="https://unpkg.com/deck.gl@9.1.14/dist.min.js"></script>
<script src="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.js"></script>
<link href="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.css" rel="stylesheet"/>
<style>
  body {{ margin:0; font-family:system-ui,sans-serif; }}
  #map {{ width:100%; height:560px; position:relative; }}
  .legend {{
    position:absolute; bottom:20px; right:20px; z-index:1;
    background:rgba(255,255,255,0.92); padding:10px 14px;
    border-radius:6px; font-size:12px; box-shadow:0 1px 4px rgba(0,0,0,.15);
  }}
  .legend-bar {{
    width:120px; height:10px; border-radius:3px;
    background:linear-gradient(to right, rgb(255,230,200), rgb(130,0,30));
  }}
  .legend-labels {{ display:flex; justify-content:space-between; margin-top:2px; }}
  .controls {{ display:flex; align-items:center; gap:8px; padding:8px 12px; justify-content:center; }}
  .controls input[type=range] {{ width:240px; }}
  #play-btn {{
    border:none; background:#eee; border-radius:4px;
    padding:4px 10px; cursor:pointer; font-size:14px;
  }}
  #play-btn:hover {{ background:#ddd; }}
</style>
</head>
<body>
<div id="map">
  <div class="legend">
    <div style="text-align:center;margin-bottom:4px;font-weight:600;">Trace count</div>
    <div class="legend-bar"></div>
    <div class="legend-labels"><span>1</span><span>{max_count}</span></div>
  </div>
</div>
<div class="controls">
  <b>All edges</b>
  <button id="play-btn">▶</button>
  <input type="range" id="slider" min="0" max="100" value="0">
  <b>Below threshold removed</b>
</div>
<script>
const edges={json.dumps(edges)};
const minCount={min_count};

function makeLayers(t) {{
  const data=edges.map(e=>{{
    const remove=e.count<minCount;
    const a=remove ? Math.round((1-t)*200) : 200;
    const w=remove ? e.width*(1-t) : e.width;
    return {{path:e.path, color:[...e.color,a], width:Math.max(w,0.1)}};
  }});
  return [new deck.PathLayer({{
    id:'edges', data,
    getPath:d=>d.path, getColor:d=>d.color,
    getWidth:d=>d.width, widthMinPixels:1,
    updateTriggers:{{getColor:t, getWidth:t}},
  }})];
}}

const gl=new deck.DeckGL({{
  container:'map',
  mapStyle:'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json',
  initialViewState:{{latitude:{center_lat},longitude:{center_lon},zoom:13}},
  controller:true,
  layers:makeLayers(0),
}});

const slider=document.getElementById('slider');
slider.addEventListener('input',()=>{{
  gl.setProps({{layers:makeLayers(slider.value/100)}});
}});

let animId;
const btn=document.getElementById('play-btn');
btn.addEventListener('click',()=>{{
  slider.value=0;
  gl.setProps({{layers:makeLayers(0)}});
  animate();
}});
function animate(){{
  let v=parseInt(slider.value)+1;
  if(v>100) return;
  slider.value=v;
  gl.setProps({{layers:makeLayers(v/100)}});
  animId=requestAnimationFrame(()=>setTimeout(animate,12));
}}
</script>
</body>
</html>"""

    return (build_density_map,)


@app.cell
def _(base64, build_density_map, edge_data, max_edge_count, min_count_input, mo):
    mo.stop(not edge_data, mo.md("*No edges to display.*"))

    _html = build_density_map(edge_data, max_edge_count, min_count_input.value)
    _b64 = base64.b64encode(_html.encode()).decode()
    mo.Html(
        f'<iframe src="data:text/html;base64,{_b64}"'
        ' style="width:100%;height:620px;border:none;"></iframe>'
    )
    return


@app.cell
def _():
    def query_route_paths(conn, line_id):
        """Query the latest route path per ramal for a line."""
        import json as _json

        conn.rollback()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT r.ramal_label, re.sequence, ST_AsGeoJSON(re.path) as geojson
                FROM route_edges re
                JOIN routes r ON r.id = re.route_id
                WHERE r.line_id = %s::uuid
                  AND r.version = (
                    SELECT MAX(r2.version) FROM routes r2
                    WHERE r2.line_id = r.line_id AND r2.ramal_label = r.ramal_label
                  )
                ORDER BY r.ramal_label, re.sequence
                """,
                (line_id,),
            )
            rows = cur.fetchall()

        routes = {}
        for ramal, _seq, geojson_str in rows:
            coords = _json.loads(geojson_str)["coordinates"]
            if ramal not in routes:
                routes[ramal] = list(coords)
            else:
                routes[ramal].extend(coords[1:] if coords else [])

        return routes

    return (query_route_paths,)


@app.cell
def _(conn, line_selector, mo, query_route_paths):
    mo.stop(not line_selector.value, mo.md("*Select a line above.*"))

    route_paths = query_route_paths(conn, line_selector.value)

    mo.md(
        f"**{len(route_paths)}** ramal(es): "
        + ", ".join(f"**{k}** ({len(v)} pts)" for k, v in route_paths.items())
    )
    return (route_paths,)


@app.cell
def _(json, np):
    ROUTE_COLORS = [
        [230, 25, 75],
        [0, 130, 200],
        [60, 180, 75],
        [245, 130, 48],
        [145, 30, 180],
    ]

    def build_route_map(clean_paths, route_paths):
        """Build HTML map: cleaned traces → final route animation."""
        _traces = [{"path": t["path"], "color": t["color"]} for t in clean_paths]

        _routes = []
        for i, (ramal, coords) in enumerate(sorted(route_paths.items())):
            _routes.append({
                "path": coords,
                "color": ROUTE_COLORS[i % len(ROUTE_COLORS)],
                "ramal": ramal,
            })

        _all_lons, _all_lats = [], []
        for r in _routes:
            for p in r["path"]:
                _all_lons.append(p[0])
                _all_lats.append(p[1])
        for t in _traces:
            for p in t["path"]:
                _all_lons.append(p[0])
                _all_lats.append(p[1])
        center_lon = float(np.mean(_all_lons)) if _all_lons else 0
        center_lat = float(np.mean(_all_lats)) if _all_lats else 0

        legend_items = "".join(
            f'<div style="display:flex;align-items:center;gap:6px;">'
            f'<div style="width:20px;height:3px;background:rgb({r["color"][0]},{r["color"][1]},{r["color"][2]});border-radius:1px;"></div>'
            f'<span>{r["ramal"]}</span></div>'
            for r in _routes
        )

        return f"""\
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<script src="https://unpkg.com/deck.gl@9.1.14/dist.min.js"></script>
<script src="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.js"></script>
<link href="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.css" rel="stylesheet"/>
<style>
  body {{ margin:0; font-family:system-ui,sans-serif; }}
  #map {{ width:100%; height:560px; position:relative; }}
  .legend {{
    position:absolute; bottom:20px; right:20px; z-index:1;
    background:rgba(255,255,255,0.92); padding:10px 14px;
    border-radius:6px; font-size:12px; box-shadow:0 1px 4px rgba(0,0,0,.15);
  }}
  .legend-title {{ font-weight:600; margin-bottom:4px; }}
  .controls {{ display:flex; align-items:center; gap:8px; padding:8px 12px; justify-content:center; }}
  .controls input[type=range] {{ width:240px; }}
  #play-btn {{
    border:none; background:#eee; border-radius:4px;
    padding:4px 10px; cursor:pointer; font-size:14px;
  }}
  #play-btn:hover {{ background:#ddd; }}
</style>
</head>
<body>
<div id="map">
  <div class="legend">
    <div class="legend-title">Ramales</div>
    {legend_items}
  </div>
</div>
<div class="controls">
  <b>Cleaned traces</b>
  <button id="play-btn">▶</button>
  <input type="range" id="slider" min="0" max="100" value="0">
  <b>Final route</b>
</div>
<script>
const traces={json.dumps(_traces)};
const routes={json.dumps(_routes)};

function makeLayers(t) {{
  const traceAlpha=Math.round((1-t)*150);
  const tracesLayer=new deck.PathLayer({{
    id:'traces', data:traces,
    getPath:d=>d.path,
    getColor:d=>[...d.color,traceAlpha],
    getWidth:2, widthMinPixels:1,
    updateTriggers:{{getColor:traceAlpha}},
  }});
  const routeAlpha=Math.round(t*255);
  const routeWidth=1+t*1.5;
  const routesLayer=new deck.PathLayer({{
    id:'routes', data:routes,
    getPath:d=>d.path,
    getColor:d=>[...d.color,routeAlpha],
    getWidth:routeWidth, widthMinPixels:Math.max(1,Math.round(t*2)),
    updateTriggers:{{getColor:routeAlpha, getWidth:t}},
  }});
  return [tracesLayer, routesLayer];
}}

const gl=new deck.DeckGL({{
  container:'map',
  mapStyle:'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json',
  initialViewState:{{latitude:{center_lat},longitude:{center_lon},zoom:13}},
  controller:true,
  layers:makeLayers(0),
}});

const slider=document.getElementById('slider');
slider.addEventListener('input',()=>{{
  gl.setProps({{layers:makeLayers(slider.value/100)}});
}});

let animId;
const btn=document.getElementById('play-btn');
btn.addEventListener('click',()=>{{
  slider.value=0;
  gl.setProps({{layers:makeLayers(0)}});
  animate();
}});
function animate(){{
  let v=parseInt(slider.value)+1;
  if(v>100) return;
  slider.value=v;
  gl.setProps({{layers:makeLayers(v/100)}});
  animId=requestAnimationFrame(()=>setTimeout(animate,12));
}}
</script>
</body>
</html>"""

    return (build_route_map,)


@app.cell
def _(base64, build_route_map, mo, route_paths, trace_points):
    mo.stop(not route_paths, mo.md("*No routes found for this line.*"))

    _clean = trace_points["clean_paths"][: trace_points["n_paired"]]
    _html = build_route_map(_clean, route_paths)
    _b64 = base64.b64encode(_html.encode()).decode()
    mo.Html(
        f'<iframe src="data:text/html;base64,{_b64}"'
        ' style="width:100%;height:620px;border:none;"></iframe>'
    )
    return


if __name__ == "__main__":
    app.run()
