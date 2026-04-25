# E2E Tests

End-to-end tests for the CBBA Mobility app using [Maestro](https://maestro.mobile.dev/).

## Prerequisites

- PostgreSQL running locally with user `transit`
- Valhalla running on port 8002 (`docker compose up -d valhalla`)
- Maestro installed: `brew install maestro`
- iOS Simulator or Android Emulator running

## Quick Start

```bash
# Run all tests
./e2e/run-tests.sh

# Or step by step:
./e2e/setup.sh          # Create test DB + start test server
maestro test e2e/flows/  # Run UI tests
./e2e/teardown.sh        # Clean up
```

## Test Structure

- `e2e/setup.sh` -- Creates test database, seeds data, starts test server on port 8001
- `e2e/teardown.sh` -- Stops test server
- `e2e/seed.py` -- Inserts known test data (3 lines, routes, detours, trips)
- `e2e/test_detour_lifecycle.py` -- Server-side pytest tests for detour confidence decay
- `e2e/flows/*.yaml` -- Maestro UI test flows

## Test Flows

| Flow | Description |
|------|-------------|
| explore-nearby-lines | Verify nearby lines appear |
| explore-nearby-radius-filter | Test 500m/2km/5km radius filtering |
| explore-search-route | Search origin to destination, view results + map |
| explore-detour-alert | Verify detour badges and alerts |
| explore-preferences-pending | Toggle pending lines on/off |
| explore-preferences-compare | Compare search results with/without pending |
| detour-confidence-decay | Verify detour age display |
| record-trip | Record a normal trip |
| record-detour | Record + flag as detour |
| record-cancel | Discard a recording |
| contribute-vote-route | Vote on route accuracy |
| contribute-vote-line | Vote on line familiarity |
| favorites-save-and-view | Save route then verify in favorites |
| favorites-view-saved | View saved trips list |
| favorites-delete | Delete a saved trip |

## Environment Variables

- `API_BASE_URL` -- Server URL for the app (default: hardcoded IP)
- `DATABASE_URL` -- Test database connection string
- `TEST_SERVER_URL` -- Test server URL for pytest tests
