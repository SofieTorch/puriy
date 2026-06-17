# Plan: Full E2E Test Suite with Maestro + Test Environment

## Context

The app has 4 tabs (Explore, Record, Contribute, Favorites) with 15+ distinct features, a FastAPI backend with 25+ endpoints, and PostGIS spatial queries. We need a reproducible test environment with seeded data and Maestro UI tests covering every user flow.

---

## Architecture

```
┌─────────────┐     ┌──────────────────┐     ┌──────────────────┐
│   Maestro   │────▶│   App (Expo Go)  │────▶│  Test Server     │
│   e2e/      │     │   Simulator      │     │  port 8001       │
│   flows/    │     │   API→:8001      │     │  test DB         │
└─────────────┘     └──────────────────┘     │  + Valhalla:8002 │
                                              └──────────────────┘
```

- **Test DB**: `open_transit_e2e` PostgreSQL database, wiped and seeded before each run
- **Test server**: Same FastAPI app on port 8001, pointing to test DB
- **App**: `API_BASE_URL` made configurable via `app.config.ts` + Expo Constants
- **Valhalla**: Shared (same instance, port 8002) — read-only, no test isolation needed
- **Maestro**: YAML test flows in `e2e/flows/`, run against iOS/Android simulator

---

## Work Units

### Unit 1: Test environment infrastructure
**Files:**
- `e2e/setup.sh` (new) — creates test DB, runs migrations, seeds data, starts test server
- `e2e/teardown.sh` (new) — stops test server, optionally drops test DB
- `e2e/seed.py` (new) — Python script to insert known test data (lines, routes, edges, detours, recordings)
- `e2e/.env.test` (new) — environment variables for test server

**Description:** Create scripts to set up a reproducible test environment:
- `setup.sh`: Creates `open_transit_e2e` database, enables PostGIS, runs Alembic migrations, runs `seed.py`, starts uvicorn on port 8001 in background
- `seed.py`: Inserts 3 known lines (Line 150, Line A, Line 250) with imported routes from trufi_gtfs GeoJSON, creates a detour on Line 250, creates trip sessions with known device_id, creates edge votes, rebuilds transit graph
- `teardown.sh`: Kills test server, drops test DB

### Unit 2: App config — environment-based API URL
**Files:**
- `app/app.config.ts` (new) — replaces static app.json for dynamic config
- `app/services/api.ts` (modify) — read API_BASE_URL from Expo Constants
- `app/app.json` (modify or remove — replaced by app.config.ts)

**Description:** Make `API_BASE_URL` configurable via environment variable so the app can point to the test server:
- Create `app.config.ts` that reads `process.env.API_BASE_URL` and puts it in `expo.extra`
- Update `api.ts` to read from `Constants.expoConfig?.extra?.apiBaseUrl` with fallback to current hardcoded IP
- For test runs: `API_BASE_URL=http://localhost:8001 npx expo start`

### Unit 3: Maestro — Explore tab flows
**Files:**
- `e2e/flows/explore-nearby-lines.yaml` — verify nearby lines appear with radius selector
- `e2e/flows/explore-nearby-radius-filter.yaml` — test radius changes: 500m shows 0 lines, 2km shows 1, 5km shows 2
- `e2e/flows/explore-search-route.yaml` — search origin/destination, see results, tap route, see map
- `e2e/flows/explore-detour-alert.yaml` — verify detour badge on nearby line + detour alert on route result
- `e2e/flows/explore-preferences-pending.yaml` — toggle pending on/off and verify nearby lines + search results change
- `e2e/flows/explore-preferences-compare.yaml` — search same route with pending OFF (fewer results) then ON (more results), compare

**Description:** Maestro flows for the Explore tab:
1. **Nearby lines**: Open app → verify "Líneas cercanas" section → verify lines appear
2. **Radius filter**: Set location near edge of Line 250's route → select 500m → assert "No se encontraron" → select 2km → assert "250 Ecologica" appears → select 5km → assert "120 UMSS" also appears
3. **Search route**: Type origin → pick suggestion → type destination → pick → tap "Buscar ruta" → verify results → tap route → verify map + steps
4. **Detour alert**: Verify ⚠️ badge on line with detour → tap line → verify detour overlay on map
5. **Preferences — pending toggle**:
   - Open preferences → verify both toggles are OFF
   - Note nearby lines count (only approved lines)
   - Toggle "Incluir líneas pendientes" ON → verify "Test Pending" line now appears in nearby list
   - Toggle OFF → verify it disappears
