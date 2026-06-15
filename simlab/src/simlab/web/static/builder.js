/* Scenario builder: multiple base routes (main / ramal / detour) from
   the catalog, uploads, or drawn directly on the map; rider groups
   assigned to a route with travel window + their own fare areas — all
   previewed live. Saves through PUT /api/scenarios/{id}. */

const PERSONA_COLORS = ["#e3514f", "#2d9cdb", "#6fcf97", "#f2c94c", "#bb6bd9", "#f2994a"];
const FARE_COLORS = ["#9b51e0", "#219653", "#eb5757", "#2f80ed"];
const ROLE_COLORS = { main: "#9aa0a8", ramal: "#2d9cdb", detour: "#f2c94c" };

let builderConfig = null;
let routeCatalog = [];
let routeCoordsCache = {};   // path -> [[lon,lat],...]
let previewTimer = null;
let drawing = null;          // {coords: [...]} while draw mode active
const hiddenGroups = new Set();   // group names hidden on the map (viz only)

function applyTraceVisibility() {
  // Re-render both the traces and the persona-owned builder features (window,
  // fare) from cache with the current eye-toggle filter — instant, and
  // independent of the async refreshPreview rebuild.
  _renderSimTraces();
  if (_lastBuilderFeatures.length && map.getSource("builder-src")) {
    const visible = _lastBuilderFeatures.filter(
      (f) => !hiddenGroups.has(f.properties.persona));
    map.getSource("builder-src").setData({ type: "FeatureCollection", features: visible });
  }
}

document.getElementById("new-scenario").onclick = () => openBuilder(null);
document.getElementById("edit-scenario").onclick = () =>
  openBuilder(document.getElementById("scenario-select").value);
document.getElementById("duplicate-scenario").onclick = duplicateScenario;

async function duplicateScenario() {
  const id = document.getElementById("scenario-select").value;
  if (!id) return;
  const resp = await fetch(`/api/scenarios/${encodeURIComponent(id)}/duplicate`,
    { method: "POST" });
  if (!resp.ok) { alert("Could not duplicate scenario"); return; }
  const { id: copy } = await resp.json();
  await loadScenarios();
  const select = document.getElementById("scenario-select");
  select.value = copy;
  select.dispatchEvent(new Event("change"));
  openBuilder(copy);   // open the copy for editing right away
}
document.getElementById("builder-close").onclick = closeBuilder;
document.getElementById("builder-save").onclick = saveScenario;

/* ---------- open / close ---------- */

async function openBuilder(scenarioId) {
  routeCatalog = await api("/routes");
  builderConfig = scenarioId
    ? await api(`/scenarios/${scenarioId}`)
    : defaultScenario();
  normalizeScenario(builderConfig);
  hiddenGroups.clear();   // fresh map-visibility state per scenario
  document.getElementById("metrics-panel").hidden = true;
  document.getElementById("builder-panel").hidden = false;
  renderBuilderForm();
  await refreshPreview(true);
  scheduleTracePreview();
}

function closeBuilder() {
  cancelDrawing();
  document.getElementById("builder-panel").hidden = true;
  document.getElementById("metrics-panel").hidden = false;
  clearBuilderLayers();
  clearSimTraces();
  builderConfig = null;
}

function defaultScenario() {
  return {
    name: "new_scenario",
    description: "",
    routes: [{
      name: "main",
      path: routeCatalog.length ? routeCatalog[0].path : "",
      role: "main", replaces: null, from_day: 0, to_day: null, fraction_of_trips: 1.0,
    }],
    seed: 42, sim_days: 21, vote_day: 21,
    personas: [defaultPersona("commuter")],
    speed: {}, noise: {}, votes: {},
    fares: { base_fare_bob: 2.4, misreport_prob: 0.05 },
    search_radius_m: 40,
    min_match_quality: 0.6,
  };
}

function defaultPersona(name, index = 0) {
  return {
    name, traces: 3, voters: 0,
    route: null, travel_window: [0.0, 1.0],
    mean_trip_distance_m: null, trip_distance_std_m: 0,
    trip_position_weights: [], vote_position_weights: [],
    noise_multiplier: 1.0,
    fare_report_prob: 0.3, sampling_rate_s: 2.0, fare_areas: [],
    color: PERSONA_COLORS[index % PERSONA_COLORS.length],
  };
}

function personaColor(persona, index) {
  return persona.color || PERSONA_COLORS[index % PERSONA_COLORS.length];
}

function normalizeScenario(cfg) {
  if (!cfg.routes || !cfg.routes.length) {
    cfg.routes = cfg.route_geojson
      ? [{ name: "main", path: cfg.route_geojson, role: "main" }]
      : [];
  }
  delete cfg.route_geojson;
  cfg.personas = cfg.personas || [];
  for (const persona of cfg.personas) persona.fare_areas = persona.fare_areas || [];
  cfg.noise = cfg.noise || {};
  cfg.speed = cfg.speed || {};
  cfg.votes = cfg.votes || {};
  cfg.fares = cfg.fares || {};
}

function rideableRoutes() {
  return (builderConfig.routes || []).filter((r) => r.role !== "detour");
}

/* ---------- form rendering ---------- */

