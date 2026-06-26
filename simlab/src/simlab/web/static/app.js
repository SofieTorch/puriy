/* simlab frontend: scenario picker, run list, stage layers, metrics. */

const STAGE_LAYERS = [
  { file: "00_ground_truth.geojson", label: "Ground truth", color: "data", fallback: "#9aa0a8", width: 5, opacity: 0.5 },
  { file: "01_raw_traces.geojson", label: "Raw traces", color: "data", fallback: "#f2994a", width: 1.5, opacity: 0.5,
    lineFilter: ["==", ["get", "kind"], "raw_trace"], pointsFilter: ["==", ["get", "kind"], "raw_points"] },
  { file: "02_matched_traces.geojson", label: "Matched traces", color: "data", fallback: "#56ccf2", width: 1.5, opacity: 0.6 },
  { file: "03_ramales.geojson", label: "Ramal clusters", color: "data", fallback: "#9aa0a8", width: 2.5, opacity: 0.8, off: true, ramalToggles: true },
  { file: "04_consensus.geojson", label: "Consensus route", color: "confidence", width: 4, opacity: 0.9 },
  { file: "05_votes.geojson", label: "Votes", color: "votes", width: 4, opacity: 0.9, off: true },
  { file: "07_fares.geojson", label: "Fare reports", color: "#bb6bd9", width: 4, opacity: 0.8, off: true, circle: true, labelField: "amount_bob" },
];

let map;
let currentRun = null;
let pollTimer = null;

init();

async function init() {
  map = new maplibregl.Map({
    container: "map",
    style: "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
    center: [-66.157, -17.3935],
    zoom: 12,
    preserveDrawingBuffer: true, // PNG export
  });
  map.addControl(new maplibregl.NavigationControl(), "top-right");
  // The grid layout may settle after map init: keep the canvas synced.
  map.on("load", () => map.resize());
  new ResizeObserver(() => map.resize()).observe(document.getElementById("map"));

  await loadScenarios();
  await refreshRuns();

  document.getElementById("run-button").onclick = startRun;
  document.getElementById("export-png").onclick = exportPng;
  document.getElementById("clear-runs").onclick = deleteAllRuns;
  document.getElementById("measure-toggle").onclick = toggleMeasure;
  document.getElementById("metrics-toggle").onclick = () =>
    document.body.classList.toggle("metrics-open");
  document.getElementById("manage-scenarios").onclick = openManageScenarios;
  document.getElementById("manage-close").onclick = () =>
    (document.getElementById("scenario-manage").hidden = true);
  document.getElementById("manage-delete").onclick = deleteSelectedScenarios;
  document.getElementById("exp-run-all").onclick = runAllInGroup;
  await loadExperimentGroups();

  // Auto-refresh the run list so new/in-progress runs appear without a manual
  // reload (this is what used to require refreshing the page).
  setInterval(() => refreshRuns(), 2500);
  // Resume tracking a server-side batch across a page refresh.
  const activeBatch = localStorage.getItem("activeBatch");
  if (activeBatch) _pollBatch(activeBatch);

  // Database mode: promote scenarios → DB, run the real pipeline, visualize.
  document.getElementById("db-promote").onclick = () => promoteScenario();
  document.getElementById("db-new-line").onclick = createDbLine;
  document.getElementById("db-rebuild-graph").onclick = rebuildDirectionsGraph;
  document.getElementById("db-import-zones").onclick = importMunicipalities;
  document.getElementById("db-infer-schedules").onclick = inferSchedules;
  document.getElementById("db-wipe").onclick = openWipeModal;
  document.getElementById("wipe-cancel").onclick = closeWipeModal;
  document.getElementById("wipe-continue").onclick = wipeStep2;
  document.getElementById("wipe-input").oninput = (e) => {
    document.getElementById("wipe-final").disabled =
      e.target.value.trim().toUpperCase() !== "DELETE";
  };
  document.getElementById("wipe-final").onclick = doWipe;
  document.getElementById("db-vsegs-mintrips").onchange = () => {
    if (_currentDbLine) renderVoteableSegments(_currentDbLine);
  };
  document.getElementById("mode-scenario-btn").onclick = () => setMode("scenario");
  document.getElementById("mode-database-btn").onclick = () => setMode("database");
  document.getElementById("mode-inspect-btn").onclick = () => setMode("inspect");
  document.getElementById("inspect-refresh").onclick = loadInspector;
  document.getElementById("inspect-eligible-only").onchange = renderInspector;
  document.getElementById("inspect-line").onchange = renderInspector;
  document.getElementById("inspect-zones").onchange = (e) => toggleFareZones(e.target.checked);
  initSidebarResize();
  setMode(localStorage.getItem("simlabMode") || "scenario");
}

/* ---------- resizable sidebar ---------- */

function initSidebarResize() {
  const KEY = "simlabSidebarW";
  const root = document.documentElement;
  const MIN = 240, MAX = 760;
  const saved = parseInt(localStorage.getItem(KEY), 10);
  if (saved >= MIN && saved <= MAX) root.style.setProperty("--sidebar-w", saved + "px");

  const handle = document.getElementById("sidebar-resizer");
  let dragging = false;
  const onMove = (e) => {
    if (!dragging) return;
    const w = Math.max(MIN, Math.min(MAX, e.clientX));
    root.style.setProperty("--sidebar-w", w + "px");
  };
  const stop = () => {
    if (!dragging) return;
    dragging = false;
    handle.classList.remove("dragging");
    document.body.style.userSelect = "";
    const w = parseInt(getComputedStyle(root).getPropertyValue("--sidebar-w"), 10);
    if (w) localStorage.setItem(KEY, String(w));
    window.removeEventListener("mousemove", onMove);
    window.removeEventListener("mouseup", stop);
  };
  handle.addEventListener("mousedown", (e) => {
    e.preventDefault();
    dragging = true;
    handle.classList.add("dragging");
    document.body.style.userSelect = "none";   // no text selection while dragging
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", stop);
  });
  // Double-click the handle to reset to the default width.
  handle.addEventListener("dblclick", () => {
    root.style.setProperty("--sidebar-w", "300px");
    localStorage.removeItem(KEY);
  });
}

/* ---------- database mode ---------- */

function setMode(mode) {
  for (const m of ["scenario", "database", "inspect"]) {
    document.body.classList.toggle(`mode-${m}`, mode === m);
    document.getElementById(`mode-${m}-btn`).classList.toggle("active", mode === m);
  }
  localStorage.setItem("simlabMode", mode);
  if (mode === "database") { loadDbLines(); loadSchedules(); }
  else clearDbLayers();
  if (mode === "inspect") loadInspector();
}

function _dbStatus(text) {
  // The Database-mode status line and the scenario-tab Advanced accordion's
  // status line mirror each other; only one is visible at a time (mode-gated).
  for (const id of ["db-status", "advanced-status"]) {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
  }
}

async function promoteScenario(lineId) {
  const id = document.getElementById("scenario-select").value;
  if (!id) return;
  _dbStatus(lineId ? `Adding "${id}" traces to the line…`
                   : `Promoting "${id}" to a new line…`);
  const lineType = document.getElementById("db-line-type")?.value || null;
  const resp = await fetch(`/api/scenarios/${encodeURIComponent(id)}/promote`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(lineId
      ? { line_id: lineId }
      : { line_name: id, line_type: lineType }),
  });
  if (!resp.ok) { _dbStatus("Promote failed."); return; }
  const r = await resp.json();
  _dbStatus(`Line "${r.line_name}" now has +${r.sessions} traces, ${r.devices} ` +
            `devices. Click ▶ Build to run the pipeline.`);
  await loadDbLines();
}

/* ---------- wipe database (double-confirm modal) ---------- */

function openWipeModal() {
  document.getElementById("wipe-step2").hidden = true;
  document.getElementById("wipe-final").hidden = true;
  document.getElementById("wipe-final").disabled = true;
  document.getElementById("wipe-continue").hidden = false;
  document.getElementById("wipe-input").value = "";
  document.getElementById("wipe-status").textContent = "";
  document.getElementById("wipe-modal").hidden = false;
}

function closeWipeModal() {
  document.getElementById("wipe-modal").hidden = true;
}

function wipeStep2() {
  document.getElementById("wipe-continue").hidden = true;
  document.getElementById("wipe-step2").hidden = false;
  document.getElementById("wipe-final").hidden = false;
  document.getElementById("wipe-input").focus();
}

async function doWipe() {
  const input = document.getElementById("wipe-input").value.trim();
  const status = document.getElementById("wipe-status");
  status.textContent = "Wiping…";
  let j;
  try {
    const r = await fetch("/api/wipe-database", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ confirm: input }),
    });
    j = await r.json();
  } catch (e) { status.textContent = "Request failed: " + e; return; }
  if (j.ok) {
    const c = j.cleared || {};
    closeWipeModal();
    clearDbLayers();
    await loadDbLines();
    _dbStatus(`Database wiped: ${c.lines} line(s) · ${c.trip_sessions} sessions · ` +
      `${c.routes} routes · ${c.fare_reports} fare reports cleared. ` +
      `Kept ${j.kept.fare_zones} fare zones + ${j.kept.devices} devices.`);
  } else {
    status.textContent = "Failed: " + (j.detail || j.error || "unknown");
  }
}