6. **Preferences — search comparison**:
   - Search route with pending OFF → note number of route options
   - Open preferences → toggle pending ON → search same route → verify different/additional results
   - Toggle OFF → search again → verify original results return

### Unit 4: Maestro — Record tab flows
**Files:**
- `e2e/flows/record-trip.yaml` — start recording, wait, stop, select line, save
- `e2e/flows/record-detour.yaml` — record trip, toggle detour, select reason, confirm, publish
- `e2e/flows/record-cancel.yaml` — start recording, stop, discard

**Description:** Maestro flows for the Record tab:
1. **Normal recording**: Navigate to Record → swipe to start → wait 5s → swipe to stop → select line "250 Ecologica" → save → verify sync
2. **Detour recording**: Record → stop → select line → toggle "Es un desvío" → select "Construcción" → tap "Revisar desvío" → verify confirmation map → tap "Publicar desvío"
3. **Cancel**: Record → stop → tap "Descartar" → verify returns to record screen

### Unit 5: Detour confidence decay tests (server-side)
**Files:**
- `e2e/flows/detour-confidence-decay.yaml` — verify detour label changes over time
- `e2e/test_detour_lifecycle.py` (new) — pytest tests that manipulate `last_confirmed_at` timestamps

**Description:** Test that detour confidence reduces and eventually expires. Since we can't wait 7 real days, we manipulate `last_confirmed_at` directly in the test DB:

**Server-side pytest tests** (`e2e/test_detour_lifecycle.py`):
1. **Fresh detour (day 0)**: Create detour → query `/detours/active/{line_id}` → assert `confidence_pct=100`, `days_since_confirmed=0`
2. **Aging detour (day 3)**: Set `last_confirmed_at = now - 3 days` → query → assert `confidence_pct≈57`, `days_since_confirmed=3`
3. **Near expiry (day 6)**: Set `last_confirmed_at = now - 6 days` → query → assert `confidence_pct≈14`, `days_since_confirmed=6`
4. **Expired (day 8)**: Set `last_confirmed_at = now - 8 days` → call `POST /detours/cleanup` → query → assert detour no longer in active list
5. **Confirmation resets**: Create aging detour (day 5) → `POST /detours/{id}/confirm` → query → assert `days_since_confirmed=0`, `confidence_pct=100`
6. **Nearby lines confidence display**: Create detour at day 3 → query `/lines/nearby/` → assert `detour_alert.confidence_pct≈57` and `detour_alert.days_since_confirmed=3`

**Maestro flow** (`detour-confidence-decay.yaml`):
- Seed a detour with `last_confirmed_at = now - 3 days` via API before test
- Open app → navigate to nearby lines → verify "Confirmado hace 3 días" text on the detour badge

### Unit 6: Maestro — Contribute tab flows (renumbered)
**Files:**
- `e2e/flows/contribute-vote-route.yaml` — vote approve/reject on a route segment
- `e2e/flows/contribute-vote-line.yaml` — vote on nearby line familiarity

**Description:** Maestro flows for the Contribute tab:
1. **Route voting**: Navigate to Contribute → verify pending routes → tap "Ver ruta" → tap approve → verify success
2. **Line voting**: Verify "¿Conoces estas líneas?" section → tap checkmark → verify line removed from list

### Unit 6: Maestro — Favorites tab flows
**Files:**
- `e2e/flows/favorites-view-saved.yaml` — verify saved trips appear, tap to see map
- `e2e/flows/favorites-save-and-view.yaml` — search route → save as commute → go to favorites → verify appears
- `e2e/flows/favorites-delete.yaml` — delete a saved trip

**Description:** Maestro flows for the Favorites tab:
1. **View saved**: Navigate to Favorites → verify "Recurrentes" / "Para hoy" sections → tap trip → verify map
2. **Save and view**: Search a route → save as "Viaje recurrente" → go to Favorites → verify it appears
3. **Delete**: Tap trash on a trip → confirm → verify removed

### Unit 7: Maestro run script + CI integration
**Files:**
- `e2e/run-tests.sh` (new) — full test runner: setup → build app → run maestro → teardown
- `e2e/README.md` (new) — documentation for running E2E tests
- `Makefile` or `package.json` script (modify) — `npm run e2e` shortcut