function renderBuilderForm() {
  const root = document.getElementById("builder-form");
  root.innerHTML = "";
  const cfg = builderConfig;

  const previewHint = document.createElement("p");
  previewHint.className = "muted";
  previewHint.id = "trace-preview-hint";
  previewHint.textContent = "Live preview: sample traces update as you edit.";
  root.appendChild(previewHint);

  root.appendChild(section("General", (body) => {
    body.appendChild(wideText("Scenario id (file name)", cfg, "name"));
    body.appendChild(wideTextarea("Description", cfg, "description"));
    const grid = fieldGrid();
    grid.appendChild(num("Random seed", cfg, "seed", 1));
    grid.appendChild(num("Simulated days", cfg, "sim_days", 1));
    grid.appendChild(num("Vote day", cfg, "vote_day", 1));
    body.appendChild(grid);
  }));

  root.appendChild(section("Base routes", (body) => {
    cfg.routes.forEach((route, index) => {
      const color = ROLE_COLORS[route.role] || "#9aa0a8";
      const title = route.role === "detour"
        ? `${route.name} — detour of ${route.replaces ?? "?"}`
        : route.name || `route ${index + 1}`;
      const card = itemCard(title, color, () => {
        const removed = cfg.routes.splice(index, 1)[0];
        // Detours of the removed route and groups riding it fall back
        // to the first remaining rideable route.
        const fallback = rideableRoutes()[0]?.name ?? null;
        for (const other of cfg.routes) {
          if (other.role === "detour" && other.replaces === removed.name) {
            other.replaces = fallback;
          }
        }
        for (const persona of cfg.personas) {
          if (persona.route === removed.name) persona.route = fallback;
        }
        renderBuilderForm();
        schedulePreview();
      });

      // Renaming a route follows through to every reference: detours
      // of it and rider groups assigned to it.
      const nameField = document.createElement("div");
      nameField.className = "field-wide";
      const nameInput = document.createElement("input");
      nameInput.type = "text";
      nameInput.placeholder = "Route name (referenced by groups & detours)";
      nameInput.value = route.name ?? "";
      nameInput.onchange = () => {
        const oldName = route.name;
        route.name = nameInput.value;
        for (const other of cfg.routes) {
          if (other.role === "detour" && other.replaces === oldName) {
            other.replaces = route.name;
          }
        }
        for (const persona of cfg.personas) {
          if (persona.route === oldName) persona.route = route.name;
        }
        renderBuilderForm();
        schedulePreview();
      };
      nameField.appendChild(nameInput);
      card.appendChild(nameField);

      const geoSelect = document.createElement("select");
      for (const entry of routeCatalog) {
        const option = document.createElement("option");
        option.value = entry.path;
        option.textContent = `${entry.name} (${entry.source})`;
        if (entry.path === route.path) option.selected = true;
        geoSelect.appendChild(option);
      }
      geoSelect.onchange = () => { route.path = geoSelect.value; schedulePreview(); };
      card.appendChild(geoSelect);

      const roleSelect = document.createElement("select");
      for (const role of ["main", "ramal", "detour"]) {
        const option = document.createElement("option");
        option.value = role;
        option.textContent = role;
        if (role === route.role) option.selected = true;
        roleSelect.appendChild(option);
      }
      roleSelect.style.marginTop = "6px";
      roleSelect.onchange = () => {
        route.role = roleSelect.value;
        renderBuilderForm();
        schedulePreview();
      };
      card.appendChild(roleSelect);

      if (route.role === "detour") {
        const rideable = rideableRoutes();
        // Self-heal a stale link (renamed/removed target).
        if (!rideable.some((other) => other.name === route.replaces)) {
          route.replaces = rideable[0]?.name ?? null;
        }
        const grid = fieldGrid();
        const replaces = document.createElement("select");
        for (const other of rideable) {
          const option = document.createElement("option");
          option.value = other.name;
          option.textContent = `${other.name} (${other.role})`;
          if (other.name === route.replaces) option.selected = true;
          replaces.appendChild(option);
        }
        replaces.onchange = () => {
          route.replaces = replaces.value;
          renderBuilderForm();   // card title shows "detour of <name>"
          schedulePreview();
        };
        const label = document.createElement("label");
        label.textContent = "Detour of";
        grid.appendChild(label);
        grid.appendChild(replaces);
        grid.appendChild(num("Active from day", route, "from_day", 1, 0));
        grid.appendChild(num("Active to day", route, "to_day", 1, cfg.sim_days));
        grid.appendChild(num("Fraction of trips", route, "fraction_of_trips", 0.1, 1.0));
        card.appendChild(grid);
      }
      body.appendChild(card);
    });

    body.appendChild(addButton("+ Add base route", () => {
      cfg.routes.push({
        name: `route_${cfg.routes.length + 1}`,
        path: routeCatalog.length ? routeCatalog[0].path : "",
        role: cfg.routes.length ? "ramal" : "main",
        replaces: null, from_day: 0, to_day: null, fraction_of_trips: 1.0,
      });
      renderBuilderForm();
      schedulePreview();
    }));

    const upload = document.createElement("input");
    upload.type = "file";
    upload.accept = ".geojson,.json";
    upload.style.marginTop = "6px";
    upload.onchange = () => uploadRouteFile(upload);
    body.appendChild(upload);

    body.appendChild(addButton("✏ Draw new route on map", startDrawing));
    const hint = document.createElement("p");
    hint.className = "muted";
    hint.id = "draw-hint";
    body.appendChild(hint);
  }));

  root.appendChild(section("GPS noise", (body) => {
    const n = cfg.noise;
    const layers = [
      ["Gaussian (receiver)", "gaussian_enabled", true,
        [["σ (m)", "gaussian_sigma_m", 0.5, 3.0],
         ["Correlation time (s, 0=white)", "gps_correlation_time_s", 1, 20]]],
      ["Cross-track (multipath)", "perpendicular_enabled", true,
        [["σ (m)", "perpendicular_sigma_m", 0.5, 1.5]]],
      ["Zigzag", "zigzag_enabled", false,
        [["Amplitude (m)", "zigzag_amplitude_m", 0.5, 1.5],
         ["Period (points)", "zigzag_period_points", 1, 8]]],
      ["Jumps", "jumps_enabled", false,
        [["Probability", "jump_probability", 0.01, 0.01],
         ["Distance (m)", "jump_distance_m", 5, 30]]],
      ["Missing points", "missing_enabled", true,
        [["Probability", "missing_probability", 0.01, 0.02]]],
      ["Biased drift", "biased_drift_enabled", false,
        [["Drift (m/pt)", "biased_drift_m_per_point", 0.01, 0.05],
         ["Bearing (deg)", "biased_drift_bearing_deg", 5, 70]]],
      ["Lateral drift", "lateral_drift_enabled", false,
        [["Total (m)", "lateral_drift_total_m", 0.5, 3.0]]],
      ["Timestamp jitter", "timestamp_jitter_enabled", true,
        [["σ (s)", "timestamp_jitter_s", 0.05, 0.15]]],
    ];
    for (const [label, enabledKey, enabledDefault, params] of layers) {
      const grid = fieldGrid();
      grid.appendChild(boolField(label, n, enabledKey, enabledDefault));
      if (n[enabledKey] ?? enabledDefault) {
        for (const [pLabel, pKey, step, fallback] of params) {
          grid.appendChild(num(`· ${pLabel}`, n, pKey, step, fallback));
        }
      }
      body.appendChild(grid);
    }
  }));

  root.appendChild(section("Bus speed & stops", (body) => {
    const grid = fieldGrid();
    grid.appendChild(num("Cruise speed (m/s)", cfg.speed, "base_speed_mps", 0.5, 8.0));
    grid.appendChild(num("Speed stddev (m/s)", cfg.speed, "speed_stddev_mps", 0.1, 1.5));
    grid.appendChild(num("Stop spacing (m)", cfg.speed, "stop_spacing_m", 50, 400));
    grid.appendChild(num("Dwell min (s)", cfg.speed, "stop_dwell_min_s", 1, 8));
    grid.appendChild(num("Dwell max (s)", cfg.speed, "stop_dwell_max_s", 1, 45));
    grid.appendChild(num("Intersection spacing (m)", cfg.speed, "intersection_spacing_m", 50, 600));
    body.appendChild(grid);
  }));

  root.appendChild(section("Rider groups (personas)", (body) => {
    cfg.personas.forEach((persona, index) => {
      const color = personaColor(persona, index);
      const card = itemCard(persona.name || "group", color, () => {
        cfg.personas.splice(index, 1);
        renderBuilderForm();
        schedulePreview();
      });
      // Map-visibility toggle (preview only — does NOT disable the group).
      const eye = document.createElement("button");
      eye.className = "toggle-vis";
      const setEye = () => {
        const hidden = hiddenGroups.has(persona.name);
        eye.textContent = hidden ? "🙈" : "👁";
        eye.title = hidden
          ? "Hidden on map (still simulated) — click to show"
          : "Shown on map — click to hide (still simulated)";
      };
      eye.onclick = () => {
        if (hiddenGroups.has(persona.name)) hiddenGroups.delete(persona.name);
        else hiddenGroups.add(persona.name);
        setEye();
        applyTraceVisibility();   // traces
        refreshPreview();         // travel-area window + fare lines
      };
      setEye();
      const head = card.querySelector(".card-title");
      head.insertBefore(eye, head.querySelector(".remove-item"));
      card.appendChild(wideText("Group name", persona, "name"));

      // Trace color on the map for this group.
      const colorRow = document.createElement("div");
      colorRow.className = "field-grid";
      const colorLabel = document.createElement("label");
      colorLabel.textContent = "Trace color";
      const colorInput = document.createElement("input");
      colorInput.type = "color";
      colorInput.value = color;
      colorInput.onchange = () => {
        persona.color = colorInput.value;
        renderBuilderForm();
        schedulePreview();
      };
      colorRow.appendChild(colorLabel);
      colorRow.appendChild(colorInput);
      card.appendChild(colorRow);

      const rideable = rideableRoutes();
      // Self-heal a stale assignment (renamed/removed route).
      if (!rideable.some((route) => route.name === persona.route)) {
        persona.route = rideable[0]?.name ?? null;
      }
      const routeSelect = document.createElement("select");
      for (const route of rideable) {
        const option = document.createElement("option");
        option.value = route.name;
        option.textContent = `rides: ${route.name} (${route.role})`;
        if (route.name === persona.route) option.selected = true;
        routeSelect.appendChild(option);
      }
      routeSelect.onchange = () => { persona.route = routeSelect.value; schedulePreview(); };
      card.appendChild(routeSelect);

      const grid = fieldGrid();
      grid.appendChild(num("Traces", persona, "traces", 1, 1));
      grid.appendChild(num("Voters", persona, "voters", 1, 0));
      grid.appendChild(selectField("Direction", persona, "direction",
        [["forward", "Forward"], ["backward", "Backward"]], "forward"));
      grid.appendChild(num("Travel area start %", persona.travel_window, 0, 1, 0, percentField));
      grid.appendChild(num("Travel area end %", persona.travel_window, 1, 1, 100, percentField));
      grid.appendChild(num("Avg trip distance (m, 0=full zone)", persona, "mean_trip_distance_m", 50, 0));
      grid.appendChild(num("Trip distance std (m)", persona, "trip_distance_std_m", 50, 0));
      grid.appendChild(num("GPS noise ×", persona, "noise_multiplier", 0.1));
      grid.appendChild(num("Sampling rate (s)", persona, "sampling_rate_s", 0.5));
      grid.appendChild(num("P(fare report)", persona, "fare_report_prob", 0.1));
      card.appendChild(grid);
      card.appendChild(positionEditor(persona, "trip_position_weights",
        "Trace position along zone — drag the bars (start → end)", "#56ccf2"));
      card.appendChild(positionEditor(persona, "vote_position_weights",
        "Voter position — where regulars concentrate (only if Voters > 0)",
        "#f2c94c"));

      const faresTitle = document.createElement("div");
      faresTitle.className = "muted";
      faresTitle.style.margin = "8px 0 4px";
      faresTitle.textContent = "Fare areas (along this group's route)";
      card.appendChild(faresTitle);
      persona.fare_areas.forEach((area, areaIndex) => {
        const areaColor = FARE_COLORS[areaIndex % FARE_COLORS.length];
        const areaCard = itemCard(area.name || `area ${areaIndex + 1}`, areaColor, () => {
          persona.fare_areas.splice(areaIndex, 1);
          renderBuilderForm();
          schedulePreview();
        });
        areaCard.appendChild(wideText("Area name", area, "name"));
        const areaGrid = fieldGrid();
        areaGrid.appendChild(num("Start %", area, "start_fraction", 1, 0, percentField));
        areaGrid.appendChild(num("End %", area, "end_fraction", 1, 100, percentField));
        areaGrid.appendChild(num("Fare (BOB)", area, "amount_bob", 0.1));
        areaCard.appendChild(areaGrid);
        card.appendChild(areaCard);
      });
      card.appendChild(addButton("+ Add fare area", () => {
        persona.fare_areas.push({
          name: `area_${persona.fare_areas.length + 1}`,
          start_fraction: 0.0, end_fraction: 0.5, amount_bob: 2.4,
        });
        renderBuilderForm();
        schedulePreview();
      }));

      body.appendChild(card);
    });
    body.appendChild(addButton("+ Add rider group", () => {
      cfg.personas.push(defaultPersona(`group_${cfg.personas.length + 1}`, cfg.personas.length));
      renderBuilderForm();
      schedulePreview();
    }));
  }));

  root.appendChild(section("Fares (global)", (body) => {
    const grid = fieldGrid();
    grid.appendChild(num("Base fare (BOB)", cfg.fares, "base_fare_bob", 0.1, 2.4));
    grid.appendChild(num("Misreport prob", cfg.fares, "misreport_prob", 0.01, 0.05));
    body.appendChild(grid);
  }));

  root.appendChild(section("Voting rules", (body) => {
    const grid = fieldGrid();
    grid.appendChild(num("Min trips to vote", cfg.votes, "eligibility_min_trips", 1, 3));
    grid.appendChild(num("Overlap tolerance (m)", cfg.votes, "overlap_tolerance_m", 5, 50));
    grid.appendChild(num("P(approve true edge)", cfg.votes, "approve_prob_true_edge", 0.01, 0.92));
    grid.appendChild(num("P(approve spurious)", cfg.votes, "approve_prob_spurious_edge", 0.01, 0.15));
    grid.appendChild(num("Edge min votes", cfg.votes, "edge_min_votes", 1, 3));
    grid.appendChild(num("Edge approval ≥", cfg.votes, "edge_approval_threshold", 0.05, 0.6));
    grid.appendChild(num("Route approval ≥", cfg.votes, "route_approval_threshold", 0.05, 0.8));
    body.appendChild(grid);
  }));

  root.appendChild(section("Reconstruction", (body) => {
    const grid = fieldGrid();
    grid.appendChild(selectField("Strategy", cfg, "strategy",
      [["support_graph", "Support graph (native)"], ["edge_overlap", "Edge overlap (geodata)"]],
      "support_graph"));
    grid.appendChild(num("Match search radius (m)", cfg, "search_radius_m", 5, 40));
    grid.appendChild(num("Min match quality", cfg, "min_match_quality", 0.05, 0.6));
    grid.appendChild(num("GPS accuracy (m, 0 = auto)", cfg, "gps_accuracy_m", 1, 0));
    grid.appendChild(num("Weld gap up to (m)", cfg, "weld_gap_m", 5, 30));
    grid.appendChild(num("Trace-stitch gap up to (m)", cfg, "stitch_gap_m", 10, 150));
    grid.appendChild(boolField("Reconstruct per route (ramal)", cfg, "reconstruct_per_route", true));
    grid.appendChild(boolField("Infer direction (else trust sim)", cfg, "infer_direction", false));
    grid.appendChild(boolField("Bridge gaps (Valhalla)", cfg, "bridge_gaps", false));
    grid.appendChild(selectField("Ramal discovery (blind)", cfg, "ramal_discovery",
      [["components", "Components (bottom-up)"],
       ["divergence", "Divergence (top-down)"]], "components"));
    grid.appendChild(num("Ramal terminus consistency", cfg, "terminus_consistency_min_share", 0.05, 0.6));
    grid.appendChild(num("Ramal min cluster size", cfg, "ramal_min_cluster_size", 1, 3));
    body.appendChild(grid);
  }));
}