async function importMunicipalities() {
  _dbStatus("Importing Cochabamba municipalities from OpenStreetMap (Overpass) — " +
            "this can take up to a minute…");
  let j;
  try {
    const r = await fetch("/api/import-zones", { method: "POST" });
    j = await r.json();
  } catch (e) {
    _dbStatus("Import request failed: " + e);
    return;
  }
  if (j.ok) {
    _dbStatus(`Municipalities imported: ${j.created} new · ${j.updated} updated · ` +
              `${j.total} fare zones total.`);
  } else {
    _dbStatus("Municipality import failed: " + j.error);
  }
}

async function inferSchedules() {
  _dbStatus("Inferring service hours + frequency from trip timestamps…");
  let j;
  try {
    const r = await fetch("/api/infer-schedules", { method: "POST" });
    j = await r.json();
  } catch (e) {
    _dbStatus("Infer schedules failed: " + e);
    return;
  }
  _dbStatus(`Schedules inferred: ${j.lines_inferred ?? 0} line(s) · ` +
            `${j.schedule_rows_written ?? 0} day-bucket rows.`);
  await loadSchedules();
}

const DAY_LABELS = { weekday: "Lun–Vie", saturday: "Sáb", sunday: "Dom" };

function _clock(t) {
  return t ? String(t).slice(0, 5) : null; // "06:00:00" → "06:00"
}

async function loadSchedules() {
  const box = document.getElementById("db-schedules");
  if (!box) return;
  let data;
  try { data = await api("/schedules"); } catch { return; }
  const lines = data.lines || [];
  if (lines.length === 0) {
    box.className = "muted";
    box.textContent = "No schedules yet. Run “🕐 Infer schedules”.";
    return;
  }
  box.className = "";
  box.innerHTML = lines.map((ln) => {
    // Only show day-buckets that actually inferred something.
    const valid = (ln.schedules || []).filter(
      (s) => s.service_start_at || s.headway_min != null,
    );
    const rows = valid.length
      ? valid.map((s) => {
          const start = _clock(s.service_start_at);
          const end = _clock(s.service_end_at);
          const parts = [];
          if (start && end) parts.push(`${start}–${end}`);
          if (s.headway_min != null) parts.push(`c/ ${s.headway_min} min`);
          return `<div class="sched-row"><span class="sched-day">${DAY_LABELS[s.day_bucket] || s.day_bucket}</span>` +
                 `<span class="sched-val">${parts.join(" · ") || "—"}</span></div>`;
        }).join("")
      : `<div class="sched-row"><span class="sched-val muted">sin horario inferido</span></div>`;
    return `<div class="sched-line"><div class="sched-name">${ln.line_name}</div>${rows}</div>`;
  }).join("");
}

async function rebuildDirectionsGraph() {
  _dbStatus("Rebuilding the API server's directions graph…");
  let j;
  try {
    const r = await fetch("/api/rebuild-graph", { method: "POST" });
    j = await r.json();
  } catch (e) {
    _dbStatus("Rebuild request failed: " + e);
    return;
  }
  if (j.ok) {
    const g = j.result || {};
    _dbStatus(`Directions graph rebuilt: ${g.lines} line(s) · ${g.bus_edges} ` +
              `bus edges · ${g.transfer_edges} transfers. A→B routing is fresh.`);
  } else {
    _dbStatus(`Rebuild failed (${j.url}): ${j.error}. Is the API server running?`);
  }
}