**Description:** Create the orchestration script:
```bash
#!/bin/bash
# 1. Setup test environment
./e2e/setup.sh
# 2. Start Expo with test API URL
API_BASE_URL=http://localhost:8001 npx expo start --ios &
# 3. Wait for app to load
sleep 15
# 4. Run Maestro tests
maestro test e2e/flows/
# 5. Teardown
./e2e/teardown.sh
```

---

## Seed Data (e2e/seed.py)

Known test data that all flows can rely on:

| Entity | Name | Details |
|--------|------|---------|
| Line 1 | "250 Ecologica" | status=APPROVED, route passes through `-66.182, -17.394` (within 500m of test location) |
| Line 2 | "120 UMSS" | status=APPROVED, route ~3km from test location (appears at 5km radius) |
| Line 3 | "Test Pending" | status=PENDING, route near test location (only visible with pending ON) |
| Detour | on Line 250 | reason="construction", active, confirmed today, map-matched path |
| Trip Sessions | 3 trips on Line 250 | device_id="test-device", cleaned, with computed_path |
| Edge Votes | partial | some edges voted on Line 250, none on Line 120 |
| Transit Graph | built | `POST /directions/graph/rebuild` called after seeding |

**Simulator location:** All flows set to `-17.394, -66.182`:
- **500m radius**: Only Line 250 visible (route passes within 242m)
- **2km radius**: Still only Line 250
- **5km radius**: Line 250 + Line 120 (at ~3km distance)
- **With pending ON**: Test Pending line also appears

**Admin test endpoint** — Add `POST /detours/{id}/set-confirmed-at` (test-only, guarded by env var) to manipulate `last_confirmed_at` for confidence decay tests without waiting real days.

---

## Maestro Flow Template

Each YAML flow follows this pattern:
```yaml
appId: com.anonymous.app
---
- launchApp:
    clearState: true
- setLocation:
    latitude: -17.394
    longitude: -66.182
# ... test steps
- assertVisible: "expected text"
- takeScreenshot: "flow-name-step"
```

---

## E2E Test Recipe (for workers)

Since Maestro tests require a running simulator and server, workers should:
1. Skip e2e — verify files are syntactically valid YAML: `python3 -c "import yaml; yaml.safe_load(open('file.yaml'))"`
2. Verify bash scripts have correct syntax: `bash -n script.sh`
3. Verify Python seed script imports work: `python3 -c "import seed"`

Full e2e is run manually via `./e2e/run-tests.sh` or in CI.

---

## Files Summary

### Create
| File | Purpose |
|------|---------|
| `e2e/setup.sh` | Create test DB, seed, start test server |
| `e2e/teardown.sh` | Stop test server, cleanup |
| `e2e/seed.py` | Insert known test data |
| `e2e/.env.test` | Test environment variables |
| `e2e/run-tests.sh` | Full test orchestration |
| `e2e/README.md` | Documentation |
| `e2e/flows/explore-nearby-lines.yaml` | Maestro: nearby lines |
| `e2e/flows/explore-nearby-radius-filter.yaml` | Maestro: radius filter (500m/2km/5km) |
| `e2e/flows/explore-search-route.yaml` | Maestro: route search |
| `e2e/flows/explore-detour-alert.yaml` | Maestro: detour alerts |
| `e2e/flows/explore-preferences-pending.yaml` | Maestro: pending toggle on/off comparison |
| `e2e/flows/explore-preferences-compare.yaml` | Maestro: search results with/without pending |
| `e2e/flows/detour-confidence-decay.yaml` | Maestro: detour confidence display |
| `e2e/test_detour_lifecycle.py` | Pytest: detour confidence decay + expiry |
| `e2e/flows/record-trip.yaml` | Maestro: record normal trip |
| `e2e/flows/record-detour.yaml` | Maestro: record detour |
| `e2e/flows/record-cancel.yaml` | Maestro: discard recording |
| `e2e/flows/contribute-vote-route.yaml` | Maestro: route voting |
| `e2e/flows/contribute-vote-line.yaml` | Maestro: line voting |
| `e2e/flows/favorites-view-saved.yaml` | Maestro: view saved trips |
| `e2e/flows/favorites-save-and-view.yaml` | Maestro: save + view flow |
| `e2e/flows/favorites-delete.yaml` | Maestro: delete trip |
| `app/app.config.ts` | Dynamic Expo config |

### Modify
| File | Change |
|------|--------|
| `app/services/api.ts` | Read API_BASE_URL from Expo Constants |