function boolField(label, obj, key, fallback = false) {
  const frag = document.createDocumentFragment();
  const labelEl = document.createElement("label");
  labelEl.textContent = label;
  const input = document.createElement("input");
  input.type = "checkbox";
  input.checked = obj[key] ?? fallback;
  input.onchange = () => {
    obj[key] = input.checked;
    renderBuilderForm();   // toggling a noise layer shows/hides its params
    schedulePreview();
  };
  frag.appendChild(labelEl);
  frag.appendChild(input);
  return frag;
}

function selectField(label, obj, key, options, fallback) {
  const frag = document.createDocumentFragment();
  const labelEl = document.createElement("label");
  labelEl.textContent = label;
  const select = document.createElement("select");
  for (const [value, text] of options) {
    const opt = document.createElement("option");
    opt.value = value;
    opt.textContent = text;
    if ((obj[key] ?? fallback) === value) opt.selected = true;
    select.appendChild(opt);
  }
  select.onchange = () => { obj[key] = select.value; schedulePreview(); };
  frag.appendChild(labelEl);
  frag.appendChild(select);
  return frag;
}

async function uploadRouteFile(input) {
  const file = input.files[0];
  if (!file) return;
  try {
    const geojson = JSON.parse(await file.text());
    const name = file.name.replace(/\.(geo)?json$/i, "");
    const saved = await postRoute(name, geojson);
    builderConfig.routes.push({
      name: saved.name, path: saved.path,
      role: builderConfig.routes.length ? "ramal" : "main",
      replaces: null, from_day: 0, to_day: null, fraction_of_trips: 1.0,
    });
    renderBuilderForm();
    schedulePreview();
  } catch (e) {
    showBuilderError(`Upload failed: ${e.message}`);
  }
}