async function createDbLine() {
  const name = prompt("New line name:");
  if (!name) return;
  const resp = await fetch("/api/lines", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  if (!resp.ok) { _dbStatus("Could not create line."); return; }
  _dbStatus(`Created empty line "${name}". Use ⬆ on it to add a scenario's traces.`);
  await loadDbLines();
}

async function renameDbLine(id, current) {
  const name = prompt("Rename line:", current);
  if (!name || name === current) return;
  await fetch(`/api/lines/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  await loadDbLines();
}

async function loadDbLines() {
  let lines;
  try { lines = await api("/lines"); } catch { return; }
  const list = document.getElementById("db-line-list");
  list.innerHTML = "";
  for (const ln of lines) {
    const li = document.createElement("li");
    li.className = "db-line";
    li.innerHTML =
      `<div class="db-line-head"><span class="db-line-name">${ln.name}` +
      `${ln.line_type ? ` <span class="db-line-type-tag">${ln.line_type}</span>` : ""}</span>` +
      `<span class="run-metric">${ln.sessions} sess · ${ln.trips} trips · ` +
      `${ln.routes} routes</span></div>`;
    const actions = document.createElement("div");
    actions.className = "db-line-actions";
    actions.appendChild(_dbBtn("▶ Build", () => reconstructLine(ln.id),
      "Run the pipeline (clean + reconstruct) on this line"));
    actions.appendChild(_dbBtn("👁 Show", () => showLine(ln.id),
      "Show its route + traces on the map"));
    actions.appendChild(_dbBtn("⬆", () => promoteScenario(ln.id),
      "Add the selected scenario's traces to this line"));
    actions.appendChild(_dbBtn("✎", () => renameDbLine(ln.id, ln.name),
      "Rename this line"));
    actions.appendChild(_dbBtn("🗑", () => deleteDbLine(ln.id, ln.name),
      "Delete this line and all its data"));
    li.appendChild(actions);
    list.appendChild(li);
  }
}

function _dbBtn(label, onclick, title) {
  const b = document.createElement("button");
  b.className = "small";
  b.textContent = label;
  if (title) b.title = title;
  b.onclick = onclick;
  return b;
}

async function reconstructLine(id) {
  _dbStatus("Running the production pipeline (clean + build) — this calls " +
            "Valhalla, may take a moment…");
  renderDbSteps([
    { name: "clean_traces", status: "running" },
    { name: "reconstruct_routes", status: "pending" },
  ]);
  let resp;
  try {
    resp = await fetch(`/api/lines/${id}/reconstruct`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ strategy: "routebuilder_divergence", clean: true }),
    });
  } catch (e) {
    _dbStatus("Build request failed: " + e);
    renderDbSteps([{ name: "request", status: "failed", info: String(e) }]);
    return;
  }
  if (!resp.ok) {
    _dbStatus(`Build failed (HTTP ${resp.status}).`);
    renderDbSteps([{ name: "reconstruct", status: "failed", info: `HTTP ${resp.status}` }]);
    return;
  }
  const r = await resp.json();
  const ct = r.clean_traces || {};
  const rr = r.reconstruct_routes || {};
  renderDbSteps([
    { name: "clean_traces", status: "completed",
      info: `${ct.sessions_matched ?? "?"} matched · ${ct.sessions_failed ?? 0} failed` },
    { name: "reconstruct_routes", status: "completed",
      info: `${rr.ramales_created ?? 0} ramal(es) · ${rr.strategy || ""}` },
  ]);
  const n = rr.ramales_created ?? 0;
  _dbStatus(n > 0
    ? `Built ${n} ramal(es). Showing on map.`
    : "Built 0 routes — see Pipeline steps. (If clean_traces matched but 0 " +
      "ramales: those trips predate the match-attributes change — promote a fresh line.)");
  await loadDbLines();
  await showLine(id);
}

function renderDbSteps(steps) {
  document.getElementById("db-steps-box").hidden = false;
  const ul = document.getElementById("db-steps");
  ul.innerHTML = "";
  for (const s of steps) {
    const cls = { completed: "status-completed", failed: "status-failed",
      running: "status-running" }[s.status] || "status-pending";
    const icon = { completed: "✓", failed: "✗", running: "…" }[s.status] || "·";
    const li = document.createElement("li");
    li.innerHTML = `<span>${s.name}</span>` +
      `<span class="${cls}">${icon} ${s.info || ""}</span>`;
    ul.appendChild(li);
  }
}

async function showLine(id) {
  _currentDbLine = id;
  const [routes, traces, fares] = await Promise.all([
    api(`/lines/${id}/routes`),
    api(`/lines/${id}/traces`),
    api(`/lines/${id}/fare-reports`).catch(() => ({ features: [] })),
  ]);
  setDbLayers(routes, traces, fares);
  await renderVoteableSegments(id);
}

async function deleteDbLine(id, name) {
  if (!confirm(`Delete line "${name}" and all its data (sessions, trips, routes)?`))
    return;
  await fetch(`/api/lines/${id}`, { method: "DELETE" });
  clearDbLayers();
  await loadDbLines();
}

const _DB_PALETTE = ["#e3514f", "#2d9cdb", "#6fcf97", "#f2c94c", "#bb6bd9", "#f2994a"];
let _dbLayerIds = [];   // every db map layer currently shown (for cleanup)

function setDbLayers(routesFC, tracesFC, faresFC) {
  clearDbLayers();   // fresh start — no stale layers
  const box = document.getElementById("db-layers");
  document.getElementById("db-layers-box").hidden = false;
  box.innerHTML = "";

  // Raw traces: one faint grey layer.
  const traces = tracesFC.features || [];
  _setDbGeo("db-traces", tracesFC,
    { "line-color": "#9aa0a8", "line-width": 1.5, "line-opacity": 0.4 });
  box.appendChild(_dbLayerRow("Raw traces", "db-traces", "#9aa0a8", `${traces.length}`));

  // Fare reports: boarding/alighting points labelled with the amount (off by
  // default — toggle on to inspect the crowdsourced fares behind the estimate).
  const fares = (faresFC && faresFC.features) || [];
  if (fares.length) {
    _addDbFareLayer(faresFC, false);
    box.appendChild(_dbFareRow(fares.length));
  }

  // Fare zones (municipalities) overlay — off by default, shared toggle logic.
  box.appendChild(_dbZonesRow());

  // One colored layer + toggle PER reconstructed ramal (added last → on top).
  const routes = routesFC.features || [];
  _dbRamalCoords = routes.map((f) => f.geometry.coordinates);   // for fare hover
  routes.forEach((f, i) => {
    const label = (f.properties || {}).ramal_label ?? `ramal ${i}`;
    const color = _DB_PALETTE[i % _DB_PALETTE.length];
    const id = `db-ramal-${i}`;
    _setDbGeo(id, { type: "FeatureCollection", features: [f] },
      { "line-color": color, "line-width": 4, "line-opacity": 0.9 });
    box.appendChild(_dbLayerRow(`Ramal ${label}`, id, color,
      `${f.geometry.coordinates.length} pts`));
  });
  if (!routes.length) {
    const p = document.createElement("p");
    p.className = "muted";
    p.textContent = "No reconstructed route on this line yet — click ▶ Build.";
    box.appendChild(p);
  }

  let bounds = null;
  for (const f of [...routes, ...traces]) {
    for (const c of f.geometry.coordinates) {
      bounds = bounds || new maplibregl.LngLatBounds(c, c);
      bounds.extend(c);
    }
  }
  if (bounds) map.fitBounds(bounds, { padding: 48, duration: 500 });
}

function _dbLayerRow(label, layerId, color, count) {
  const row = document.createElement("label");
  row.className = "layer-row";
  row.innerHTML =
    `<input type="checkbox" checked />` +
    `<span class="swatch" style="background:${color}"></span>` +
    `<span>${label}</span><span class="run-metric">${count}</span>`;
  row.querySelector("input").onchange = (e) => {
    if (map.getLayer(layerId)) {
      map.setLayoutProperty(layerId, "visibility",
        e.target.checked ? "visible" : "none");
    }
  };
  return row;
}

// --- fare hover: highlight the route span a fare applies to ---------------

let _dbRamalCoords = [];
let _fareHoverWired = false;

function _nearestIdx(coords, pt) {
  let best = 0, bestD = Infinity;
  for (let i = 0; i < coords.length; i++) {
    const dx = coords[i][0] - pt[0], dy = coords[i][1] - pt[1];
    const d = dx * dx + dy * dy;
    if (d < bestD) { bestD = d; best = i; }
  }
  return { idx: best, dist: bestD };
}

// Highlight the stretch of route between a fare's boarding and alighting
// points — i.e. where that fare applies. Picks the ramal closest to both ends;
// falls back to a straight connector if neither end is near a route.
function _highlightFareSpan(board, alight) {
  let seg = null, bestCost = Infinity;
  for (const coords of _dbRamalCoords) {
    if (!coords || coords.length < 2) continue;
    const b = _nearestIdx(coords, board), a = _nearestIdx(coords, alight);
    const cost = b.dist + a.dist;
    if (cost < bestCost) {
      bestCost = cost;
      seg = coords.slice(Math.min(b.idx, a.idx), Math.max(b.idx, a.idx) + 1);
    }
  }
  if (!seg || seg.length < 2) seg = [board, alight];
  const fc = { type: "FeatureCollection", features: [
    { type: "Feature", geometry: { type: "LineString", coordinates: seg } }] };
  const src = "db-fare-hl-src";
  if (map.getSource(src)) {
    map.getSource(src).setData(fc);
  } else {
    map.addSource(src, { type: "geojson", data: fc });
    map.addLayer({
      id: "db-fare-hl", type: "line", source: src,
      layout: { "line-cap": "round", "line-join": "round" },
      // bright gold so the span pops over the (blue) route line
      paint: { "line-color": "#ffb000", "line-width": 9, "line-opacity": 0.95 },
    }, "db-fares");   // under the points so they stay clickable
  }
}

function _clearFareHighlight() {
  if (map.getLayer("db-fare-hl")) map.removeLayer("db-fare-hl");
  if (map.getSource("db-fare-hl-src")) map.removeSource("db-fare-hl-src");
}

function _wireFareHover() {
  if (_fareHoverWired) return;
  _fareHoverWired = true;
  map.on("mouseenter", "db-fares", () => { map.getCanvas().style.cursor = "pointer"; });
  map.on("mousemove", "db-fares", (e) => {
    const f = e.features && e.features[0];
    if (!f) return;
    let board = f.properties.board, alight = f.properties.alight;
    try {
      if (typeof board === "string") board = JSON.parse(board);
      if (typeof alight === "string") alight = JSON.parse(alight);
    } catch (err) { return; }
    _highlightFareSpan(board, alight);
  });
  map.on("mouseleave", "db-fares", () => {
    map.getCanvas().style.cursor = "";
    _clearFareHighlight();
  });
}

// Fare reports → a circle layer + an amount-label layer sharing one source.
function _addDbFareLayer(fc, visible) {
  const src = "db-fares-src";
  const apply = () => {
    map.addSource(src, { type: "geojson", data: fc });
    map.addLayer({
      id: "db-fares", type: "circle", source: src,
      paint: {
        "circle-radius": 4, "circle-color": "#bb6bd9", "circle-opacity": 0.85,
        "circle-stroke-width": 1, "circle-stroke-color": "#ffffff",
      },
    });
    map.addLayer({
      id: "db-fares-label", type: "symbol", source: src,
      filter: ["==", ["get", "kind"], "fare_alighting"],   // label at the end
      layout: {
        "text-field": ["concat", "Bs ",
          ["number-format", ["get", "amount_bob"],
            { "min-fraction-digits": 2, "max-fraction-digits": 2 }]],
        "text-size": 13, "text-offset": [0, 1], "text-anchor": "top",
        "text-allow-overlap": false,
      },
      paint: {
        "text-color": "#7a3fa0", "text-halo-color": "#ffffff", "text-halo-width": 1.8,
      },
    });
    for (const id of ["db-fares", "db-fares-label"]) {
      map.setLayoutProperty(id, "visibility", visible ? "visible" : "none");
      if (!_dbLayerIds.includes(id)) _dbLayerIds.push(id);
    }
  };
  try { apply(); } catch (e) { map.once("idle", apply); }
  _wireFareHover();
}

function _dbZonesRow() {
  const row = document.createElement("label");
  row.className = "layer-row";
  row.innerHTML =
    `<input type="checkbox" id="db-zones" />` +
    `<span class="swatch" style="background:#9b51e0"></span>` +
    `<span>Fare zones</span><span class="run-metric">municipalities</span>`;
  row.querySelector("input").onchange = (e) => toggleFareZones(e.target.checked);
  return row;
}

function _dbFareRow(count) {
  const row = document.createElement("label");
  row.className = "layer-row";
  row.innerHTML =
    `<input type="checkbox" />` +
    `<span class="swatch" style="background:#bb6bd9"></span>` +
    `<span>Fare reports</span><span class="run-metric">${count} pts</span>`;
  row.querySelector("input").onchange = (e) => {
    for (const id of ["db-fares", "db-fares-label"]) {
      if (map.getLayer(id)) {
        map.setLayoutProperty(id, "visibility", e.target.checked ? "visible" : "none");
      }
    }
    if (!e.target.checked) _clearFareHighlight();
  };
  return row;
}

function _setDbGeo(id, fc, paint) {
  const src = `${id}-src`;
  const apply = () => {
    // Always remove + re-add — a leftover source without its layer (or vice
    // versa) would otherwise leave the route present in data but not drawn.
    if (map.getLayer(id)) map.removeLayer(id);
    if (map.getSource(src)) map.removeSource(src);
    map.addSource(src, { type: "geojson", data: fc });
    map.addLayer({
      id, type: "line", source: src,
      layout: { "line-cap": "round", "line-join": "round" }, paint,
    });
    if (!_dbLayerIds.includes(id)) _dbLayerIds.push(id);
  };
  // Add directly when possible; on failure (style mid-update — common right
  // after adding the previous layer) retry on "idle", which RE-fires — unlike
  // "load", which only fires once and would never run after initial load.
  try {
    apply();
  } catch (e) {
    map.once("idle", apply);
  }
}

function clearDbLayers() {
  // Two passes: remove every layer first, then sources — the fare circle and
  // label layers share one source, which can't be dropped while in use.
  for (const id of _dbLayerIds) if (map.getLayer(id)) map.removeLayer(id);
  for (const id of _dbLayerIds) {
    if (map.getSource(`${id}-src`)) map.removeSource(`${id}-src`);
  }
  _clearFareHighlight();
  if (map.getSource("db-fares-src")) map.removeSource("db-fares-src");
  _dbLayerIds = [];
  const layersBox = document.getElementById("db-layers-box");
  if (layersBox) layersBox.hidden = true;
  clearVsegLayers();
  clearFareZones();
  const zonesCb = document.getElementById("inspect-zones");
  if (zonesCb) zonesCb.checked = false;
}

/* ---------- voteable segments (preview of the per-rider vote UI) ---------- */

// Leads with colors distinct from the route ramal layers (red/blue) so a
// rider's voteable highlight pops against the route it overlays.
const _VSEG_PALETTE = ["#27ae60", "#9b51e0", "#f2994a", "#e91e63", "#00bcd4",
  "#7cb342", "#ff8f00", "#2f80ed", "#5c6bc0", "#eb5757"];
let _currentDbLine = null;
let _vsegLayerIds = [];   // every voteable-segment map layer currently shown

function clearVsegLayers() {
  for (const id of _vsegLayerIds) {
    if (map.getLayer(id)) map.removeLayer(id);
    if (map.getSource(`${id}-src`)) map.removeSource(`${id}-src`);
  }
  _vsegLayerIds = [];
  const box = document.getElementById("db-vsegs-box");
  if (box) box.hidden = true;
}

function _setVsegVisible(id, coords, color, visible) {
  const src = `${id}-src`;
  const fc = { type: "FeatureCollection", features: [
    { type: "Feature", geometry: { type: "LineString", coordinates: coords } }] };
  const apply = () => {
    if (!map.getSource(src)) {
      map.addSource(src, { type: "geojson", data: fc });
      map.addLayer({
        id, type: "line", source: src,
        layout: { "line-cap": "round", "line-join": "round" },
        paint: { "line-color": color, "line-width": 6, "line-opacity": 0.85 },
      });
      if (!_vsegLayerIds.includes(id)) _vsegLayerIds.push(id);
    }
    map.setLayoutProperty(id, "visibility", visible ? "visible" : "none");
  };
  try { apply(); } catch (e) { map.once("idle", apply); }
}

async function renderVoteableSegments(lineId) {
  clearVsegLayers();
  const box = document.getElementById("db-vsegs-box");
  const tree = document.getElementById("db-vsegs");
  const summary = document.getElementById("db-vsegs-summary");
  tree.innerHTML = "";
  box.hidden = false;

  const minTrips = Math.max(1, parseInt(
    document.getElementById("db-vsegs-mintrips").value, 10) || 1);
  let data;
  try {
    data = await api(`/lines/${lineId}/voteable-segments?min_trips=${minTrips}`);
  } catch (e) {
    summary.textContent = "failed to load";
    return;
  }
  const users = data.users || [];
  const nSeg = users.reduce((a, u) => a + u.segments.length, 0);
  summary.textContent =
    `${users.length} rider(s) · ${nSeg} segment(s) · ${data.ramal_count} ramal(es)`;
  if (!users.length) {
    tree.innerHTML =
      `<p class="muted">No rider has ≥${minTrips} trip(s) on this line. ` +
      `Sim non-voters record a single trip; lower Min trips to 1 to see them.</p>`;
    return;
  }

  users.forEach((u, ui) => {
    const color = _VSEG_PALETTE[ui % _VSEG_PALETTE.length];
    const persona = (u.device_id.split(":")[1] || u.device_id).trim();
    const details = document.createElement("details");
    details.className = "vseg-user";

    const sum = document.createElement("summary");
    sum.innerHTML =
      `<input type="checkbox" class="vseg-user-cb" />` +
      `<span class="swatch" style="background:${color}"></span>` +
      `<span class="vseg-user-name">User ${ui + 1}</span>` +
      `<span class="run-metric">${u.segments.length} seg · ${u.trip_count} trips</span>`;
    sum.title = u.device_id;
    details.appendChild(sum);

    const kids = [];
    u.segments.forEach((s, si) => {
      const layerId = `db-vseg-${ui}-${si}`;
      const row = document.createElement("label");
      row.className = "vseg-seg layer-row";
      const km = (s.length_m / 1000).toFixed(2);
      row.innerHTML =
        `<input type="checkbox" />` +
        `<span class="swatch" style="background:${color}"></span>` +
        `<span>Segment ${si + 1} <span class="muted">${s.ramal_label}</span></span>` +
        `<span class="run-metric">${s.edge_count}e · ${km} km</span>`;
      const cb = row.querySelector("input");
      cb.onchange = () => {
        _setVsegVisible(layerId, s.geometry, color, cb.checked);
        syncUserCb();
      };
      kids.push({ cb, layerId, coords: s.geometry, color });
      details.appendChild(row);
    });

    const userCb = sum.querySelector(".vseg-user-cb");
    // Clicking the parent checkbox shouldn't also toggle the <details>.
    userCb.onclick = (e) => e.stopPropagation();
    userCb.onchange = () => {
      kids.forEach((k) => {
        k.cb.checked = userCb.checked;
        _setVsegVisible(k.layerId, k.coords, k.color, userCb.checked);
      });
    };
    function syncUserCb() {
      const on = kids.filter((k) => k.cb.checked).length;
      userCb.checked = on === kids.length;
      userCb.indeterminate = on > 0 && on < kids.length;
    }

    tree.appendChild(details);
  });
}

/* ---------- database inspector ---------- */

let _inspectorDevices = [];
let _inspectorMinTrips = 3;

async function loadInspector() {
  const summary = document.getElementById("inspect-summary");
  summary.textContent = "loading…";
  let data;
  try { data = await api("/inspect/devices"); }
  catch (e) { summary.textContent = "failed to load"; return; }
  _inspectorDevices = data.devices || [];
  _inspectorMinTrips = data.min_trips ?? 3;
  _populateInspectLines();
  renderInspector();
}

/** Fill the line dropdown from the lines present in the data, keeping the
 * current selection if it still exists. */
function _populateInspectLines() {
  const sel = document.getElementById("inspect-line");
  const prev = sel.value;
  const names = [...new Set(
    _inspectorDevices.flatMap((d) => d.lines.map((l) => l.line_name))
  )].filter((n) => n && n !== "(no line)").sort();
  sel.innerHTML = `<option value="">all lines</option>` +
    names.map((n) => `<option value="${_esc(n)}">${_esc(n)}</option>`).join("");
  if (names.includes(prev)) sel.value = prev;
}

/** A device can vote on `line` if it has >= min_trips clean trips there; with
 * no line selected, "any line". */
function _deviceEligible(dev, line) {
  if (!line) return dev.eligible_any;
  const l = dev.lines.find((x) => x.line_name === line);
  return !!(l && l.eligible);
}

function renderInspector() {
  const box = document.getElementById("inspect-devices");
  const summary = document.getElementById("inspect-summary");
  const eligibleOnly = document.getElementById("inspect-eligible-only").checked;
  const line = document.getElementById("inspect-line").value;
  box.innerHTML = "";

  const totalElig = _inspectorDevices.filter((d) => _deviceEligible(d, line)).length;
  summary.textContent =
    `${_inspectorDevices.length} device(s) · ${totalElig} eligible to vote ` +
    `${line ? `on ${line}` : "on any line"} (≥${_inspectorMinTrips} clean trips)`;

  const devices = eligibleOnly
    ? _inspectorDevices.filter((d) => _deviceEligible(d, line))
    : _inspectorDevices;

  for (const dev of devices) {
    const details = document.createElement("details");
    details.className = "insp-device";

    const eligible = _deviceEligible(dev, line);
    // When a line is selected, show that line's clean count; else the total.
    const lineEntry = line && dev.lines.find((l) => l.line_name === line);
    const cleanLabel = lineEntry
      ? `${lineEntry.clean_trips} clean on ${line}`
      : `${dev.clean_trip_count} clean`;

    const sum = document.createElement("summary");
    const star = eligible
      ? `<span class="insp-star" title="enough clean trips to vote">★</span>`
      : `<span class="insp-star-empty"></span>`;
    sum.innerHTML =
      star +
      `<code class="insp-id" title="click to copy id">${_esc(dev.id)}</code>` +
      `<span class="run-metric">${dev.session_count} sess · ${cleanLabel} · ` +
      `${_fmtTime(dev.last_seen_at)}</span>`;
    const idEl = sum.querySelector(".insp-id");
    idEl.onclick = (e) => { e.preventDefault(); e.stopPropagation(); copyText(dev.id, idEl); };
    // Click the row (not the id) → draw this device's traces on the map.
    sum.addEventListener("click", () => showDeviceTraces(dev.id, details));
    details.appendChild(sum);

    const body = document.createElement("div");
    body.className = "insp-body";
    if (dev.lines.length) {
      body.innerHTML = dev.lines.map((l) =>
        `<div class="insp-line ${l.eligible ? "elig" : ""}">` +
        `${_esc(l.line_name)}: ${l.clean_trips}/${l.sessions} clean` +
        `${l.eligible ? " · ✓ can vote" : ""}</div>`).join("");
    }
    body.innerHTML += dev.sessions.length
      ? dev.sessions.map((s) =>
          `<div class="insp-sess"><span>${_esc(s.line_name || "(no line)")}</span>` +
          `<span class="muted">${s.points} pts · ${s.clean ? "clean" : _esc(s.processing_status)}` +
          `</span></div>`).join("")
      : `<div class="muted insp-sess">no traces recorded</div>`;
    details.appendChild(body);
    box.appendChild(details);
  }
  if (!devices.length) {
    box.innerHTML = `<p class="muted">No devices${eligibleOnly ? " eligible to vote" : ""}.</p>`;
  }
}

async function showDeviceTraces(deviceId, rowEl) {
  document.querySelectorAll(".insp-device.active")
    .forEach((d) => d.classList.remove("active"));
  if (rowEl) rowEl.classList.add("active");
  let fc;
  try { fc = await api(`/inspect/device-traces?device_id=${encodeURIComponent(deviceId)}`); }
  catch (e) { return; }
  _setDbGeo("insp-traces", fc,
    { "line-color": "#2d9cdb", "line-width": 3, "line-opacity": 0.9 });
  let bounds = null;
  for (const f of fc.features || []) {
    for (const c of f.geometry.coordinates) {
      bounds = bounds || new maplibregl.LngLatBounds(c, c);
      bounds.extend(c);
    }
  }
  if (bounds) map.fitBounds(bounds, { padding: 60, duration: 500 });
}

async function copyText(text, el) {
  try {
    await navigator.clipboard.writeText(text);
    const prev = el.textContent;
    el.textContent = "copied!";
    setTimeout(() => { el.textContent = prev; }, 900);
  } catch (e) { /* clipboard unavailable (insecure context) */ }
}

function _fmtTime(iso) {
  return iso ? iso.replace("T", " ").slice(0, 16) : "—";
}

function _esc(s) {
  return String(s).replace(/[&<>"]/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

/* ---------- fare zones overlay ---------- */

let _zoneLayerIds = [];

function _eachCoord(geom, cb) {
  const walk = (a) => { if (typeof a[0] === "number") cb(a); else a.forEach(walk); };
  walk(geom.coordinates);
}

async function toggleFareZones(show) {
  clearFareZones();
  if (!show) return;
  let fc;
  try { fc = await api("/fare-zones"); } catch (e) { return; }
  if (!fc.features || !fc.features.length) {
    _dbStatus("No fare zones yet — click 🏛 Populate municipalities first.");
    for (const id of ["inspect-zones", "db-zones"]) {
      const el = document.getElementById(id);
      if (el) el.checked = false;
    }
    return;
  }
  const src = "fare-zones-src";
  const apply = () => {
    map.addSource(src, { type: "geojson", data: fc });
    map.addLayer({ id: "fare-zones-fill", type: "fill", source: src,
      paint: { "fill-color": "#9b51e0", "fill-opacity": 0.07 } });
    map.addLayer({ id: "fare-zones-line", type: "line", source: src,
      paint: { "line-color": "#9b51e0", "line-width": 1, "line-opacity": 0.55 } });
    map.addLayer({ id: "fare-zones-label", type: "symbol", source: src,
      layout: { "text-field": ["get", "name"], "text-size": 11, "text-allow-overlap": false },
      paint: { "text-color": "#6b3fa0", "text-halo-color": "#fff", "text-halo-width": 1.4 } });
    _zoneLayerIds = ["fare-zones-fill", "fare-zones-line", "fare-zones-label"];
  };
  try { apply(); } catch (e) { map.once("idle", apply); }

  let bounds = null;
  for (const f of fc.features) {
    _eachCoord(f.geometry, (c) => {
      bounds = bounds || new maplibregl.LngLatBounds(c, c);
      bounds.extend(c);
    });
  }
  // Fit to the zones only when there's nothing else to anchor on (Inspect);
  // in Database mode keep the current line view and just overlay.
  if (bounds && !document.body.classList.contains("mode-database")) {
    map.fitBounds(bounds, { padding: 40, duration: 500 });
  }
}

function clearFareZones() {
  for (const id of _zoneLayerIds) if (map.getLayer(id)) map.removeLayer(id);
  if (map.getSource("fare-zones-src")) map.removeSource("fare-zones-src");
  _zoneLayerIds = [];
}

/* ---------- experiments ---------- */

let _groups = [];

async function loadExperimentGroups() {
  _groups = await api("/scenario-groups");
  const section = document.getElementById("experiments-section");
  section.hidden = _groups.length === 0;
  if (!_groups.length) return;
  const sel = document.getElementById("exp-group-select");
  const prev = sel.value;
  sel.innerHTML = "";
  for (const g of _groups) {
    const o = document.createElement("option");
    o.value = g.prefix;
    o.textContent = `${g.prefix} (${g.all.length})`;
    sel.appendChild(o);
  }
  if (prev && [...sel.options].some((o) => o.value === prev)) sel.value = prev;
}

function currentGroup() {
  const prefix = document.getElementById("exp-group-select").value;
  return _groups.find((g) => g.prefix === prefix);
}

const _sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function runAllInGroup() {
  const g = currentGroup();
  if (!g) return;
  const ids = g.all;   // the whole factorial
  if (!ids.length) return;
  const resp = await fetch("/api/runs/batch", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ scenario_ids: ids }),
  });
  if (!resp.ok) { _expStatus("Could not start the batch"); return; }
  const batch = await resp.json();
  // Persist so a page refresh keeps tracking it — the batch runs on the
  // server now, so refreshing no longer cancels it.
  localStorage.setItem("activeBatch", batch.id);
  _pollBatch(batch.id);
}

function _expStatus(text) {
  document.getElementById("exp-run-status").textContent = text;
}

async function _pollBatch(batchId) {
  for (;;) {
    let st;
    try { st = await api(`/runs/batch/${batchId}`); }
    catch { localStorage.removeItem("activeBatch"); return; }
    await refreshRuns(true);
    if (st.status === "done") {
      _expStatus(`Done — ran ${st.total}. Read the response surface in Runs ` +
                 `(cov % / ram per cell) to find the minimum.`);
      localStorage.removeItem("activeBatch");
      return;
    }
    _expStatus(`Running ${st.done + 1}/${st.total}${st.current ? ": " + st.current : ""} … (safe to refresh)`);
    await _sleep(2000);
  }
}

async function generateExperiments() {
  const id = document.getElementById("scenario-select").value;
  if (!id) return;
  if (!confirm(`Generate the reconstruction factorial from "${id}"?\n` +
               `Keeps your rider groups & ramales; sweeps the combination of ` +
               `traces × mean distance × position shape (~56 scenarios). ` +
               `Coverage & turnout are measured, not set.`))
    return;
  const resp = await fetch(
    `/api/scenarios/${encodeURIComponent(id)}/generate-experiments`,
    { method: "POST" });
  if (!resp.ok) { alert("Could not generate experiments"); return; }
  const { created } = await resp.json();
  await loadScenarios();
  await loadExperimentGroups();
  alert(`Created ${created.length} experiment scenarios (prefix "${id}_").`);
}

async function openManageScenarios() {
  const panel = document.getElementById("scenario-manage");
  const list = document.getElementById("scenario-manage-list");
  const scenarios = await api("/scenarios");
  list.innerHTML = "";
  for (const s of scenarios) {
    const row = document.createElement("label");
    row.className = "manage-row";
    row.innerHTML =
      `<input type="checkbox" value="${s.id}" /> <span>${s.name || s.id}</span>`;
    list.appendChild(row);
  }
  panel.hidden = false;
}

async function deleteSelectedScenarios() {
  const ids = [...document.querySelectorAll(
    "#scenario-manage-list input:checked")].map((c) => c.value);
  if (!ids.length) return;
  if (!confirm(`Delete ${ids.length} scenario(s)? This cannot be undone.`)) return;
  const resp = await fetch("/api/scenarios/batch-delete", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids }),
  });
  if (!resp.ok) { alert("Could not delete scenarios"); return; }
  await loadScenarios();
  await loadExperimentGroups();
  await openManageScenarios();   // refresh the checkbox list
}

/* ---------- measure tool: click points, read the distance ---------- */

let measuring = false;
const measurePoints = [];   // [lng, lat] in click order

function haversineM(a, b) {
  const R = 6371000, rad = Math.PI / 180;
  const dLat = (b[1] - a[1]) * rad, dLon = (b[0] - a[0]) * rad;
  const s = Math.sin(dLat / 2) ** 2 +
    Math.cos(a[1] * rad) * Math.cos(b[1] * rad) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(s));
}

function toggleMeasure() {
  measuring ? stopMeasure() : startMeasure();
}

function startMeasure() {
  measuring = true;
  measurePoints.length = 0;
  document.getElementById("measure-toggle").classList.add("active");
  map.getCanvas().style.cursor = "crosshair";
  map.on("click", measureClick);
  document.addEventListener("keydown", measureKey);
  renderMeasure();
}

function stopMeasure() {
  measuring = false;
  document.getElementById("measure-toggle").classList.remove("active");
  map.getCanvas().style.cursor = "";
  map.off("click", measureClick);
  document.removeEventListener("keydown", measureKey);
  if (map.getLayer("measure-line")) map.removeLayer("measure-line");
  if (map.getLayer("measure-points")) map.removeLayer("measure-points");
  if (map.getSource("measure-src")) map.removeSource("measure-src");
  document.getElementById("measure-readout").hidden = true;
}

function measureKey(event) {
  if (event.key === "Escape") stopMeasure();
  else if (event.key === "Backspace") { measurePoints.pop(); renderMeasure(); event.preventDefault(); }
}

function measureClick(event) {
  measurePoints.push([event.lngLat.lng, event.lngLat.lat]);
  renderMeasure();
}

function renderMeasure() {
  const features = [];
  if (measurePoints.length >= 2) {
    features.push({ type: "Feature", geometry: { type: "LineString", coordinates: measurePoints }, properties: {} });
  }
  for (const p of measurePoints) {
    features.push({ type: "Feature", geometry: { type: "Point", coordinates: p }, properties: {} });
  }
  const data = { type: "FeatureCollection", features };
  if (!map.getSource("measure-src")) {
    map.addSource("measure-src", { type: "geojson", data });
    map.addLayer({
      id: "measure-line", type: "line", source: "measure-src",
      filter: ["==", ["geometry-type"], "LineString"],
      paint: { "line-color": "#e3514f", "line-width": 2, "line-dasharray": [2, 1] },
    });
    map.addLayer({
      id: "measure-points", type: "circle", source: "measure-src",
      filter: ["==", ["geometry-type"], "Point"],
      paint: {
        "circle-radius": 4, "circle-color": "#e3514f",
        "circle-stroke-width": 1.5, "circle-stroke-color": "#ffffff",
      },
    });
  } else {
    map.getSource("measure-src").setData(data);
  }

  const readout = document.getElementById("measure-readout");
  readout.hidden = false;
  if (measurePoints.length < 2) {
    readout.innerHTML = `<span class="hint">Click two points on the map to measure.` +
      ` Backspace = undo · Esc = done</span>`;
    return;
  }
  let total = 0;
  for (let i = 1; i < measurePoints.length; i++) total += haversineM(measurePoints[i - 1], measurePoints[i]);
  const last = haversineM(measurePoints[measurePoints.length - 2], measurePoints[measurePoints.length - 1]);
  const fmt = (m) => m >= 1000 ? `${(m / 1000).toFixed(2)} km` : `${m.toFixed(1)} m`;
  const segs = measurePoints.length - 1;
  readout.innerHTML =
    `<div class="total">${fmt(total)}</div>` +
    (segs > 1 ? `<div class="hint">${segs} segments · last ${fmt(last)}</div>` : "") +
    `<div class="hint">Backspace = undo · Esc = done</div>`;
}

async function api(path) {
  const resp = await fetch(`/api${path}`);
  if (!resp.ok) throw new Error(`${path}: ${resp.status}`);
  return resp.json();
}

/* ---------- scenarios ---------- */

async function loadScenarios() {
  const scenarios = await api("/scenarios");
  const select = document.getElementById("scenario-select");
  select.innerHTML = "";
  for (const s of scenarios) {
    const option = document.createElement("option");
    option.value = s.id;
    option.textContent = s.name || s.id;
    option.dataset.description = s.description || "";
    select.appendChild(option);
  }
  const updateDescription = () => {
    const opt = select.selectedOptions[0];
    document.getElementById("scenario-description").textContent =
      opt ? opt.dataset.description : "";
  };
  select.onchange = updateDescription;
  updateDescription();
}

async function startRun() {
  const scenario = document.getElementById("scenario-select").value;
  const resp = await fetch("/api/runs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ scenario }),
  });
  const { run_id } = await resp.json();
  await refreshRuns();
  selectRun(run_id);
}

/* ---------- runs ---------- */

const _EXP_RUN = /^(.+?)_F\d+/;   // factorial cell: {base}_F001_…
let _runsSig = "";

function _runRow(run, base) {
  const li = document.createElement("li");
  li.dataset.runId = run.run_id;
  const status = run.failed ? "✗" : run.finished
    ? "✓" : `${run.completed_stages}/${run.total_stages}`;
  const cls = run.failed ? "status-failed" : run.finished
    ? "status-completed" : "status-running";
  // experiment runs show the factor (A1_n1) + key metrics inline.
  const label = base
    ? (run.scenario || run.run_id).replace(`${base}_`, "")
    : run.run_id;
  let metric = "";
  const s = run.summary;
  if (s) {
    const comp = s.completeness == null ? "—" : `${Math.round(s.completeness * 100)}%`;
    metric = `<span class="run-metric">cov ${comp} · ram ${s.ramales_found}/${s.ramales_expected}</span>`;
  }
  li.innerHTML =
    `<span class="run-name">${label}</span>${metric}<span class="${cls}">${status}</span>`;
  const del = document.createElement("button");
  del.className = "run-delete";
  del.textContent = "🗑";
  del.title = "Delete this run's data";
  del.onclick = (e) => { e.stopPropagation(); deleteRun(run.run_id, run.finished || run.failed); };
  li.appendChild(del);
  li.onclick = () => selectRun(run.run_id);
  if (run.run_id === currentRun) li.classList.add("active");
  return li;
}

async function refreshRuns(force = false) {
  const runs = await api("/runs");
  // Only re-render when something actually changed (so the list doesn't
  // flicker / collapse open groups while you read it).
  const sig = runs.map((r) =>
    `${r.run_id}:${r.completed_stages}:${r.finished}:${r.failed}`).join("|");
  if (!force && sig === _runsSig) return;
  _runsSig = sig;

  const list = document.getElementById("run-list");
  const openBases = new Set([...list.querySelectorAll("details.run-group[open]")]
    .map((d) => d.dataset.base));

  // Newest first. created_at is an ISO string → plain compare is chronological
  // (locale-independent, no punctuation quirks).
  const cmpDesc = (x, y) => (x < y ? 1 : x > y ? -1 : 0);
  const tOf = (r) => r.created_at || "";
  const latest = (g) => g.reduce((mx, r) => (tOf(r) > mx ? tOf(r) : mx), "");

  const groups = {};
  const standalone = [];
  for (const run of runs) {
    const m = (run.scenario || "").match(_EXP_RUN);
    if (m) (groups[m[1]] ||= []).push(run);
    else standalone.push(run);
  }

  // One timeline: each standalone run and each group is a block keyed by its
  // newest run, so the most recent thing is always at the top regardless of
  // whether it's a one-off run or part of a sweep.
  const blocks = [];
  standalone.sort((a, b) => cmpDesc(tOf(a), tOf(b)));
  for (const run of standalone.slice(0, 15)) {
    blocks.push({ time: tOf(run), el: _runRow(run) });
  }
  for (const [base, gruns] of Object.entries(groups)) {
    gruns.sort((a, b) => cmpDesc(tOf(a), tOf(b)));
    const det = document.createElement("details");
    det.className = "run-group";
    det.dataset.base = base;
    const running = gruns.some((r) => !r.finished && !r.failed);
    det.open = openBases.has(base) || running;
    const done = gruns.filter((r) => r.finished).length;
    const sum = document.createElement("summary");
    sum.innerHTML = `⚗ ${base} <span class="muted">(${done}/${gruns.length})</span>`;
    det.appendChild(sum);
    for (const run of gruns) det.appendChild(_runRow(run, base));
    blocks.push({ time: latest(gruns), el: det });
  }

  blocks.sort((a, b) => cmpDesc(a.time, b.time));
  list.innerHTML = "";
  for (const b of blocks) list.appendChild(b.el);
  document.getElementById("clear-runs").hidden = runs.length === 0;
}

async function deleteRun(runId, done) {
  const warning = done ? "" : "\nThis run looks unfinished — its process may still be writing.";
  if (!confirm(`Delete run ${runId} and all its artifacts?${warning}`)) return;
  await fetch(`/api/runs/${encodeURIComponent(runId)}`, { method: "DELETE" });
  if (runId === currentRun) clearCurrentRun();
  await refreshRuns();
}

async function deleteAllRuns() {
  if (!confirm("Delete ALL runs and their artifacts? Scenarios are kept.")) return;
  await fetch("/api/runs", { method: "DELETE" });
  clearCurrentRun();
  await refreshRuns();
}

function clearCurrentRun() {
  currentRun = null;
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
  for (const spec of STAGE_LAYERS) {
    for (const suffix of ["", "-inferred", "-points", "-label"]) {
      const id = `layer-${spec.file}${suffix}`;
      if (map.getLayer(id)) map.removeLayer(id);
    }
    const sourceId = `stage-${spec.file}`;
    if (map.getSource(sourceId)) map.removeSource(sourceId);
  }
  document.getElementById("stage-list").innerHTML = "";
  document.getElementById("layer-toggles").innerHTML = "";
  document.getElementById("metrics-content").innerHTML =
    '<span class="muted">run a scenario to see metrics</span>';
}

async function selectRun(runId) {
  currentRun = runId;
  document.querySelectorAll("#run-list li").forEach((li) =>
    li.classList.toggle("active", li.dataset.runId === runId));
  document.getElementById("export-csv").href = `/api/runs/${runId}/export.csv`;
  if (pollTimer) clearInterval(pollTimer);
  await renderRun(runId);
  // Poll while the run is still progressing.
  pollTimer = setInterval(async () => {
    const manifest = await api(`/runs/${runId}/manifest`).catch(() => null);
    if (!manifest) return;
    renderStages(manifest);
    if (manifest.finished_at || manifest.stages.some((s) => s.status === "failed")) {
      clearInterval(pollTimer);
      pollTimer = null;
      await renderRun(runId);
      await refreshRuns();
    }
  }, 1500);
}

async function renderRun(runId) {
  const manifest = await api(`/runs/${runId}/manifest`).catch(() => null);
  if (!manifest) return;
  renderStages(manifest);
  await renderLayers(runId);
  await renderMetrics(runId);
}

function renderStages(manifest) {
  const list = document.getElementById("stage-list");
  list.innerHTML = "";
  for (const stage of manifest.stages) {
    const li = document.createElement("li");
    const fmt = (v) => Array.isArray(v) ? v.join(",")
      : (v && typeof v === "object") ? Object.entries(v).map(([a, b]) => `${a}:${b}`).join(" ")
      : v;
    const stats = Object.entries(stage.stats || {})
      .slice(0, 2).map(([k, v]) => `${k}=${fmt(v)}`).join(" ");
    li.innerHTML = `<span>${stage.name}</span>
      <span class="muted">${stats}</span>
      <span class="status-${stage.status}">${stage.status}</span>`;
    if (stage.error) li.title = stage.error;
    list.appendChild(li);
  }
}

/* ---------- map layers ---------- */

function directionOffset() {
  return [
    "case",
    ["==", ["coalesce", ["get", "direction_group"], 0], 1], 3,
    -3,
  ];
}

function layerPaint(spec) {
  if (spec.color === "confidence") {
    // line-dasharray is not data-driven in MapLibre: inferred edges
    // get their own dashed layer (added in renderLayers).
    return {
      "line-color": [
        "case",
        ["==", ["get", "inferred"], true], "#f2c94c",
        ["interpolate", ["linear"], ["coalesce", ["get", "confidence"], 1],
          0, "#e3514f", 0.5, "#f2994a", 1, "#219653"],
      ],
      // Uniform width: route and edges draw at the same thickness so a
      // bridged stretch (route line with no edge over it) does not look
      // thinner. Bridges get their own optional dashed highlight layer.
      "line-width": spec.width,
      "line-opacity": spec.opacity,
      // Opposite directions get opposite perpendicular offsets so
      // they don't overpaint each other on shared streets.
      "line-offset": directionOffset(),
    };
  }
  if (spec.color === "votes") {
    return {
      "line-color": [
        "case",
        ["==", ["get", "status"], "CONFIRMED"], "#219653",
        [">", ["get", "votes_against"], ["get", "votes_for"]], "#e3514f",
        "#f2c94c",
      ],
      "line-width": spec.width,
      "line-opacity": spec.opacity,
    };
  }
  if (spec.color === "data") {
    // The runner writes a per-feature `color` property (rider-group
    // color on traces, per-ramal color on clusters, role color on
    // ground truth).
    return {
      "line-color": ["coalesce", ["get", "color"], spec.fallback],
      "line-width": spec.width,
      "line-opacity": spec.opacity,
    };
  }
  return { "line-color": spec.color, "line-width": spec.width, "line-opacity": spec.opacity };
}

async function renderLayers(runId) {
  const toggles = document.getElementById("layer-toggles");
  toggles.innerHTML = "";
  let bounds = null;

  for (const spec of STAGE_LAYERS) {
    const sourceId = `stage-${spec.file}`;
    const layerId = `layer-${spec.file}`;
    if (map.getLayer(layerId)) map.removeLayer(layerId);
    if (map.getLayer(`${layerId}-inferred`)) map.removeLayer(`${layerId}-inferred`);
    if (map.getLayer(`${layerId}-bridge-halo`)) map.removeLayer(`${layerId}-bridge-halo`);
    if (map.getLayer(`${layerId}-bridge`)) map.removeLayer(`${layerId}-bridge`);
    if (map.getLayer(`${layerId}-points`)) map.removeLayer(`${layerId}-points`);
    if (map.getSource(sourceId)) map.removeSource(sourceId);

    let data;
    try {
      const resp = await fetch(`/api/runs/${runId}/artifacts/${spec.file}`);
      if (!resp.ok) continue;
      data = await resp.json();
    } catch { continue; }
    if (!data.features || data.features.length === 0) continue;

    map.addSource(sourceId, { type: "geojson", data });
    if (spec.circle) {
      map.addLayer({
        id: layerId, type: "circle", source: sourceId,
        paint: {
          "circle-radius": 4,
          "circle-color": spec.color,
          "circle-opacity": spec.opacity,
          "circle-stroke-width": 1,
          "circle-stroke-color": "#16181d",
        },
      });
      if (spec.labelField) {
        map.addLayer({
          id: `${layerId}-label`, type: "symbol", source: sourceId,
          filter: ["==", ["get", "kind"], "fare_alighting"],   // label at the end
          layout: {
            "text-field": ["concat", "Bs ",
              ["number-format", ["get", spec.labelField],
                { "min-fraction-digits": 2, "max-fraction-digits": 2 }]],
            "text-size": 13, "text-offset": [0, 1], "text-anchor": "top",
            "text-allow-overlap": false,
          },
          paint: {
            "text-color": spec.color, "text-halo-color": "#16181d",
            "text-halo-width": 1.6,
          },
        });
      }
    } else {
      const layer = {
        id: layerId, type: "line", source: sourceId,
        layout: { "line-cap": "round", "line-join": "round" },
        paint: layerPaint(spec),
      };
      if (spec.color === "confidence") {
        // Main line draws real edges + the welded route, but not the
        // bridge-highlight features (those have their own layer).
        layer.filter = ["all",
          ["!=", ["get", "inferred"], true],
          ["!=", ["get", "kind"], "bridge"]];
      }
      if (spec.lineFilter) layer.filter = spec.lineFilter;
      map.addLayer(layer);
      if (spec.pointsFilter) {
        // Companion dots: every GPS fix of every trace.
        map.addLayer({
          id: `${layerId}-points`, type: "circle", source: sourceId,
          filter: spec.pointsFilter,
          paint: {
            "circle-radius": 2.5,
            "circle-color": ["coalesce", ["get", "color"], spec.fallback || "#f2994a"],
            "circle-opacity": Math.min(1, spec.opacity + 0.3),
            "circle-stroke-width": 0.5,
            "circle-stroke-color": "#ffffff",
          },
        });
      }
      if (spec.color === "confidence") {
        // Companion dashed layer for inferred (gap-bridged) edges.
        map.addLayer({
          id: `${layerId}-inferred`, type: "line", source: sourceId,
          filter: ["==", ["get", "inferred"], true],
          paint: {
            "line-color": "#f2c94c",
            "line-width": spec.width,
            "line-opacity": spec.opacity,
            "line-dasharray": [2, 2],
            "line-offset": directionOffset(),
          },
        });
        // Optional bridge highlight (off by default): inferred connector
        // stretches (weld / straight-bridge / trace-stitch / de-drift).
        // A thick translucent halo makes the location obvious, with a
        // crisp dashed line on top marking it as inferred.
        map.addLayer({
          id: `${layerId}-bridge-halo`, type: "line", source: sourceId,
          filter: ["==", ["get", "kind"], "bridge"],
          layout: { "line-cap": "round", "line-join": "round", visibility: "none" },
          paint: {
            "line-color": "#2d9cdb",
            "line-width": spec.width + 8,
            "line-opacity": 0.25,
            "line-offset": directionOffset(),
          },
        });
        map.addLayer({
          id: `${layerId}-bridge`, type: "line", source: sourceId,
          filter: ["==", ["get", "kind"], "bridge"],
          layout: { "line-cap": "round", "line-join": "round", visibility: "none" },
          paint: {
            "line-color": "#2d9cdb",
            "line-width": spec.width + 1,
            "line-opacity": 0.95,
            "line-dasharray": [1.5, 1.5],
            "line-offset": directionOffset(),
          },
        });
      }
    }
    if (spec.off) {
      for (const id of [layerId, `${layerId}-inferred`, `${layerId}-points`]) {
        if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", "none");
      }
    }

    for (const f of data.features) {
      const coords = f.geometry.type === "Point"
        ? [f.geometry.coordinates]
        : f.geometry.coordinates;
      for (const c of coords) {
        bounds = bounds || new maplibregl.LngLatBounds(c, c);
        bounds.extend(c);
      }
    }

    const row = document.createElement("div");
    row.className = "layer-row";
    const swatchColor = typeof spec.color === "string" && spec.color.startsWith("#")
      ? spec.color : "#6fcf97";
    row.innerHTML = `
      <input type="checkbox" ${spec.off ? "" : "checked"} />
      <span class="swatch" style="background:${swatchColor}"></span>
      <span>${spec.label}</span>
      <input type="range" min="0" max="100" value="${spec.opacity * 100}" />`;
    const [checkbox, , , slider] = row.children;
    const siblingIds = [layerId, `${layerId}-inferred`, `${layerId}-points`]
      .filter((id) => map.getLayer(id));
    checkbox.onchange = () => siblingIds.forEach((id) =>
      map.setLayoutProperty(id, "visibility", checkbox.checked ? "visible" : "none"));
    slider.oninput = () => {
      siblingIds.forEach((id) => {
        const prop = map.getLayer(id).type === "circle" ? "circle-opacity" : "line-opacity";
        map.setPaintProperty(id, prop, Number(slider.value) / 100);
      });
    };
    toggles.appendChild(row);

    if (spec.color === "confidence") {
      const hasBridges = data.features.some((f) => (f.properties || {}).kind === "bridge");
      if (hasBridges && map.getLayer(`${layerId}-bridge`)) {
        const brow = document.createElement("div");
        brow.className = "layer-row ramal-row";
        brow.innerHTML = `
          <input type="checkbox" />
          <span class="swatch" style="background:#2d9cdb"></span>
          <span>Highlight bridges</span>`;
        const bcheck = brow.children[0];
        bcheck.onchange = () => {
          const vis = bcheck.checked ? "visible" : "none";
          for (const id of [`${layerId}-bridge-halo`, `${layerId}-bridge`]) {
            if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", vis);
          }
        };
        toggles.appendChild(brow);
      }
      const noBridge = ["all",
        ["!=", ["get", "inferred"], true], ["!=", ["get", "kind"], "bridge"]];
      renderRamalToggles(toggles, data, [
        { id: layerId, baseFilter: noBridge },
        { id: `${layerId}-inferred`, baseFilter: ["==", ["get", "inferred"], true] },
        { id: `${layerId}-bridge-halo`, baseFilter: ["==", ["get", "kind"], "bridge"] },
        { id: `${layerId}-bridge`, baseFilter: ["==", ["get", "kind"], "bridge"] },
      ]);
    } else if (spec.ramalToggles) {
      renderRamalToggles(toggles, data, [{ id: layerId, baseFilter: null }]);
    }
  }

  if (bounds) map.fitBounds(bounds, { padding: 48, duration: 600 });
}

/* Per-ramal visibility: one checkbox per reconstructed variant,
   filtering the given layers (consensus edges/route, or the ramal
   clusters). Each layerSpec is {id, baseFilter} — baseFilter is the
   layer's own static filter (e.g. inferred vs not) to AND with. */
function renderRamalToggles(container, data, layerSpecs) {
  const ramals = new Map();   // key -> {label, dir}
  for (const f of data.features) {
    const p = f.properties || {};
    if (p.ramal_label === undefined) continue;
    const dir = p.direction_group ?? 0;
    ramals.set(`${p.ramal_label}|${dir}`, { label: p.ramal_label, dir });
  }
  if (ramals.size <= 1) return;

  const hidden = new Set();
  const applyFilters = () => {
    const visible = ["!", ["in",
      ["concat", ["get", "ramal_label"], "|",
        ["to-string", ["coalesce", ["get", "direction_group"], 0]]],
      ["literal", Array.from(hidden)],
    ]];
    for (const { id, baseFilter } of layerSpecs) {
      if (!map.getLayer(id)) continue;
      map.setFilter(id, baseFilter ? ["all", baseFilter, visible] : visible);
    }
  };

  for (const [key, info] of [...ramals.entries()].sort()) {
    const row = document.createElement("div");
    row.className = "layer-row ramal-row";
    const dirLabel = info.label === "unassigned" ? "" : ` · dir ${info.dir}`;
    row.innerHTML = `
      <input type="checkbox" checked />
      <span class="muted">↳</span>
      <span>${info.label}${dirLabel}</span>`;
    const checkbox = row.children[0];
    checkbox.onchange = () => {
      if (checkbox.checked) hidden.delete(key);
      else hidden.add(key);
      applyFilters();
    };
    container.appendChild(row);
  }
}

/* ---------- metrics ---------- */

const METRIC_ROWS = [
  ["frechet_m", "Fréchet (strict)", "m", (v) => v < 60],
  ["frechet_overlap_m", "Fréchet (overlap)", "m", (v) => v < 60],
  ["start_truncation_m", "Start truncation", "m", (v) => v < 300],
  ["end_truncation_m", "End truncation", "m", (v) => v < 300],
  ["coverage", "Coverage", "", (v) => v > 0.9],
  ["edge_precision", "Edge precision", "", (v) => v > 0.9],
  ["edge_recall", "Edge recall", "", (v) => v > 0.85],
  ["max_junction_gap_m", "Max junction gap", "m", (v) => v <= 15],
  ["consensus_edges", "Edges", "", null],
  ["inferred_edges", "Inferred edges", "", null],
];

async function renderMetrics(runId) {
  const container = document.getElementById("metrics-content");
  let metrics;
  try {
    metrics = await api(`/runs/${runId}/metrics`);
  } catch {
    container.textContent = "metrics not available yet";
    return;
  }
  container.innerHTML = "";
  // metrics.json is now {summary, routes, initial}; older runs are a bare array.
  const routes = Array.isArray(metrics) ? metrics : (metrics.routes || []);
  const summary = Array.isArray(metrics) ? null : metrics.summary;
  const initial = Array.isArray(metrics) ? null : metrics.initial;

  if (initial) {
    const block = document.createElement("div");
    block.className = "route-block";
    const total = initial.traces_total || 0;
    const matchPct = total ? Math.round((initial.traces_matched / total) * 100) : 0;
    const rows = (initial.per_route || []).map((r) =>
      `<tr><td>${r.route} <span class="muted">(${r.role})</span></td>` +
      `<td>${r.matched} / ${r.traces}</td></tr>`).join("");
    block.innerHTML = `<h3>Initial data</h3><table class="metrics">
      <tr><td>Traces (matched / total)</td><td>${initial.traces_matched} / ${total} · ${matchPct}%</td></tr>
      ${rows ? `<tr><td colspan="2" class="muted">Per ramal — matched / assigned</td></tr>${rows}` : ""}</table>`;
    container.appendChild(block);
  }
  if (summary) {
    const pct = (v) => (v == null ? "—" : `${Math.round(v * 100)}%`);
    const m = (v) => (v == null ? "—" : `${Math.round(v)} m`);
    const block = document.createElement("div");
    block.className = "route-block";
    const compCls = summary.completeness == null ? ""
      : summary.completeness >= 0.95 ? "metric-good" : "metric-bad";
    const ramCls = summary.ramales_found >= summary.ramales_expected
      ? "metric-good" : "metric-bad";
    block.innerHTML = `<h3>Summary</h3><table class="metrics">
      <tr><td>Completeness (of rider envelope)</td><td class="${compCls}">${pct(summary.completeness)}</td></tr>
      <tr><td>Coverage envelope (of full route)</td><td>${pct(summary.coverage_envelope)}</td></tr>
      <tr><td>Per-trace distance (median / mean ± std)</td><td>${m(summary.trace_distance_median_m)} / ${m(summary.trace_distance_mean_m)} ± ${m(summary.trace_distance_std_m)}</td></tr>
      <tr><td>Ramales found / expected</td><td class="${ramCls}">${summary.ramales_found} / ${summary.ramales_expected}</td></tr>
      <tr><td>Reconstructed routes</td><td>${summary.reconstructed_routes}</td></tr>
      ${summary.voters_requested ? `<tr><td>Voters (voted / requested) · turnout</td><td>${summary.voters_voted} / ${summary.voters_requested} · ${pct(summary.turnout)}</td></tr>` : ""}
      ${summary.votes_total ? `<tr><td>Votes (for / against)</td><td>${summary.votes_total} · ${summary.votes_for} ✓ / ${summary.votes_against} ✗</td></tr>` : ""}</table>`;
    container.appendChild(block);
  }
  for (const route of routes) {
    const block = document.createElement("div");
    block.className = "route-block";
    const status = route.route_status || "PENDING";
    const dir = route.direction_group !== undefined ? ` · dir ${route.direction_group}` : "";
    block.innerHTML = `<h3>${route.ramal_label}<span class="muted">${dir}</span>
      <span class="${status === "CONFIRMED" ? "metric-good" : "muted"}">${status}</span></h3>`;
    const table = document.createElement("table");
    table.className = "metrics";
    for (const [key, label, unit, good] of METRIC_ROWS) {
      const value = route[key];
      if (value === null || value === undefined) continue;
      const cls = good === null ? "" : good(value) ? "metric-good" : "metric-bad";
      const text = typeof value === "number" && !Number.isInteger(value)
        ? value.toFixed(unit === "m" ? 1 : 3) : value;
      table.innerHTML += `<tr><td>${label}</td><td class="${cls}">${text}${unit}</td></tr>`;
    }
    block.appendChild(table);
    container.appendChild(block);
  }
}

/* ---------- export ---------- */

function exportPng() {
  const link = document.createElement("a");
  link.download = `${currentRun || "simlab"}.png`;
  link.href = map.getCanvas().toDataURL("image/png");
  link.click();
}