async function postRoute(name, geojson) {
  const resp = await fetch("/api/routes", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, geojson }),
  });
  if (!resp.ok) throw new Error((await resp.json()).detail || resp.status);
  const saved = await resp.json();
  routeCatalog = await api("/routes");
  return saved;
}

/* ---------- draw mode ---------- */

function startDrawing() {
  if (drawing) return;
  drawing = { coords: [] };
  map.getCanvas().style.cursor = "crosshair";
  map.on("click", drawClick);
  document.addEventListener("keydown", drawKey);
  updateDrawHint();
}

function drawClick(event) {
  drawing.coords.push([event.lngLat.lng, event.lngLat.lat]);
  updateDrawHint();
  refreshPreview(false);
}

function drawKey(event) {
  if (!drawing) return;
  if (event.key === "Escape") cancelDrawing();
  if (event.key === "Backspace") {
    drawing.coords.pop();
    updateDrawHint();
    refreshPreview(false);
    event.preventDefault();
  }
  if (event.key === "Enter") finishDrawing();
}

function updateDrawHint() {
  const hint = document.getElementById("draw-hint");
  if (!hint) return;
  if (!drawing) { hint.innerHTML = ""; return; }
  hint.innerHTML =
    `Drawing: ${drawing.coords.length} points — click the map to add, ` +
    `Backspace = undo, Esc = cancel. `;
  if (drawing.coords.length >= 2) {
    const finish = document.createElement("button");
    finish.className = "small";
    finish.textContent = "✔ Finish & save";
    finish.onclick = finishDrawing;
    hint.appendChild(finish);
  }
}

async function finishDrawing() {
  if (!drawing || drawing.coords.length < 2) return;
  const name = prompt("Name for the drawn route:", "drawn_route");
  if (!name) return;
  try {
    const geojson = {
      type: "FeatureCollection",
      features: [{
        type: "Feature",
        geometry: { type: "LineString", coordinates: drawing.coords },
        properties: { drawn: true },
      }],
    };
    const saved = await postRoute(name, geojson);
    builderConfig.routes.push({
      name: saved.name, path: saved.path,
      role: builderConfig.routes.length ? "ramal" : "main",
      replaces: null, from_day: 0, to_day: null, fraction_of_trips: 1.0,
    });
    cancelDrawing();
    renderBuilderForm();
    schedulePreview();
  } catch (e) {
    showBuilderError(`Save failed: ${e.message}`);
  }
}

function cancelDrawing() {
  if (!drawing) return;
  drawing = null;
  map.getCanvas().style.cursor = "";
  map.off("click", drawClick);
  document.removeEventListener("keydown", drawKey);
  updateDrawHint();
  refreshPreview(false);
}

/* ---------- small form helpers ---------- */

function section(title, fill) {
  const div = document.createElement("div");
  div.className = "builder-section";
  const h = document.createElement("h3");
  h.textContent = title;
  div.appendChild(h);
  fill(div);
  return div;
}

function fieldGrid() {
  const div = document.createElement("div");
  div.className = "field-grid";
  return div;
}

const percentField = {
  toInput: (v) => Math.round((v ?? 0) * 100),
  fromInput: (v) => Number(v) / 100,
};

function num(label, obj, key, step = 1, fallback = undefined, transform = null) {
  const frag = document.createDocumentFragment();
  const labelEl = document.createElement("label");
  labelEl.textContent = label;
  const input = document.createElement("input");
  input.type = "number";
  input.step = step;
  let value = obj[key];
  if ((value === undefined || value === null) && fallback !== undefined) {
    value = transform ? transform.fromInput(fallback) : fallback;
  }
  input.value = transform ? transform.toInput(value) : (value ?? "");
  input.onchange = () => {
    obj[key] = transform ? transform.fromInput(input.value) : Number(input.value);
    schedulePreview();
  };
  frag.appendChild(labelEl);
  frag.appendChild(input);
  return frag;
}

const _POS_BINS = 12;
const _POS_SHAPES = {
  Uniform: () => 1,
  Center: (t) => Math.exp(-((t - 0.5) ** 2) / (2 * 0.18 ** 2)),
  Edges: (t) => 0.08 + Math.abs(t - 0.5) * 2,
  Start: (t) => Math.max(0.05, 1 - t),
  End: (t) => Math.max(0.05, t),
};

/* Draggable density editor for a per-group position profile (drag the bars to
   shape where things concentrate along the zone, start → end). `key` is the
   persona field (trip_position_weights or vote_position_weights). */
function positionEditor(persona, key, label, color) {
  const N = _POS_BINS;
  if (!Array.isArray(persona[key]) || persona[key].length !== N) {
    persona[key] = new Array(N).fill(1);
  }
  const weights = persona[key];

  const wrap = document.createElement("div");
  wrap.className = "pos-editor";
  const lbl = document.createElement("div");
  lbl.className = "muted";
  lbl.textContent = label;
  wrap.appendChild(lbl);

  const W = 240, H = 60;
  const NS = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svg.classList.add("pos-svg");

  const draw = () => {
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    const max = Math.max(...weights, 1e-6);
    const bw = W / N;
    for (let i = 0; i < N; i++) {
      const h = Math.max(1, (weights[i] / max) * (H - 2));
      const r = document.createElementNS(NS, "rect");
      r.setAttribute("x", i * bw + 0.5);
      r.setAttribute("y", H - h);
      r.setAttribute("width", bw - 1);
      r.setAttribute("height", h);
      r.setAttribute("fill", color);
      svg.appendChild(r);
    }
  };
  const setFromEvent = (e) => {
    const rect = svg.getBoundingClientRect();
    const i = Math.max(0, Math.min(N - 1,
      Math.floor(((e.clientX - rect.left) / rect.width) * N)));
    weights[i] = Math.max(0, Math.min(1, 1 - (e.clientY - rect.top) / rect.height));
    draw();
    schedulePreview();
  };
  let dragging = false;
  svg.addEventListener("pointerdown", (e) => {
    dragging = true; svg.setPointerCapture(e.pointerId); setFromEvent(e); e.preventDefault();
  });
  svg.addEventListener("pointermove", (e) => { if (dragging) setFromEvent(e); });
  svg.addEventListener("pointerup", () => { dragging = false; });
  wrap.appendChild(svg);

  const presets = document.createElement("div");
  presets.className = "pos-presets";
  for (const [name, fn] of Object.entries(_POS_SHAPES)) {
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = name;
    b.onclick = () => {
      for (let i = 0; i < N; i++) weights[i] = fn((i + 0.5) / N);
      const mx = Math.max(...weights, 1e-6);
      for (let i = 0; i < N; i++) weights[i] /= mx;
      draw();
      schedulePreview();
    };
    presets.appendChild(b);
  }
  wrap.appendChild(presets);

  draw();
  return wrap;
}

function wideText(label, obj, key, onchange = null) {
  const div = document.createElement("div");
  div.className = "field-wide";
  const input = document.createElement("input");
  input.type = "text";
  input.placeholder = label;
  input.value = obj[key] ?? "";
  input.onchange = () => {
    obj[key] = input.value;
    schedulePreview();
    if (onchange) onchange();
  };
  div.appendChild(input);
  return div;
}

function wideTextarea(label, obj, key) {
  const div = document.createElement("div");
  div.className = "field-wide";
  const input = document.createElement("textarea");
  input.rows = 2;
  input.placeholder = label;
  input.value = obj[key] ?? "";
  input.onchange = () => { obj[key] = input.value; };
  div.appendChild(input);
  return div;
}

function itemCard(title, color, onRemove) {
  const card = document.createElement("div");
  card.className = "item-card";
  const head = document.createElement("div");
  head.className = "card-title";
  head.innerHTML = `<span class="chip" style="background:${color}"></span><span>${title}</span>`;
  const remove = document.createElement("button");
  remove.className = "remove-item";
  remove.textContent = "✕";
  remove.onclick = onRemove;
  head.appendChild(remove);
  card.appendChild(head);
  return card;
}

function addButton(label, onClick) {
  const button = document.createElement("button");
  button.className = "add-item";
  button.textContent = label;
  button.onclick = onClick;
  return button;
}

function showBuilderError(message) {
  const el = document.getElementById("builder-error");
  el.textContent = message || "";
  el.hidden = !message;
}

/* ---------- map preview ---------- */

async function routeCoords(path) {
  if (!path) return null;
  if (!(path in routeCoordsCache)) {
    try {
      const data = await api(`/routes/geojson?path=${encodeURIComponent(path)}`);
      routeCoordsCache[path] = firstLineString(data);
    } catch {
      routeCoordsCache[path] = null;
    }
  }
  return routeCoordsCache[path];
}

function firstLineString(data) {
  const features = data.features || (data.type === "Feature" ? [data] : []);
  for (const f of features) {
    const g = f.geometry || {};
    if (g.type === "LineString") return g.coordinates.map((c) => [c[0], c[1]]);
    if (g.type === "MultiLineString") return g.coordinates.flat().map((c) => [c[0], c[1]]);
  }
  return null;
}

function schedulePreview() {
  clearTimeout(previewTimer);
  previewTimer = setTimeout(() => refreshPreview(false), 250);
  scheduleTracePreview();
}

/* ---------- live trace pre-visualization ---------- */

let tracePreviewTimer = null;
let tracePreviewAbort = null;

function scheduleTracePreview() {
  clearTimeout(tracePreviewTimer);
  tracePreviewTimer = setTimeout(fetchTracePreview, 450);
}

async function fetchTracePreview() {
  if (!builderConfig || document.getElementById("builder-panel").hidden) return;
  if (tracePreviewAbort) tracePreviewAbort.abort();
  tracePreviewAbort = new AbortController();
  try {
    const resp = await fetch("/api/preview/traces", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ config: builderConfig, max_trips: 12 }),
      signal: tracePreviewAbort.signal,
    });
    if (!resp.ok) { setSimTraces([]); return; }
    const data = await resp.json();
    setSimTraces(data.features || []);
    const hint = document.getElementById("trace-preview-hint");
    if (hint) {
      hint.textContent =
        `Live preview: ${data.sampled} sample traces of ${data.total_trips} total trips.`;
    }
  } catch (e) {
    if (e.name !== "AbortError") setSimTraces([]);
  }
}

let _lastTraceFeatures = [];

function setSimTraces(features) {
  _lastTraceFeatures = features || [];
  _renderSimTraces();
}

function _renderSimTraces() {
  // Client-side filter by group visibility (robust — no map filter expression).
  const visible = _lastTraceFeatures.filter(
    (f) => !(f.properties && hiddenGroups.has(f.properties.persona)));
  const data = { type: "FeatureCollection", features: visible };
  const apply = () => {
    if (!map.getSource("builder-sim-src")) {
      map.addSource("builder-sim-src", { type: "geojson", data });
      map.addLayer({
        id: "builder-sim", type: "line", source: "builder-sim-src",
        layout: { "line-cap": "round", "line-join": "round" },
        paint: {
          "line-color": ["coalesce", ["get", "color"], "#f2994a"],
          "line-width": 1.5,
          "line-opacity": 0.75,
        },
      });
    } else {
      map.getSource("builder-sim-src").setData(data);
    }
  };
  if (map.isStyleLoaded()) apply();
  else map.once("load", apply);
}

function clearSimTraces() {
  if (map.getLayer("builder-sim")) map.removeLayer("builder-sim");
  if (map.getSource("builder-sim-src")) map.removeSource("builder-sim-src");
}

// haversineM is defined in app.js (loaded first, shared global scope).

function sliceByFraction(coords, f0, f1) {
  if (!coords || coords.length < 2) return [];
  const cumulative = [0];
  for (let i = 1; i < coords.length; i++) {
    cumulative.push(cumulative[i - 1] + haversineM(coords[i - 1], coords[i]));
  }
  const total = cumulative[cumulative.length - 1];
  const lo = Math.max(0, Math.min(f0, f1)) * total;
  const hi = Math.min(1, Math.max(f0, f1)) * total;
  const at = (d) => {
    let i = 1;
    while (i < cumulative.length - 1 && cumulative[i] < d) i++;
    const seg = cumulative[i] - cumulative[i - 1] || 1;
    const t = (d - cumulative[i - 1]) / seg;
    return [
      coords[i - 1][0] + t * (coords[i][0] - coords[i - 1][0]),
      coords[i - 1][1] + t * (coords[i][1] - coords[i - 1][1]),
    ];
  };
  const out = [at(lo)];
  for (let i = 0; i < coords.length; i++) {
    if (cumulative[i] > lo && cumulative[i] < hi) out.push(coords[i]);
  }
  out.push(at(hi));
  return out;
}

async function refreshPreview(fit = false) {
  if (!builderConfig || document.getElementById("builder-panel").hidden) return;
  const features = [];

  const coordsByRouteName = {};
  for (const route of builderConfig.routes || []) {
    const coords = await routeCoords(route.path);
    if (!coords) continue;
    coordsByRouteName[route.name] = coords;
    features.push(lineFeature(coords, {
      kind: route.role === "detour" ? "detour" : "route",
      color: ROLE_COLORS[route.role] || "#9aa0a8",
    }));
  }

  (builderConfig.personas || []).forEach((persona, index) => {
    const coords = coordsByRouteName[persona.route] ||
      Object.values(coordsByRouteName)[0];
    if (!coords) return;
    // Tag each persona-owned feature so setBuilderLayers can honor the eye
    // toggle at render time (viz only — the group is still simulated).
    (persona.fare_areas || []).forEach((area, areaIndex) => {
      features.push(lineFeature(
        sliceByFraction(coords, area.start_fraction, area.end_fraction),
        { kind: "fare", color: FARE_COLORS[areaIndex % FARE_COLORS.length],
          persona: persona.name },
      ));
    });
    const [w0, w1] = persona.travel_window || [0, 1];
    features.push(lineFeature(
      sliceByFraction(coords, w0, w1),
      { kind: "window", color: personaColor(persona, index),
        persona: persona.name },
    ));
  });

  if (drawing && drawing.coords.length) {
    if (drawing.coords.length >= 2) {
      features.push(lineFeature(drawing.coords, { kind: "drawing", color: "#ffffff" }));
    }
    for (const c of drawing.coords) {
      features.push({
        type: "Feature",
        geometry: { type: "Point", coordinates: c },
        properties: { kind: "draw-point", color: "#ffffff" },
      });
    }
  }

  setBuilderLayers(features, fit);
}

function lineFeature(coords, properties) {
  return {
    type: "Feature",
    geometry: { type: "LineString", coordinates: coords },
    properties,
  };
}

const BUILDER_LAYERS = [
  { id: "builder-fare", kind: "fare", type: "line", paint: { "line-color": ["get", "color"], "line-width": 14, "line-opacity": 0.25 } },
  { id: "builder-route", kind: "route", type: "line", paint: { "line-color": ["get", "color"], "line-width": 3, "line-opacity": 0.8 } },
  { id: "builder-window", kind: "window", type: "line", paint: { "line-color": ["get", "color"], "line-width": 5, "line-opacity": 0.85 } },
  { id: "builder-detour", kind: "detour", type: "line", paint: { "line-color": ["get", "color"], "line-width": 3, "line-opacity": 0.95, "line-dasharray": [2, 2] } },
  { id: "builder-drawing", kind: "drawing", type: "line", paint: { "line-color": ["get", "color"], "line-width": 3, "line-opacity": 0.9, "line-dasharray": [1, 1] } },
  { id: "builder-draw-points", kind: "draw-point", type: "circle", paint: { "circle-radius": 4, "circle-color": ["get", "color"], "circle-stroke-width": 1, "circle-stroke-color": "#16181d" } },
];

let _lastBuilderFeatures = [];

function setBuilderLayers(features, fit) {
  _lastBuilderFeatures = features;
  // Honor the eye toggle at render time: persona-tagged features of a hidden
  // group are dropped (viz only). Untagged features (route/detour/drawing)
  // have persona === undefined, which is never in hiddenGroups, so they stay.
  const visible = features.filter((f) => !hiddenGroups.has(f.properties.persona));
  const data = { type: "FeatureCollection", features: visible };
  const apply = () => {
    if (!map.getSource("builder-src")) {
      map.addSource("builder-src", { type: "geojson", data });
      for (const spec of BUILDER_LAYERS) {
        map.addLayer({
          id: spec.id, type: spec.type, source: "builder-src",
          filter: ["==", ["get", "kind"], spec.kind],
          ...(spec.type === "line" ? { layout: { "line-cap": "round", "line-join": "round" } } : {}),
          paint: spec.paint,
        });
      }
    } else {
      map.getSource("builder-src").setData(data);
    }
    if (fit && features.length) {
      let bounds = null;
      for (const f of features) {
        const coords = f.geometry.type === "Point" ? [f.geometry.coordinates] : f.geometry.coordinates;
        for (const c of coords) {
          bounds = bounds || new maplibregl.LngLatBounds(c, c);
          bounds.extend(c);
        }
      }
      if (bounds) map.fitBounds(bounds, { padding: 48, duration: 500 });
    }
  };
  if (map.isStyleLoaded()) apply();
  else map.once("load", apply);
}

function clearBuilderLayers() {
  for (const spec of BUILDER_LAYERS) {
    if (map.getLayer(spec.id)) map.removeLayer(spec.id);
  }
  if (map.getSource("builder-src")) map.removeSource("builder-src");
}

/* ---------- save ---------- */

async function saveScenario() {
  showBuilderError("");
  const id = (builderConfig.name || "").trim();
  if (!id) { showBuilderError("Scenario needs a name."); return; }
  try {
    const resp = await fetch(`/api/scenarios/${encodeURIComponent(id)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(builderConfig),
    });
    if (!resp.ok) {
      const detail = (await resp.json()).detail;
      throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail, null, 1));
    }
    const { saved } = await resp.json();
    await loadScenarios();
    document.getElementById("scenario-select").value = saved;
    document.getElementById("scenario-select").dispatchEvent(new Event("change"));
    const el = document.getElementById("builder-error");
    el.hidden = false;
    el.style.color = "#6fcf97";
    el.textContent = `Saved as scenarios/${saved}.yaml ✓`;
    setTimeout(() => { el.hidden = true; el.style.color = ""; }, 2500);
  } catch (e) {
    showBuilderError(`Save failed: ${e.message}`);
  }
}
